import os,logging
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from src.config.database import Base,engine
from sqlalchemy import text
from src.models import entities
from src.routes.api import router
from src.middlewares.request import RequestId,SecurityHeaders
def ensure_columns():
 """为既有库补齐新增档案列（幂等，仅PostgreSQL）；新表由create_all建立。"""
 if engine.dialect.name!='postgresql':return
 with engine.connect() as c:
  for ddl in["ALTER TABLE readers ADD COLUMN IF NOT EXISTS version integer DEFAULT 1",
   "ALTER TABLE readers ADD COLUMN IF NOT EXISTS source varchar(10) DEFAULT 'manual'",
   "ALTER TABLE readers ADD COLUMN IF NOT EXISTS \"week\" varchar(10)"]:
   c.execute(text(ddl))
  c.commit()
@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 ensure_columns()
 if os.getenv('SEED_DEMO')=='true':
  try:
   from scripts.seed_demo import seed
   seed()
  except Exception:logging.exception('seed failed')
 yield
app=FastAPI(title='内容订阅行为分群',lifespan=lifespan)
app.add_middleware(RequestId);app.add_middleware(SecurityHeaders)
app.include_router(router)
@app.get('/health')
def health():
 from sqlalchemy import text
 import redis
 with engine.connect() as c:c.execute(text('SELECT 1'))
 redis.Redis.from_url(os.environ['REDIS_URL']).ping()
 return {'status':'ok'}
@app.exception_handler(Exception)
async def errors(request:Request,exc:Exception):
 logging.exception('request failed');return JSONResponse(status_code=500,content={'detail':'服务暂时异常，请稍后重试'})
