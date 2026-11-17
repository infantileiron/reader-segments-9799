from fastapi import HTTPException
from src.models.entities import Segment
def ensure_segment(s,i):
 row=s.get(Segment,i)
 if not row:raise HTTPException(404,'分群版本不存在')
 return row
