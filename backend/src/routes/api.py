import os,json
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy.exc import IntegrityError
from src.config.database import db
from src.models.entities import User,Reader,ReadEvent,WeeklySummary,Segment,Outreach,Audit
from src.schemas.business import Login,ReaderInput,ReaderEdit,EventInput,RevokeInput,ComputeInput,SegmentInput,OutreachInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.services.events import ingest,revoke,compute_pending,publish,stale_summaries
from src.constants.enums import FEATURES
from src.controllers.business import ensure_segment
router=APIRouter()
@router.post('/auth/login')
def login(data:Login,s=Depends(db)):
 u=s.query(User).filter_by(email=data.email).first()
 if not u or not verify(data.password,u.password):raise HTTPException(401,'账号或密码错误')
 return {'token':token(u),'user':dump(u)}
@router.get('/me')
def me(u=Depends(current)):return dump(u)
def _same(a,b):
 if a is None or b is None:return a is None and b is None
 return abs(float(a)-float(b))<1e-9
@router.get('/readers')
def readers(u=Depends(current),s=Depends(db)):
 latest={}
 for w in s.query(WeeklySummary).all():
  if w.code not in latest or w.week>latest[w.code].week:latest[w.code]=w
 out=[]
 for r in s.query(Reader).order_by(Reader.id).all():
  d=dump(r);w=latest.get(r.code)
  d['summary']={'id':w.id,'week':w.week,'state':w.state,'weekly_reading':w.weekly_reading,'completion':w.completion,'night_share':w.night_share} if w else None
  d['diff']=[f for f in FEATURES if w and not _same(getattr(r,f),getattr(w,f))]
  out.append(d)
 return out
@router.post('/readers')
def create(data:ReaderInput,u=Depends(editor),s=Depends(db)):
 r=Reader(**data.model_dump());s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'会员编号重复')
 audit(s,u,'录入阅读档案 '+r.code);return dump(r)
@router.put('/readers/{i}')
def edit(i:int,data:ReaderEdit,u=Depends(editor),s=Depends(db)):
 r=s.query(Reader).filter_by(id=i).with_for_update().first()
 if not r:raise HTTPException(404,'会员档案不存在')
 if data.version!=r.version:raise HTTPException(409,'档案已被并发修改（可能刚发布事件汇总），请刷新后重试')
 for k,v in data.model_dump(exclude={'version'}).items():setattr(r,k,v)
 r.version=r.version+1;r.source='manual'
 stale_summaries(s,r.code)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'会员编号重复')
 audit(s,u,'修订档案 '+str(i));return dump(r)
@router.get('/events')
def events(u=Depends(current),s=Depends(db)):
 return [dump(e) for e in s.query(ReadEvent).order_by(ReadEvent.id.desc()).limit(1000).all()]
@router.post('/events')
def create_event(data:EventInput,u=Depends(editor),s=Depends(db)):
 row,created=ingest(s,data)
 if created=='conflict':raise HTTPException(409,'事件编号已存在且内容不一致')
 if created:audit(s,u,'录入事件 '+data.event_id)
 return dump(row)
@router.post('/events/revoke')
def revoke_event(data:RevokeInput,u=Depends(editor),s=Depends(db)):
 rev,created=revoke(s,data.event_id,data.reason)
 if created:audit(s,u,('撤销事件 '+data.event_id+'：'+data.reason)[:190])
 return dump(rev)
@router.get('/summaries')
def summaries(u=Depends(current),s=Depends(db)):
 return [dump(w) for w in s.query(WeeklySummary).order_by(WeeklySummary.week.desc(),WeeklySummary.code).all()]
@router.post('/summaries/compute')
def compute(data:ComputeInput,u=Depends(editor),s=Depends(db)):
 done=compute_pending(s,data.code,data.week)
 if done:audit(s,u,'计算周汇总 '+str(len(done))+' 份')
 return {'computed':len(done),'ids':done}
@router.get('/summaries/{i}')
def summary_detail(i:int,u=Depends(current),s=Depends(db)):
 w=s.get(WeeklySummary,i)
 if not w:raise HTTPException(404,'周汇总不存在')
 return dump(w)
@router.post('/summaries/{i}/publish')
def publish_summary(i:int,u=Depends(editor),s=Depends(db)):
 w=s.query(WeeklySummary).filter_by(id=i).with_for_update().first()
 if not w:raise HTTPException(404,'周汇总不存在')
 row,error=publish(s,w)
 if error:raise HTTPException(409,error)
 audit(s,u,'发布周汇总 '+w.code+' '+w.week)
 return dump(row)
@router.get('/segments')
def segments(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Segment).order_by(Segment.id.desc()).all()]
@router.post('/segments')
def train(data:SegmentInput,u=Depends(editor),s=Depends(db)):
 rows=[dump(r) for r in s.query(Reader).order_by(Reader.id).all()];r=Segment(**data.model_dump(),result={'snapshot':rows});s.add(r);s.commit()
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('reader:segments',r.id)
 except redis.RedisError:r.state='failed';r.error='队列暂不可用，请稍后重试';s.commit();raise HTTPException(503,r.error)
 audit(s,u,'提交分群 '+str(r.id));return dump(r)
@router.get('/segments/{i}')
def detail(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_segment(s,i))
@router.get('/segments/{i}/export')
def export(i:int,u=Depends(current),s=Depends(db)):
 r=ensure_segment(s,i)
 if r.state!='done':raise HTTPException(409,'仅成功分群可导出')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="reader-segments-{i}.json"'})
@router.get('/outreaches')
def outreaches(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Outreach).order_by(Outreach.id.desc()).all()]
@router.post('/outreaches')
def outreach(data:OutreachInput,u=Depends(editor),s=Depends(db)):
 r=ensure_segment(s,data.segment_id)
 if r.state!='done':raise HTTPException(409,'分群完成后才能制定触达方案')
 members=[m['code'] for m in r.result['members'] if m['cluster_id']==data.cluster_id]
 if not members:raise HTTPException(422,'该版本没有所选群组')
 o=Outreach(**data.model_dump(),members=members);s.add(o);s.commit();audit(s,u,'起草触达方案 '+str(o.id));return dump(o)
@router.post('/outreaches/{i}/approve')
def approve(i:int,u=Depends(admin),s=Depends(db)):
 r=s.get(Outreach,i)
 if not r:raise HTTPException(404,'触达方案不存在')
 if r.status!='draft':raise HTTPException(409,'已签核方案不可重复签核')
 r.status='approved';s.commit();audit(s,u,'签核触达方案 '+str(i));return dump(r)
@router.get('/outreaches/{i}/export')
def export_outreach(i:int,u=Depends(current),s=Depends(db)):
 r=s.get(Outreach,i)
 if not r:raise HTTPException(404,'触达方案不存在')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="reader-outreach-{i}.json"'})
@router.get('/audits')
def audits(u=Depends(admin),s=Depends(db)):return [dump(r) for r in s.query(Audit).order_by(Audit.id.desc()).limit(100)]
