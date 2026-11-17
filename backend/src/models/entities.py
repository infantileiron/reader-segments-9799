from sqlalchemy import Column,Integer,String,Float,JSON,Text,ForeignKey,UniqueConstraint
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True);password=Column(String(200));role=Column(String(20))
class Reader(Base):
 __tablename__='readers'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);weekly_reading=Column(Float);completion=Column(Float);night_share=Column(Float);note=Column(Text,default='')
 version=Column(Integer,default=1,nullable=False);source=Column(String(10),default='manual',nullable=False);week=Column(String(10))
class ReadEvent(Base):
 __tablename__='read_events'
 id=Column(Integer,primary_key=True);event_id=Column(String(80),unique=True,nullable=False);code=Column(String(60),nullable=False);article=Column(String(120),nullable=False)
 start=Column(String(40),nullable=False);end=Column(String(40),nullable=False);ratio=Column(Float,nullable=False)
 state=Column(String(20),default='active',nullable=False);revoke_reason=Column(Text,default='');created=Column(String(40))
class Revocation(Base):
 __tablename__='revocations'
 id=Column(Integer,primary_key=True);event_id=Column(String(80),unique=True,nullable=False);reason=Column(Text,default='');created=Column(String(40))
class WeeklySummary(Base):
 __tablename__='weekly_summaries'
 id=Column(Integer,primary_key=True);code=Column(String(60),nullable=False);week=Column(String(10),nullable=False)
 state=Column(String(20),default='pending',nullable=False);weekly_reading=Column(Float);completion=Column(Float);night_share=Column(Float)
 detail=Column(JSON);base_reader_version=Column(Integer);updated=Column(String(40))
 __table_args__=(UniqueConstraint('code','week',name='uq_summary_code_week'),)
class Segment(Base):
 __tablename__='segments'
 id=Column(Integer,primary_key=True);name=Column(String(100));k=Column(Integer);features=Column(JSON);state=Column(String(20),default='queued');result=Column(JSON);error=Column(Text,default='')
class Outreach(Base):
 __tablename__='outreaches'
 id=Column(Integer,primary_key=True);segment_id=Column(Integer,ForeignKey('segments.id'));cluster_id=Column(Integer);title=Column(String(100));note=Column(Text);members=Column(JSON);status=Column(String(20),default='draft')
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
