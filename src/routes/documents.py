from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..db import (
    delete_document,
    delete_file,
    insert_document,
    list_documents,
    list_files,
)
from ..embeddings import get_embedding

router = APIRouter()


class DocumentIn(BaseModel):
    content: str


@router.get("")
async def get_documents():
    return list_documents()


@router.post("", status_code=201)
async def create_document(body: DocumentIn):
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="content is required")
    embedding = await get_embedding(body.content.strip())
    return insert_document(body.content.strip(), embedding)


@router.delete("/{doc_id}", status_code=204)
async def remove_document(doc_id: int):
    if not delete_document(doc_id):
        raise HTTPException(status_code=404, detail="document not found")


# ── File groups ──────────────────────────────────────────────────────

@router.get("/files")
async def get_files():
    return list_files()


@router.delete("/files/{filename}", status_code=200)
async def remove_file(filename: str):
    count = delete_file(filename)
    if count == 0:
        raise HTTPException(status_code=404, detail="file not found")
    return {"deleted": count}
