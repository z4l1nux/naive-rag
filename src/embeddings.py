import os

from ollama import AsyncClient

client = AsyncClient(host=os.getenv("OLLAMA_HOST", "http://localhost:11434"))

EMBED_MODEL = os.getenv("EMBED_MODEL", "embeddinggemma:latest")


async def get_embedding(text: str) -> list[float]:
    res = await client.embeddings(model=EMBED_MODEL, prompt=text)
    return res.embedding
