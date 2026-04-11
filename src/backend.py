"""
backend.py — inference backend selection: Ollama vs llama.cpp server.

Ollama  : cliente async atual, TurboQuant via num_ctx/num_batch (aproximacao).
llamacpp: llama-server com API OpenAI-compativel; KV cache quantization real
          configurada no startup via --cache-type-k / --cache-type-v.

Embeddings SEMPRE via Ollama independente do backend de texto selecionado.
Estado em memoria, resetado ao reiniciar (comportamento esperado).
"""
from __future__ import annotations

import os
import threading

_lock  = threading.Lock()
_state: dict = {"backend": "ollama"}

LLAMACPP_HOST  = os.getenv("LLAMACPP_HOST",  "http://localhost:8080")
LLAMACPP_MODEL = os.getenv("LLAMACPP_MODEL", "gemma-3-12b")


def get_config() -> dict:
    with _lock:
        return dict(_state)


def set_config(backend: str) -> dict:
    with _lock:
        _state["backend"] = backend if backend in {"ollama", "llamacpp"} else "ollama"
        return dict(_state)
