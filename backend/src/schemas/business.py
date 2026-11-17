from pydantic import BaseModel,Field,field_validator,model_validator
from typing import Literal,Optional
from src.services.aggregation import parse_ts,parse_week
class Login(BaseModel):email:str;password:str
class ReaderInput(BaseModel):
 code:str=Field(min_length=1,max_length=60)
 weekly_reading:float=Field(ge=0,le=1000,allow_inf_nan=False)
 completion:float=Field(ge=0,le=1,allow_inf_nan=False)
 night_share:float=Field(ge=0,le=1,allow_inf_nan=False)
 note:str=Field(default='',max_length=1000)
class ReaderEdit(ReaderInput):
 version:int=Field(ge=1,description='修订时携带的档案版本号，与发布并发校验')
class EventInput(BaseModel):
 event_id:str=Field(min_length=1,max_length=80)
 code:str=Field(min_length=1,max_length=60)
 article:str=Field(min_length=1,max_length=120)
 start:str=Field(min_length=10,max_length=40)
 end:str=Field(min_length=10,max_length=40)
 ratio:float=Field(ge=0,le=1,allow_inf_nan=False)
 @field_validator('start','end')
 @classmethod
 def ts(cls,v):parse_ts(v);return v
 @model_validator(mode='after')
 def order(self):
  if parse_ts(self.end)<=parse_ts(self.start):raise ValueError('结束时间必须晚于开始时间')
  return self
class RevokeInput(BaseModel):
 event_id:str=Field(min_length=1,max_length=80)
 reason:str=Field(min_length=2,max_length=500)
class ComputeInput(BaseModel):
 code:Optional[str]=Field(default=None,max_length=60)
 week:Optional[str]=None
 @field_validator('week')
 @classmethod
 def wk(cls,v):
  if v is not None:parse_week(v)
  return v
class SegmentInput(BaseModel):
 name:str=Field(min_length=2,max_length=100)
 k:int=Field(default=3,ge=2,le=6)
 features:list[Literal['weekly_reading','completion','night_share']]=Field(default=['weekly_reading','completion','night_share'],min_length=2,max_length=3)
 @field_validator('features')
 @classmethod
 def unique(cls,v):
  if len(set(v))!=len(v):raise ValueError('特征不能重复')
  return v
class OutreachInput(BaseModel):
 segment_id:int=Field(gt=0)
 cluster_id:int=Field(ge=0,le=5)
 title:str=Field(min_length=2,max_length=100)
 note:str=Field(min_length=8,max_length=2000)
