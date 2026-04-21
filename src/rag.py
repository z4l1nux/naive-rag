import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator

import httpx

from .db import find_similar
from .embeddings import client, get_embedding
from . import turboquant
from . import backend as backend_mod
from . import reranker as reranker_mod

TEXT_MODEL    = os.getenv("TEXT_MODEL",    "gemma4:latest")
LLAMACPP_HOST = backend_mod.LLAMACPP_HOST
LLAMACPP_MODEL = backend_mod.LLAMACPP_MODEL

_SYSTEM_PROMPT = (
    "Voce e um assistente especialista em RAG. Use o contexto fornecido como fonte principal. "
    "Quando o contexto mencionar conceitos, termos ou descricoes que correspondam ao que foi "
    "perguntado — mesmo que indiretamente — interprete e responda com base nessa informacao. "
    "Apenas informe que nao possui a informacao se o contexto for genuinamente irrelevante para "
    "a pergunta."
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
        # Fetch top_n candidates when reranker is active, top_k otherwise
        docs = find_similar(query_embedding, reranker_mod.get_top_n(top_k))
        docs = await asyncio.get_event_loop().run_in_executor(
            None, reranker_mod.rerank, question, docs
        )

        if not docs:
            yield _event({"type": "token", "content": "Nenhum documento encontrado na base de conhecimento."})
            yield _event({"type": "sources", "sources": []})
            return

        context = "\n\n".join(d["content"] for d in docs)

        # Snapshot TurboQuant mode before the call
        tq_options   = turboquant.get_options()
        tq_mode_snap = turboquant.get_config()["mode"]

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": f"Contexto:\n{context}\n\nPergunta: {question}"},
        ]

        current_backend = backend_mod.get_config()["backend"]
        ollama_data = None

        # ── llama.cpp backend ─────────────────────────────────────────────
        if current_backend == "llamacpp":
            t_start = time.time_ns()
            prompt_tokens = 0
            gen_tokens    = 0

            try:
                async with httpx.AsyncClient(timeout=180.0) as http:
                    async with http.stream(
                        "POST",
                        f"{LLAMACPP_HOST}/v1/chat/completions",
                        json={
                            "model":    LLAMACPP_MODEL,
                            "messages": messages,
                            "stream":   True,
                        },
                    ) as resp:
                        async for line in resp.aiter_lines():
                            line = line.strip()
                            if not line or line == "data: [DONE]":
                                continue
                            if not line.startswith("data: "):
                                continue
                            try:
                                chunk = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue

                            delta   = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                gen_tokens += 1
                                yield _event({"type": "token", "content": content})

                            # final chunk may carry usage stats
                            usage = chunk.get("usage")
                            if usage:
                                prompt_tokens = usage.get("prompt_tokens",     0)
                                gen_tokens    = usage.get("completion_tokens", gen_tokens)

            except httpx.ConnectError:
                yield _event({
                    "type":    "error",
                    "message": f"llama.cpp server nao encontrado em {LLAMACPP_HOST}. "
                               "Inicie o servidor antes de usar este backend.",
                })
                return

            total_ns = time.time_ns() - t_start
            ollama_data = {
                "total_duration":       total_ns,
                "load_duration":        0,
                "prompt_eval_count":    prompt_tokens,
                "prompt_eval_duration": 0,
                "eval_count":           gen_tokens,
                "eval_duration":        total_ns,  # aproximacao: sem separacao de prefill
            }

        # ── Ollama backend (padrao) ────────────────────────────────────────
        else:
            chat_kwargs: dict = {
                "model":    TEXT_MODEL,
                "stream":   True,
                "messages": messages,
            }
            if tq_options:
                chat_kwargs["options"] = tq_options

            stream = await client.chat(**chat_kwargs)

            last_part = None
            async for part in stream:
                content = part.message.content
                if content:
                    yield _event({"type": "token", "content": content})
                last_part = part

            if last_part is not None:
                ollama_data = {
                    "total_duration":       last_part.total_duration,
                    "load_duration":        last_part.load_duration,
                    "prompt_eval_count":    last_part.prompt_eval_count,
                    "prompt_eval_duration": last_part.prompt_eval_duration,
                    "eval_count":           last_part.eval_count,
                    "eval_duration":        last_part.eval_duration,
                }

        # ── Fontes ────────────────────────────────────────────────────────
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

        # ── Metricas Reranker ─────────────────────────────────────────────
        if reranker_mod.is_enabled():
            rr_metrics = reranker_mod.get_metrics()
            if rr_metrics:
                yield _event({
                    "type":    "reranker",
                    "record":  rr_metrics[-1],
                    "summary": reranker_mod.get_summary(),
                })

        # ── Metricas TurboQuant ───────────────────────────────────────────
        if ollama_data is not None:
            record  = turboquant.record_metric(ollama_data, tq_mode_snap)
            summary = turboquant.get_summary()
            yield _event({"type": "metrics", "record": record, "summary": summary})

    except Exception as exc:
        yield _event({"type": "error", "message": str(exc)})


def _event(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
