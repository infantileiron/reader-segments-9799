"""API级验证：事件接收幂等、乱序撤销、周汇总生命周期、发布与人工修订并发。

运行：docker compose exec -T backend python -m pytest tests -q
测试始终使用临时SQLite库，不触碰 DATABASE_URL 指向的开发库。
本地无依赖时至少运行 python -m unittest tests.test_aggregation（纯标准库）。
"""
import os,tempfile
os.environ['DATABASE_URL']='sqlite:///'+os.path.join(tempfile.gettempdir(),'reader_events_test.db')
os.environ.setdefault('REDIS_URL','redis://localhost:6379/0')
os.environ.setdefault('JWT_SECRET','test-secret')
os.environ['SEED_DEMO']='false'
import pytest
from fastapi.testclient import TestClient
_db=os.environ['DATABASE_URL'].replace('sqlite:///','')
if os.path.exists(_db):os.remove(_db)
from src.main import app
from src.config.database import Session
from src.models.entities import User,Reader
from src.utils.security import hash_password
@pytest.fixture(scope='session')
def client():
 with TestClient(app) as c:
  with Session() as s:
   for role in ('admin','analyst','viewer'):
    s.add(User(email=role+'@t.local',role=role,password=hash_password('Pass123!')))
   s.commit()
  yield c
@pytest.fixture(scope='session')
def token(client):
 r=client.post('/auth/login',json={'email':'analyst@t.local','password':'Pass123!'})
 assert r.status_code==200,r.text
 return {'Authorization':'Bearer '+r.json()['token']}
@pytest.fixture(scope='session')
def viewer_token(client):
 r=client.post('/auth/login',json={'email':'viewer@t.local','password':'Pass123!'})
 return {'Authorization':'Bearer '+r.json()['token']}
def put_reader(client,token,code,reading=10,completion=0.5,night=0.3):
 r=client.post('/readers',headers=token,json={'code':code,'weekly_reading':reading,'completion':completion,'night_share':night,'note':'测试档案'})
 assert r.status_code==200,r.text
 return r.json()
def test_ingest_and_retry_not_double_counted(client,token):
 put_reader(client,token,'T-101')
 body={'event_id':'T-E01','code':'T-101','article':'A-1','start':'2026-11-10T22:00:00+08:00','end':'2026-11-10T23:00:00+08:00','ratio':0.9}
 r=client.post('/events',headers=token,json=body)
 assert r.status_code==200,r.text
 assert r.json()['state']=='active'
 again=client.post('/events',headers=token,json=body)
 assert again.status_code==200
 assert again.json()['id']==r.json()['id']  # 重试返回同一记录
 events=[e for e in client.get('/events',headers=token).json() if e['event_id']=='T-E01']
 assert len(events)==1  # 不重复计入
 changed=dict(body,article='A-2')
 conflict=client.post('/events',headers=token,json=changed)
 assert conflict.status_code==409  # 同编号不同内容明确冲突
def test_validation(client,token):
 bad={'event_id':'T-BAD','code':'T-101','article':'A-1','start':'2026-11-10T23:00','end':'2026-11-10T22:00','ratio':0.5}
 assert client.post('/events',headers=token,json=bad).status_code==422
 bad2=dict(bad,start='2026-11-10T21:00',ratio=1.5)
 assert client.post('/events',headers=token,json=bad2).status_code==422
def test_out_of_order_revoke_never_revives(client,token):
 put_reader(client,token,'T-102')
 # 撤销先到：事件尚不存在
 r=client.post('/events/revoke',headers=token,json={'event_id':'T-E02','reason':'重复上报，先撤销'})
 assert r.status_code==200,r.text
 # 原事件后到：落库即为已撤销
 late=client.post('/events',headers=token,json={'event_id':'T-E02','code':'T-102','article':'A-9','start':'2026-11-11T10:00:00+08:00','end':'2026-11-11T11:00:00+08:00','ratio':1.0})
 assert late.status_code==200
 assert late.json()['state']=='revoked'
 assert late.json()['revoke_reason']=='重复上报，先撤销'
 # 重试不复活
 retry=client.post('/events',headers=token,json={'event_id':'T-E02','code':'T-102','article':'A-9','start':'2026-11-11T10:00:00+08:00','end':'2026-11-11T11:00:00+08:00','ratio':1.0})
 assert retry.json()['state']=='revoked'
 # 重复撤销幂等，保留首个依据
 again=client.post('/events/revoke',headers=token,json={'event_id':'T-E02','reason':'另一个理由'})
 assert again.status_code==200
 assert again.json()['reason']=='重复上报，先撤销'
 # 撤销事件不贡献指标，也不产生待计算汇总
 done=client.post('/summaries/compute',headers=token,json={'code':'T-102'})
 assert done.json()['computed']==0
 sums=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-102']
 assert sums==[]
