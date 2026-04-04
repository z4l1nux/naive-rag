import json
import os
from collections.abc import AsyncGenerator

from .db import find_similar
from .embeddings import client, get_embedding

TEXT_MODEL = os.getenv("TEXT_MODEL", "gemma4:e2b")

_SYSTEM_PROMPT = (
    "Voce e um assistente especialista. Responda usando apenas as informacoes do contexto "
    "fornecido. Se a resposta nao estiver no contexto, informe que nao possui essa informacao."
)


async def rag_stream(question: str, top_k: int = 3) -> AsyncGenerator[str, None]:
    """
    Yields SSE-formatted lines: `data: <json>\\n\\n`

    Events:
      {"type": "token",   "content": "..."}   — one per LLM token
      {"type": "sources", "sources": [...]}    — sent once at the end
      {"type": "error",   "message": "..."}    — on failure
    """
    try:
        query_embedding = await get_embedding(question)
        docs = find_similar(query_embedding, top_k)

        if not docs:
            yield _event({"type": "token", "content": "Nenhum documento encontrado na base de conhecimento."})
            yield _event({"type": "sources", "sources": []})
            return

        context = "\n\n".join(d["content"] for d in docs)

        stream = await client.chat(
            model=TEXT_MODEL,
            stream=True,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Contexto:\n{context}\n\nPergunta: {question}"},
            ],
        )

        async for part in stream:
            content = part.message.content
            if content:
                yield _event({"type": "token", "content": content})

        # Serialize datetime to string for JSON
        sources = [
            {
                "id": d["id"],
                "content": d["content"],
                "source_file": d["source_file"],
                "similarity": float(d["similarity"]),
            }
            for d in docs
        ]
        yield _event({"type": "sources", "sources": sources})

    except Exception as exc:
        yield _event({"type": "error", "message": str(exc)})


def _event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
