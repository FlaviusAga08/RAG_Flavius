from fastapi import FastAPI, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from domain.models import QueryRequest, QueryResponse
from application.indexer import DocumentIndexer
import os
from dotenv import load_dotenv

import asyncio

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
doc_location = os.getenv("LOCATION")
persist_directory = "db"

indexer = DocumentIndexer(doc_location=doc_location, persist_directory=persist_directory, api_key=api_key)
indexer.load_vector_db()

app = FastAPI()

@app.on_event("startup")
def startup_event():
    indexer.load_vector_db()


@app.post("/query", response_model=list[QueryResponse])
async def query(request: QueryRequest, top_k: int = Query(5, ge=1, le=20)):
    try:
        return await indexer.query(request.query, top_k=top_k)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/index")
async def trigger_index():
    asyncio.create_task(indexer.index_documents())
    return {"message": "Indexing started"}
