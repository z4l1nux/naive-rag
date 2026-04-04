from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..rag import rag_stream

router = APIRouter()


class QueryIn(BaseModel):
    question: str
    topK: int = 3


@router.post("")
async def query(body: QueryIn):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    return StreamingResponse(
        rag_stream(body.question.strip(), body.topK),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
