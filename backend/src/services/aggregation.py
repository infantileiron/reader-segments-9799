"""阅读事件按北京时间自然周聚合的纯函数实现。

口径：
- 自然周为北京时间周一00:00（含）至下周一00:00（不含），跨周事件按周界裁剪。
- 篇数按文章去重；完读率为各文章最高完读比例的均值；无文章时留空(None)。
- 夜读占比 = 22:00-06:00 时段并集时长 / 全部时段并集时长；跨设备重叠只计一次。
- 全部时段并集为零时长时夜读占比留空(None)。
"""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
BJ=ZoneInfo('Asia/Shanghai')
NIGHT_END_HOUR=6   # 00:00-06:00
NIGHT_START_HOUR=22 # 22:00-24:00
def parse_ts(text):
 """解析ISO 8601时间；无时区按北京时间处理，统一返回带时区时间。"""
 try:dt=datetime.fromisoformat(str(text).strip().replace('Z','+00:00'))
 except (ValueError,TypeError):raise ValueError('时间需为ISO 8601格式，例如 2026-11-10T22:30:00+08:00')
 if dt.tzinfo is None:dt=dt.replace(tzinfo=BJ)
 return dt
def iso(dt):return dt.astimezone(BJ).isoformat(timespec='seconds')
def week_of(dt):
 """所在北京时间自然周的周一00:00（带时区）。"""
 bj=dt.astimezone(BJ)
 return (bj-timedelta(days=bj.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
def week_label(monday):return monday.date().isoformat()
def parse_week(label):
 """校验并解析 YYYY-MM-DD 周标签，必须是北京时间周一。"""
 try:day=datetime.strptime(str(label).strip(),'%Y-%m-%d')
 except (ValueError,TypeError):raise ValueError('自然周格式需为 YYYY-MM-DD')
 monday=day.replace(tzinfo=BJ)
 if monday.weekday()!=0:raise ValueError('自然周须从北京时间周一开始')
 return monday
def weeks_spanned(start,end):
 """[start,end) 触及的所有北京自然周周一列表，用于标记待计算汇总。"""
 first=week_of(start);last=week_of(end-timedelta(microseconds=1));out=[]
 while first<=last:out.append(first);first+=timedelta(days=7)
 return out
def merge(intervals):
 """合并重叠/相接时段为不相交并集，跨设备重叠阅读只计一次。"""
 out=[]
 for s,e in sorted(intervals):
  if out and s<=out[-1][1]:
   if e>out[-1][1]:out[-1]=(out[-1][0],e)
  else:out.append((s,e))
 return out
def night_windows(monday):
 """该周每天 00:00-06:00 与 22:00-24:00 的夜读窗口。"""
 out=[]
 for d in range(7):
  day=monday+timedelta(days=d)
  out.append((day,day+timedelta(hours=NIGHT_END_HOUR)))
  out.append((day+timedelta(hours=NIGHT_START_HOUR),day+timedelta(days=1)))
 return out
def intersect(intervals,windows):
 """两个时段集合的交集（结果仍为不相交并集）。"""
 pieces=[]
 for s,e in intervals:
  for ws,we in windows:
   a,b=max(s,ws),min(e,we)
   if b>a:pieces.append((a,b))
 return merge(pieces)
def duration(intervals):return sum((e-s).total_seconds() for s,e in intervals)
def aggregate_week(events,monday):
 """聚合某会员某北京自然周的事件。

 events元素需含 start/end(datetime)、article、ratio、state、event_id、revoke_reason。
 仅 state=='active' 的事件计入指标；撤销事件只留痕不贡献。
 """
 week_end=monday+timedelta(days=7)
 frags=[];ratios={};active=0;revoked=[]
 for ev in events:
  s,e=ev['start'],ev['end']
  if s>=week_end or e<=monday:continue
  if ev['state']!='active':
   revoked.append({'event_id':ev['event_id'],'reason':ev.get('revoke_reason') or ''});continue
  cs,ce=max(s,monday),min(e,week_end)
  if ce<=cs:continue
  active+=1;frags.append((cs,ce))
  article=ev['article'];ratio=float(ev['ratio'])
  if article not in ratios or ratio>ratios[article]:ratios[article]=ratio
 merged=merge(frags);night=intersect(merged,night_windows(monday))
 total=duration(merged);night_secs=duration(night)
 detail={'merged':[[iso(s),iso(e)] for s,e in merged],'night':[[iso(s),iso(e)] for s,e in night],
  'articles':[{'article':a,'ratio':round(r,6)} for a,r in sorted(ratios.items())],
  'total_seconds':int(total),'night_seconds':int(night_secs),'active_events':active,
  'revoked_events':len(revoked),'revoked':revoked}
 return {'weekly_reading':len(ratios),
  'completion':round(sum(ratios.values())/len(ratios),6) if ratios else None,
  'night_share':round(night_secs/total,6) if total>0 else None,
  'detail':detail}
