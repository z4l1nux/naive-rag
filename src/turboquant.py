"""
turboquant.py — TurboQuant KV Cache optimisation: state, options, metrics.

Implements the TurboQuant concept (Google ICLR 2026) as an Ollama approximation:
  - Standard  (8-bit):      num_ctx=4096, num_batch=256          → ~50% mem reduction
  - Aggressive (3-bit TQ):  num_ctx=4096, num_batch=512, keep=5  → ~73% mem reduction

KV memory formula (Gemma 3 12B):
  tokens × 2 × hidden_dim × layers × bytes_per_value
  FP16=2.0 | 8-bit=1.0 | 3-bit≈0.375

State is in-memory and process-scoped. Resets on restart (expected for demo).
"""
from __future__ import annotations

import time
import threading
from collections import deque

# ── Global state (thread-safe) ───────────────────────────────────────────────

_lock     = threading.Lock()
_state: dict  = {"enabled": False, "mode": "off"}
_metrics: deque = deque(maxlen=50)   # ring buffer — no memory leak

# ── Memory formula constants — Gemma 3 12B architecture ─────────────────────
# tokens × 2 × hidden_dim × layers × bytes_per_value
#   ×2         : separate K and V tensors
#   hidden_dim : head_dim(256) × num_kv_heads(8) = 2048  [n_embd_k_gqa]
#   layers     : 48 transformer layers (8 non-SWA global + 40 SWA sliding)

HIDDEN_DIM = 2048
LAYERS     = 48
BYTES_FP16 = 2.0
BYTES_8BIT = 1.0
BYTES_3BIT = 0.375   # TurboQuant: 3 bits / 8 bits per byte


def _kv_bytes(tokens: int, bpv: float) -> int:
    return int(tokens * 2 * HIDDEN_DIM * LAYERS * bpv)


# ── Public API ───────────────────────────────────────────────────────────────

def get_config() -> dict:
    with _lock:
        return dict(_state)


def set_config(enabled: bool, mode: str) -> dict:
    with _lock:
        _state["enabled"] = enabled
        _state["mode"]    = mode if enabled else "off"
        return dict(_state)


def get_options() -> dict:
    """Return Ollama options dict for the current mode.
    Returns empty dict when TQ is off → Ollama uses its defaults.
    """
    with _lock:
        mode = _state["mode"]

    if mode == "standard":
        return {"num_ctx": 4096, "num_batch": 256}
    elif mode == "aggressive":
        return {"num_ctx": 4096, "num_batch": 512}
    return {}


def record_metric(ollama_data: dict, mode_snapshot: str) -> dict:
    """Compute and store one metric record. Returns the stored record.

    ollama_data must be a plain dict with Ollama timing fields (nanoseconds):
      total_duration, load_duration, prompt_eval_count, prompt_eval_duration,
      eval_count, eval_duration
    """
    prompt_tokens  = ollama_data.get("prompt_eval_count", 0) or 0
    gen_tokens     = ollama_data.get("eval_count", 0) or 0
    total_tokens   = prompt_tokens + gen_tokens

    total_ns       = ollama_data.get("total_duration", 0) or 0
    load_ns        = ollama_data.get("load_duration", 0) or 0
    prompt_eval_ns = ollama_data.get("prompt_eval_duration", 0) or 0
    eval_ns        = ollama_data.get("eval_duration", 0) or 0

    tokens_per_sec = (gen_tokens / (eval_ns / 1e9)) if eval_ns > 0 else 0.0

    bpv_map       = {"off": BYTES_FP16, "standard": BYTES_8BIT, "aggressive": BYTES_3BIT}
    bpv           = bpv_map.get(mode_snapshot, BYTES_FP16)
    kv_bytes      = _kv_bytes(total_tokens, bpv)
    kv_bytes_fp16 = _kv_bytes(total_tokens, BYTES_FP16)
    mem_reduction = 1.0 - (kv_bytes / kv_bytes_fp16) if kv_bytes_fp16 > 0 else 0.0

    record = {
        "ts":               time.time(),
        "mode":             mode_snapshot,
        "prompt_tokens":    prompt_tokens,
        "gen_tokens":       gen_tokens,
        "total_tokens":     total_tokens,
        "total_ms":         round(total_ns       / 1e6, 1),
        "load_ms":          round(load_ns        / 1e6, 1),
        "prompt_eval_ms":   round(prompt_eval_ns / 1e6, 1),
        "eval_ms":          round(eval_ns        / 1e6, 1),
        "tokens_per_sec":   round(tokens_per_sec, 2),
        "kv_bytes":         kv_bytes,
        "kv_bytes_fp16":    kv_bytes_fp16,
        "memory_reduction": round(mem_reduction * 100, 1),
    }

    with _lock:
        _metrics.append(record)

    return record


def get_metrics() -> list:
    with _lock:
        return list(_metrics)


def get_summary() -> dict:
    """Compute per-mode averages over stored records."""
    with _lock:
        records = list(_metrics)

    def avg(lst: list) -> float:
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    def summarise(recs: list) -> dict | None:
        if not recs:
            return None
        return {
            "count":                len(recs),
            "avg_total_ms":         avg([r["total_ms"]          for r in recs]),
            "avg_tokens_per_sec":   avg([r["tokens_per_sec"]    for r in recs]),
            "avg_memory_reduction": avg([r["memory_reduction"]  for r in recs]),
            "avg_kv_bytes":         avg([r["kv_bytes"]          for r in recs]),
            "avg_kv_bytes_fp16":    avg([r["kv_bytes_fp16"]     for r in recs]),
        }

    return {
        "off":        summarise([r for r in records if r["mode"] == "off"]),
        "standard":   summarise([r for r in records if r["mode"] == "standard"]),
        "aggressive": summarise([r for r in records if r["mode"] == "aggressive"]),
    }