def test_revoke_after_ingest_marks_summary_pending(client,token):
 put_reader(client,token,'T-103')
 client.post('/events',headers=token,json={'event_id':'T-E03','code':'T-103','article':'A-1','start':'2026-11-10T22:00:00+08:00','end':'2026-11-10T23:00:00+08:00','ratio':0.8})
 client.post('/summaries/compute',headers=token,json={'code':'T-103'})
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-103'][0]
 assert w['state']=='computed' and w['weekly_reading']==1
 client.post('/events/revoke',headers=token,json={'event_id':'T-E03','reason':'设备时间错误'})
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-103'][0]
 assert w['state']=='pending'  # 数据变更后回到待计算
 client.post('/summaries/compute',headers=token,json={'code':'T-103'})
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-103'][0]
 assert w['weekly_reading']==0 and w['night_share'] is None
def test_cross_week_summary_split(client,token):
 put_reader(client,token,'T-104')
 client.post('/events',headers=token,json={'event_id':'T-E04','code':'T-104','article':'A-1','start':'2026-11-15T23:30:00+08:00','end':'2026-11-16T00:30:00+08:00','ratio':0.8})
 client.post('/summaries/compute',headers=token,json={'code':'T-104'})
 sums={w['week']:w for w in client.get('/summaries',headers=token).json() if w['code']=='T-104'}
 assert set(sums)=={'2026-11-09','2026-11-16'}  # 跨周裁剪成两份汇总
 assert sums['2026-11-09']['detail']['total_seconds']==1800
 assert sums['2026-11-16']['detail']['total_seconds']==1800
 assert sums['2026-11-09']['night_share']==1.0
def test_publish_updates_profile_and_diff_clears(client,token):
 r=put_reader(client,token,'T-105',reading=99,completion=0.1,night=0.1)
 client.post('/events',headers=token,json={'event_id':'T-E05','code':'T-105','article':'A-1','start':'2026-11-10T22:00:00+08:00','end':'2026-11-10T23:00:00+08:00','ratio':0.9})
 client.post('/events',headers=token,json={'event_id':'T-E06','code':'T-105','article':'A-2','start':'2026-11-12T12:00:00+08:00','end':'2026-11-12T13:00:00+08:00','ratio':0.5})
 client.post('/summaries/compute',headers=token,json={'code':'T-105'})
 before=[x for x in client.get('/readers',headers=token).json() if x['code']=='T-105'][0]
 assert set(before['diff'])=={'weekly_reading','completion','night_share'}  # 档案与汇总差异
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-105'][0]
 p=client.post(f"/summaries/{w['id']}/publish",headers=token)
 assert p.status_code==200,p.text
 after=[x for x in client.get('/readers',headers=token).json() if x['code']=='T-105'][0]
 assert after['weekly_reading']==2 and after['completion']==0.7
 assert after['source']=='events' and after['week']=='2026-11-09'
 assert after['version']==r['version']+1
 assert after['diff']==[]  # 发布后差异消除
 again=client.post(f"/summaries/{w['id']}/publish",headers=token)
 assert again.status_code==200  # 重复发布幂等
