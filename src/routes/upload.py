from fastapi import APIRouter, HTTPException, UploadFile, Form

from ..chunker import chunk_text
from ..db import insert_document
from ..embeddings import get_embedding
from ..parsers import extract_text, validate_file

router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("")
async def upload(
    file: UploadFile,
    chunkSize: int = Form(default=1000),
    overlap: int = Form(default=150),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    try:
        validate_file(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    data = await file.read()

    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo excede o limite de 20 MB.")

    try:
        raw_text = await extract_text(data, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao extrair texto: {exc}")

    chunks = chunk_text(raw_text, size=chunkSize, overlap=overlap)

    if not chunks:
        raise HTTPException(status_code=400, detail="Nenhum conteudo de texto encontrado no arquivo.")

    try:
        for i, chunk in enumerate(chunks):
            embedding = await get_embedding(chunk)
            insert_document(chunk, embedding, file.filename, i)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao indexar: {exc}")

    return {"source": file.filename, "chunks": len(chunks)}
