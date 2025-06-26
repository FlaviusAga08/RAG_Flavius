from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import asynccontextmanager
from domain.models import QueryHistory
import json

Base = declarative_base()

class Database:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///./history.db"):
        self.engine = create_async_engine(db_url, echo=False)
        self.AsyncSessionLocal = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def create_tables(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_db(self) -> AsyncSession:
        async with self.AsyncSessionLocal() as session:
            yield session


    async def save_query(self, db: AsyncSession, query: str, result: str, sources: list[str]):
        sources_json = json.dumps(sources)
        entry = QueryHistory(query=query, result=result, sources=sources_json)
        db.add(entry)
        await db.commit()
        return entry
