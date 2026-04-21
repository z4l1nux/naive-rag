"""
reranker.py — cross-encoder reranking using sentence-transformers.

Takes the top-N candidates from pgvector (bi-encoder) and reorders them
by a cross-encoder score, returning the top-K most relevant documents.

The cross-encoder reads (query, chunk) jointly — full attention across
both texts — producing more accurate relevance scores than cosine similarity.

State is in-memory and process-scoped. Resets on restart (expected for lab use).
"""
from __future__ import annotations

import time
import threading
from collections import deque

_lock = threading.Lock()
_state: dict = {"enabled": False, "top_n": 10, "top_k": 3}
_metrics: deque = deque(maxlen=50)

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model = None  # lazy-loaded on first rerank call


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder(_MODEL_NAME)
    return _model


# ── Public API ────────────────────────────────────────────────────────────────

def get_config() -> dict:
    with _lock:
        return dict(_state)


def set_config(enabled: bool, top_n: int, top_k: int) -> dict:
    with _lock:
        _state["enabled"] = enabled
        _state["top_n"] = top_n
        _state["top_k"] = top_k
        return dict(_state)


def get_top_n(fallback: int = 3) -> int:
    """Candidates to fetch from pgvector.
    When enabled: top_n (wider net for reranker).
    When disabled: caller's top_k (original behaviour).
    """
    with _lock:
        return _state["top_n"] if _state["enabled"] else fallback


def is_enabled() -> bool:
    with _lock:
        return _state["enabled"]


def rerank(query: str, docs: list[dict]) -> list[dict]:
    """Score and reorder docs by cross-encoder relevance.

    Returns top_k docs sorted by descending score.
    Returns docs unchanged (original cosine order) if disabled.
    """
    with _lock:
        enabled = _state["enabled"]
        top_k = _state["top_k"]

    if not enabled or not docs:
        return docs

    model = _load_model()

    t0 = time.perf_counter()
    pairs = [(query, d["content"]) for d in docs]
    scores = model.predict(pairs).tolist()
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    scored = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)
    reranked = [d for _, d in scored[:top_k]]

    _record_metric(query, docs, reranked, scores, latency_ms)
    return reranked


# ── Metrics ───────────────────────────────────────────────────────────────────

def _record_metric(
    query: str,
    docs_before: list[dict],
    docs_after: list[dict],
    scores: list[float],
    latency_ms: float,
) -> None:
    ids_before = [d["id"] for d in docs_before]
    ids_after = [d["id"] for d in docs_after]

    rank_changes = []
    for new_rank, doc in enumerate(docs_after):
        old_rank = ids_before.index(doc["id"]) if doc["id"] in ids_before else -1
        rank_changes.append({"id": doc["id"], "from": old_rank, "to": new_rank})

    record = {
        "ts": time.time(),
        "query": query[:120],
        "n_candidates": len(docs_before),
        "n_selected": len(docs_after),
        "latency_ms": latency_ms,
        "scores": [round(s, 4) for s in scores],
        "rank_changes": rank_changes,
    }
    with _lock:
        _metrics.append(record)


def get_metrics() -> list:
    with _lock:
        return list(_metrics)


def get_summary() -> dict:
    with _lock:
        records = list(_metrics)
    if not records:
        return {}

    avg_lat = round(sum(r["latency_ms"] for r in records) / len(records), 1)

    deltas = []
    for r in records:
        for rc in r["rank_changes"]:
            if rc["from"] >= 0:
                deltas.append(rc["from"] - rc["to"])
    avg_delta = round(sum(deltas) / len(deltas), 2) if deltas else 0.0

    return {
        "count": len(records),
        "avg_latency_ms": avg_lat,
        "avg_rank_improvement": avg_delta,
    }