def test_manual_edit_then_publish_conflict(client,token):
 r=put_reader(client,token,'T-106',reading=5,completion=0.5,night=0.5)
 client.post('/events',headers=token,json={'event_id':'T-E07','code':'T-106','article':'A-1','start':'2026-11-10T22:00:00+08:00','end':'2026-11-10T23:00:00+08:00','ratio':0.9})
 client.post('/summaries/compute',headers=token,json={'code':'T-106'})
 # 计算完成后人工修订档案
 edit=client.put(f"/readers/{r['id']}",headers=token,json={'code':'T-106','weekly_reading':7,'completion':0.6,'night_share':0.4,'note':'人工修订','version':r['version']})
 assert edit.status_code==200,edit.text
 # 发布不得静默覆盖人工修订
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-106'][0]
 p=client.post(f"/summaries/{w['id']}/publish",headers=token)
 assert p.status_code==409
 # 重新计算后即可发布
 client.post('/summaries/compute',headers=token,json={'code':'T-106'})
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-106'][0]
 assert client.post(f"/summaries/{w['id']}/publish",headers=token).status_code==200
 after=[x for x in client.get('/readers',headers=token).json() if x['code']=='T-106'][0]
 assert after['weekly_reading']==1 and after['source']=='events'
def test_manual_edit_stale_version_rejected(client,token):
 r=put_reader(client,token,'T-107')
 ok=client.put(f"/readers/{r['id']}",headers=token,json={'code':'T-107','weekly_reading':1,'completion':0.1,'night_share':0.1,'note':'','version':r['version']})
 assert ok.status_code==200
 stale=client.put(f"/readers/{r['id']}",headers=token,json={'code':'T-107','weekly_reading':2,'completion':0.2,'night_share':0.2,'note':'','version':r['version']})
 assert stale.status_code==409  # 版本过期不静默覆盖
def test_publish_creates_missing_profile(client,token):
 client.post('/events',headers=token,json={'event_id':'T-E08','code':'T-108','article':'A-1','start':'2026-11-10T08:00:00+08:00','end':'2026-11-10T09:00:00+08:00','ratio':0.6})
 client.post('/summaries/compute',headers=token,json={'code':'T-108'})
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-108'][0]
 assert client.post(f"/summaries/{w['id']}/publish",headers=token).status_code==200
 after=[x for x in client.get('/readers',headers=token).json() if x['code']=='T-108'][0]
 assert after['weekly_reading']==1 and after['source']=='events'
def test_pending_summary_not_visible_to_publish(client,token):
 client.post('/events',headers=token,json={'event_id':'T-E09','code':'T-109','article':'A-1','start':'2026-11-10T08:00:00+08:00','end':'2026-11-10T09:00:00+08:00','ratio':0.6})
 w=[w for w in client.get('/summaries',headers=token).json() if w['code']=='T-109'][0]
 assert w['state']=='pending'
 assert client.post(f"/summaries/{w['id']}/publish",headers=token).status_code==409  # 待计算不可发布
def test_viewer_readonly(client,viewer_token):
 assert client.post('/events',headers=viewer_token,json={'event_id':'T-V1','code':'T-1','article':'A','start':'2026-11-10T08:00+08:00','end':'2026-11-10T09:00+08:00','ratio':0.5}).status_code==403
 assert client.post('/events/revoke',headers=viewer_token,json={'event_id':'T-V1','reason':'只读'}).status_code==403
 assert client.get('/events',headers=viewer_token).status_code==200
 assert client.get('/summaries',headers=viewer_token).status_code==200
def test_segments_and_outreach_retained(client,token,monkeypatch):
 # 已完成分群与触达名单保留：既有接口行为不变
 class FakeRedis:
  def __init__(self):self.pushed=[]
  def rpush(self,q,i):self.pushed.append((q,i))
 fake=FakeRedis()
 monkeypatch.setattr('redis.Redis.from_url',lambda url:fake)
 for i in range(4):
  put_reader(client,token,f'T-2{i}',reading=5+i*5,completion=0.3+i*0.2,night=0.2+i*0.2)
 r=client.post('/segments',headers=token,json={'name':'回归验证分群','k':2,'features':['weekly_reading','completion']})
 assert r.status_code==200,r.text
 seg=r.json()
 assert seg['state']=='queued' and seg['result']['snapshot']  # 快照只含已发布/人工确认的档案
 assert fake.pushed==[('reader:segments',seg['id'])]
