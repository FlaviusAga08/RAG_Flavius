from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from domain.models import QueryRequest, QueryResponse
from application.indexer import DocumentIndexer
import os
from dotenv import load_dotenv
from infrastructure.watcher import start_directory_watcher
from fastapi import Depends
from infrastructure.database import Database
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio

load_dotenv()
db = Database()

api_key = os.getenv("OPENAI_API_KEY")
doc_location = os.getenv("LOCATION")
persist_directory = "db"

indexer = DocumentIndexer(doc_location=doc_location, persist_directory=persist_directory, api_key=api_key)
indexer.load_vector_db()

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    await db.create_tables()
    indexer.load_vector_db()
    start_directory_watcher(path=doc_location, indexer=indexer)



@app.post("/query", response_model=list[QueryResponse])
async def query(
    request: QueryRequest,
    top_k: int = Query(5, ge=1, le=20),
    db_session: AsyncSession = Depends(db.get_db),
):
    try:
        responses = await indexer.query(request.query, top_k=top_k)
        await db.save_query(db_session, request.query, responses[0].result, responses[0].sources)
        return responses
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index")
async def trigger_index():
    asyncio.create_task(indexer.index_documents())
    return {"message": "Indexing started"}