from pydantic import BaseModel
from typing import List
from sqlalchemy import Column, Integer, Text, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)
    result = Column(Text, nullable=False)
    sources = Column(Text, nullable=False) 

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    result: str
    sources: List[str]

