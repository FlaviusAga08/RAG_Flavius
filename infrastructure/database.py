from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from domain.models import Base, QueryHistory
import json

class Database:
    def __init__(self, db_url: str = "sqlite:///./history.db"):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)

    def create_tables(self):
        Base.metadata.create_all(bind=self.engine)

    @contextmanager
    def get_db(self) -> Session:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def save_query(self, db: Session, query: str, result: str, sources: list[str]):
        sources_json = json.dumps(sources)
        entry = QueryHistory(query=query, result=result, sources=sources_json)
        db.add(entry)
        db.commit()
        return entry
