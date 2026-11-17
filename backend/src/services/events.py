"""阅读事件接收、撤销与周汇总生命周期（待计算→已计算→已发布）。

幂等口径：事件与撤销均按 event_id 去重，重试返回既有记录不重复计入；
撤销为先到先生效的墓碑，原事件后到或重试都不复活。
"""
from datetime import datetime,timezone
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from src.models.entities import Reader,ReadEvent,Revocation,WeeklySummary
from src.services.aggregation import parse_ts,iso,weeks_spanned,week_label,parse_week,aggregate_week
def now():return datetime.now(timezone.utc).isoformat()
def _lock(s,key):
 """按事件编号串行化接收与撤销（PostgreSQL咨询锁）；SQLite测试库为单线程无需加锁。"""
 if s.get_bind().dialect.name=='postgresql':
  s.execute(text('SELECT pg_advisory_xact_lock(hashtext(:k))'),{'k':key})
def _event_dict(row):
 return {'start':parse_ts(row.start),'end':parse_ts(row.end),'article':row.article,'ratio':row.ratio,
  'state':row.state,'event_id':row.event_id,'revoke_reason':row.revoke_reason}
def touch(s,code,start,end):
 """事件触及的（会员,自然周）汇总标记为待计算；已计算/已发布的回退待重新计算。"""
 for monday in weeks_spanned(start,end):
  label=week_label(monday)
  row=s.query(WeeklySummary).filter_by(code=code,week=label).first()
  if not row:s.add(WeeklySummary(code=code,week=label,state='pending',updated=now()))
  elif row.state!='pending':row.state='pending';row.updated=now()
def ingest(s,data):
 """接收事件；返回 (记录, 是否新写入)。撤销先到的事件落库即为已撤销且永不复活。"""
 _lock(s,'event:'+data.event_id)
 start,end=parse_ts(data.start),parse_ts(data.end)
 ns,ne=iso(start),iso(end)
 existing=s.query(ReadEvent).filter_by(event_id=data.event_id).first()
 if existing:
  if (existing.code,existing.article,existing.start,existing.end,existing.ratio)!=(data.code,data.article,ns,ne,data.ratio):
   return None,'conflict'
  return existing,False
 rev=s.query(Revocation).filter_by(event_id=data.event_id).first()
 row=ReadEvent(event_id=data.event_id,code=data.code,article=data.article,start=ns,end=ne,ratio=data.ratio,
  state='revoked' if rev else 'active',revoke_reason=rev.reason if rev else '',created=now())
 s.add(row)
 try:s.flush()
 except IntegrityError:
  s.rollback();return s.query(ReadEvent).filter_by(event_id=data.event_id).first(),False
 if row.state=='active':touch(s,data.code,start,end)
 s.commit()
 return row,True
def revoke(s,event_id,reason):
 """撤销事件；返回 (撤销记录, 是否新撤销)。重复撤销幂等返回首个撤销依据。"""
 _lock(s,'event:'+event_id)
 rev=s.query(Revocation).filter_by(event_id=event_id).first()
 if rev:return rev,False
 rev=Revocation(event_id=event_id,reason=reason,created=now());s.add(rev)
 ev=s.query(ReadEvent).filter_by(event_id=event_id).first()
 if ev and ev.state=='active':
  ev.state='revoked';ev.revoke_reason=reason
  touch(s,ev.code,parse_ts(ev.start),parse_ts(ev.end))
 try:s.commit()
 except IntegrityError:
  s.rollback();return s.query(Revocation).filter_by(event_id=event_id).first(),False
 return rev,True
def stale_summaries(s,code):
 """人工修订档案后，该会员已计算/已发布的汇总回到待计算，发布不得沿用旧基线。"""
 for w in s.query(WeeklySummary).filter(WeeklySummary.code==code,WeeklySummary.state!='pending').all():
  w.state='pending';w.updated=now()
def compute_pending(s,code=None,week=None):
 """把待计算汇总算成已计算；记录计算时档案版本供发布做并发校验。"""
 q=s.query(WeeklySummary).filter_by(state='pending')
 if code:q=q.filter_by(code=code)
 if week:q=q.filter_by(week=week)
 rows=q.all();done=[]
 for w in rows:
  events=[_event_dict(e) for e in s.query(ReadEvent).filter_by(code=w.code).all()]
  result=aggregate_week(events,parse_week(w.week))
  reader=s.query(Reader).filter_by(code=w.code).first()
  w.weekly_reading=result['weekly_reading'];w.completion=result['completion'];w.night_share=result['night_share']
  w.detail=result['detail'];w.base_reader_version=reader.version if reader else 0
  w.state='computed';w.updated=now();done.append(w.id)
 s.commit();return done
def publish(s,w):
 """发布汇总到阅读档案。人工修订与发布并发时不静默覆盖，版本不符返回409文案。"""
 if w.state=='published':return w,None
 if w.state!='computed':return None,'汇总尚未完成计算，请先计算再发布'
 reader=s.query(Reader).filter_by(code=w.code).with_for_update().first()
 if reader and reader.version!=(w.base_reader_version or 0):
  return None,'计算完成后档案被人工修订，请重新计算再发布，避免覆盖人工修改'
 if reader:
  reader.weekly_reading=w.weekly_reading;reader.completion=w.completion;reader.night_share=w.night_share
  reader.source='events';reader.week=w.week;reader.version=reader.version+1
 else:
  s.add(Reader(code=w.code,weekly_reading=w.weekly_reading,completion=w.completion,night_share=w.night_share,
   source='events',week=w.week,version=1,note='由阅读事件周汇总发布'))
 w.state='published';w.updated=now();s.commit();return w,None
