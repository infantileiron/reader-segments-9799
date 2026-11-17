import random
from src.config.database import Base,engine,Session
from src.models.entities import User,Reader,ReadEvent,Revocation,WeeklySummary
from src.utils.security import hash_password
from src.services.events import ingest,revoke,compute_pending
from src.schemas.business import EventInput
DEMO_EVENTS=[
 # SL-001 跨设备重叠：手机与平板同时段读同一篇文章，合并后只计一次
 ('SEED-E01','SL-001','A-101','2026-11-10T22:10:00+08:00','2026-11-10T23:00:00+08:00',0.9),
 ('SEED-E02','SL-001','A-101','2026-11-10T22:20:00+08:00','2026-11-10T23:10:00+08:00',0.95),
 ('SEED-E03','SL-001','A-102','2026-11-12T12:00:00+08:00','2026-11-12T12:40:00+08:00',0.6),
 # SL-002 跨周事件：周日晚读到周一凌晨，两周各计一段；另有一条被撤销
 ('SEED-E04','SL-002','A-103','2026-11-15T23:30:00+08:00','2026-11-16T00:30:00+08:00',0.8),
 ('SEED-E05','SL-002','A-104','2026-11-11T03:00:00+08:00','2026-11-11T04:00:00+08:00',1.0),
 # SL-003 撤销先到：补传事件落库即为已撤销，不复活
 ('SEED-E06','SL-003','A-105','2026-11-13T21:00:00+08:00','2026-11-13T21:45:00+08:00',0.7),
]
DEMO_REVOKE=[('SEED-E05','设备时钟异常，运营复核后撤销'),('SEED-E06','重复上报，先撤销后补传')]
def seed():
 Base.metadata.create_all(engine);rng=random.Random(3107)
 with Session() as s:
  for role in ('admin','analyst','viewer'):
   email=role+'@demo.local'
   if not s.query(User).filter_by(email=email).first():s.add(User(email=email,role=role,password=hash_password('Demo123!')))
  for i in range(240):
   code=f'SL-{i+1:03}';mode=i//80
   reading=round(max(0,rng.gauss([4,14,26][mode],[1.1,3,4][mode])),2)
   completion=round(max(0,min(1,rng.gauss([.32,.81,.61][mode],.06))),4)
   night=round(max(0,min(1,rng.gauss([.18,.23,.77][mode],.08))),4)
   if not s.query(Reader).filter_by(code=code).first():s.add(Reader(code=code,weekly_reading=reading,completion=completion,night_share=night,note='最近完整自然周行为聚合；模拟会员，不含个人联系方式'))
  s.commit()
  for event_id,reason in DEMO_REVOKE:
   if not s.query(Revocation).filter_by(event_id=event_id).first():revoke(s,event_id,reason)
  for event_id,code,article,start,end,ratio in DEMO_EVENTS:
   if not s.query(ReadEvent).filter_by(event_id=event_id).first():
    ingest(s,EventInput(event_id=event_id,code=code,article=article,start=start,end=end,ratio=ratio))
  pending=s.query(WeeklySummary).filter_by(state='pending',detail=None).all()
  if pending:compute_pending(s)
  print({'users':s.query(User).count(),'readers':s.query(Reader).count(),'events':s.query(ReadEvent).count(),'summaries':s.query(WeeklySummary).count()})
if __name__=='__main__':seed()
