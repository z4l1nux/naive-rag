import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .db import init_db
from .routes.documents import router as documents_router
from .routes.query import router as query_router
from .routes.upload import router as upload_router

BASE_DIR = Path(__file__).parent.parent
PUBLIC_DIR = BASE_DIR / "public"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("Database ready.")
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(documents_router, prefix="/api/documents")
app.include_router(query_router,     prefix="/api/query")
app.include_router(upload_router,    prefix="/api/upload")

app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")
