import json
import os
from collections.abc import AsyncGenerator

from .db import find_similar
from .embeddings import client, get_embedding
from . import turboquant

TEXT_MODEL = os.getenv("TEXT_MODEL", "gemma4:latest")

_SYSTEM_PROMPT = (
    "Voce e um assistente especialista. Responda usando apenas as informacoes do contexto "
    "fornecido. Se a resposta nao estiver no contexto, informe que nao possui essa informacao."
)


async def rag_stream(question: str, top_k: int = 3) -> AsyncGenerator[str, None]:
    """
    Yields SSE-formatted lines: `data: <json>\\n\\n`

    Events:
      {"type": "token",   "content": "..."}    — one per LLM token
      {"type": "sources", "sources": [...]}     — sent once after tokens
      {"type": "metrics", "record": {...},
                          "summary": {...}}      — TurboQuant perf data
      {"type": "error",   "message": "..."}     — on failure
    """
    try:
        query_embedding = await get_embedding(question)
        docs = find_similar(query_embedding, top_k)

        if not docs:
            yield _event({"type": "token", "content": "Nenhum documento encontrado na base de conhecimento."})
            yield _event({"type": "sources", "sources": []})
            return

        context = "\n\n".join(d["content"] for d in docs)

        # Snapshot TurboQuant mode before the call to avoid TOCTOU mislabelling
        tq_options    = turboquant.get_options()
        tq_mode_snap  = turboquant.get_config()["mode"]

        chat_kwargs: dict = {
            "model":    TEXT_MODEL,
            "stream":   True,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": f"Contexto:\n{context}\n\nPergunta: {question}"},
            ],
        }
        # Only inject options when TQ is active — baseline calls are untouched
        if tq_options:
            chat_kwargs["options"] = tq_options

        stream = await client.chat(**chat_kwargs)

        last_part = None
        async for part in stream:
            content = part.message.content
            if content:
                yield _event({"type": "token", "content": content})
            last_part = part  # keep last chunk — it carries timing fields when done=True

        # Emit sources
        sources = [
            {
                "id":          d["id"],
                "content":     d["content"],
                "source_file": d["source_file"],
                "similarity":  float(d["similarity"]),
            }
            for d in docs
        ]
        yield _event({"type": "sources", "sources": sources})

        # Emit TurboQuant metrics (always, even when TQ is off — baseline data is useful)
        if last_part is not None:
            ollama_data = {
                "total_duration":       last_part.total_duration,
                "load_duration":        last_part.load_duration,
                "prompt_eval_count":    last_part.prompt_eval_count,
                "prompt_eval_duration": last_part.prompt_eval_duration,
                "eval_count":           last_part.eval_count,
                "eval_duration":        last_part.eval_duration,
            }
            record  = turboquant.record_metric(ollama_data, tq_mode_snap)
            summary = turboquant.get_summary()
            yield _event({"type": "metrics", "record": record, "summary": summary})

    except Exception as exc:
        yield _event({"type": "error", "message": str(exc)})


def _event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
