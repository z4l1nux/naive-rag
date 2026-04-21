import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from .db import init_db
from .routes.documents import router as documents_router
from .routes.query import router as query_router
from .routes.upload import router as upload_router
from . import turboquant
from . import backend as backend_mod
from . import reranker as reranker_mod

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


# ── TurboQuant API ────────────────────────────────────────────────────────────

class TurboQuantConfigRequest(BaseModel):
    enabled: bool
    mode: str   # "off" | "standard" | "aggressive"


@app.get("/api/turboquant/config")
def tq_get_config():
    """Return current TurboQuant enabled state and mode."""
    return turboquant.get_config()


@app.post("/api/turboquant/config")
def tq_set_config(req: TurboQuantConfigRequest):
    """Enable/disable TurboQuant and set compression mode."""
    valid = {"off", "standard", "aggressive"}
    mode  = req.mode if req.mode in valid else "off"
    return turboquant.set_config(req.enabled, mode)


@app.get("/api/turboquant/metrics")
def tq_get_metrics():
    """Return the last 50 inference metrics records plus per-mode averages."""
    return {
        "records": turboquant.get_metrics(),
        "summary": turboquant.get_summary(),
    }


# ── Backend API ───────────────────────────────────────────────────────────────

class BackendConfigRequest(BaseModel):
    backend: str   # "ollama" | "llamacpp"


@app.get("/api/backend/config")
def backend_get_config():
    """Return current inference backend and llama.cpp connection info."""
    cfg = backend_mod.get_config()
    cfg["llamacpp_host"]  = backend_mod.LLAMACPP_HOST
    cfg["llamacpp_model"] = backend_mod.LLAMACPP_MODEL
    return cfg


@app.post("/api/backend/config")
def backend_set_config(req: BackendConfigRequest):
    """Switch inference backend between 'ollama' and 'llamacpp'."""
    cfg = backend_mod.set_config(req.backend)
    cfg["llamacpp_host"]  = backend_mod.LLAMACPP_HOST
    cfg["llamacpp_model"] = backend_mod.LLAMACPP_MODEL
    return cfg


# ── Reranker API ──────────────────────────────────────────────────────────────

class RerankerConfigRequest(BaseModel):
    enabled: bool
    top_n: int = 10
    top_k: int = 3


@app.get("/api/reranker/config")
def reranker_get_config():
    """Return current reranker state (enabled, top_n, top_k)."""
    return reranker_mod.get_config()


@app.post("/api/reranker/config")
def reranker_set_config(req: RerankerConfigRequest):
    """Enable/disable cross-encoder reranking and set top_n / top_k."""
    if req.top_n <= req.top_k:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="top_n must be greater than top_k")
    if req.top_n < 1 or req.top_k < 1:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="top_n and top_k must be positive")
    return reranker_mod.set_config(req.enabled, req.top_n, req.top_k)


@app.get("/api/reranker/metrics")
def reranker_get_metrics():
    """Return the last 50 reranking records plus aggregate summary."""
    return {
        "records": reranker_mod.get_metrics(),
        "summary": reranker_mod.get_summary(),
    }


app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")
