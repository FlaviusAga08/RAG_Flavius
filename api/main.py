import asyncio
from fastapi import FastAPI, BackgroundTasks, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from domain.models import QueryRequest, QueryResponse, QueryHistory
from application.indexer import DocumentIndexer
from infrastructure.watcher import start_directory_watcher
from infrastructure.database import Database
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from dotenv import load_dotenv
from typing import List
import os
import json

DAILY_INDEX_INTERVAL = 24 * 60 * 60  

def create_app() -> FastAPI:
    load_dotenv()
    
    app = FastAPI()
    
    api_key = os.getenv("OPENAI_API_KEY")
    doc_location = os.getenv("LOCATION")
    persist_directory = "db"

    app.state.db = Database()
    app.state.indexer = DocumentIndexer(
        doc_location=doc_location,
        persist_directory=persist_directory,
        api_key=api_key
    )

    async def daily_indexing_loop():
        while True:
            try:
                print("Running daily indexing task...")
                await app.state.indexer.index_documents()
                print("Daily indexing complete.")
            except Exception as e:
                print(f"Error during daily indexing: {e}")
            await asyncio.sleep(DAILY_INDEX_INTERVAL)

    @app.on_event("startup")
    async def startup_event():
        # Create DB tables
        await app.state.db.create_tables()

        # Load existing vector DB (maybe optional if index_documents always runs)
        app.state.indexer.load_vector_db()

        # Start watching directory for changes (change-triggered indexing)
        start_directory_watcher(path=doc_location, indexer=app.state.indexer)

        # Run initial indexing on startup (on-demand first run)
        asyncio.create_task(app.state.indexer.index_documents())

        # Start the daily indexing loop (time-based indexing)
        asyncio.create_task(daily_indexing_loop())

    @app.post("/query", response_model=List[QueryResponse])
    async def query(
        request: QueryRequest,
        top_k: int = Query(5, ge=1, le=20),
        db_session: AsyncSession = Depends(app.state.db.get_db),
    ):
        try:
            responses = await app.state.indexer.query(request.query, top_k=top_k)
            await app.state.db.save_query(
                db_session, request.query, responses[0].result, responses[0].sources
            )
            return responses
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/history", response_model=List[QueryResponse])
    async def get_history(db_session: AsyncSession = Depends(app.state.db.get_db)):
        try:
            result = await db_session.execute(
                select(QueryHistory).order_by(QueryHistory.id.desc())
            )
            entries = result.scalars().all()
            return [
                QueryResponse(
                    result=entry.result,
                    sources=json.loads(entry.sources)
                )
                for entry in entries
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/index")
    async def index(background_tasks: BackgroundTasks):
        try:
            # On-demand indexing via endpoint
            background_tasks.add_task(app.state.indexer.index_documents)
            return {"message": "Indexing started in the background"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app

app = create_app()
