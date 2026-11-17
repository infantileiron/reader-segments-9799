import random
from src.config.database import Base,engine,Session
from src.models.entities import User,Reader
from src.utils.security import hash_password
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
  s.commit();print({'users':s.query(User).count(),'readers':s.query(Reader).count()})
if __name__=='__main__':seed()
