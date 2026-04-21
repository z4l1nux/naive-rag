# Changelog

## 2026-04-21

### Fase 4 — Re-ranking e melhorias de qualidade

- feat: adicionar `src/reranker.py` — cross-encoder `ms-marco-MiniLM-L-6-v2` com lazy-load, top-N/top-K configuráveis, métricas de latência e rank_changes
- feat: integrar reranker no pipeline RAG — busca top-N candidatos, reranqueia via executor async, emite evento SSE `{"type":"reranker"}` após `sources`
- feat: endpoints `GET/POST /api/reranker/config` e `GET /api/reranker/metrics` em `src/main.py`
- feat: painel Reranker no frontend — toggle habilitado/desabilitado, inputs top-N/top-K, cards de latência/candidatos/melhoria, badges de rank delta nas fontes
- fix: mover `sentence-transformers` para dependências principais em `pyproject.toml` (era grupo dev — não instalado no Docker)
- fix: remover `num_keep=5` do modo TurboQuant Aggressive (`src/turboquant.py`) — causava truncamento de prompt sem benefício real neste workload
- fix: melhorar system prompt em `src/rag.py` para permitir inferência quando o contexto descreve algo indiretamente

## 2026-04-15
- chore: change logic

## 2026-04-11
- fix: add llama.cpp
- feat: add turboQuant

## 2026-04-07
- fix: change example rag code

## 2026-04-04
- chore: implement chunk

## 2026-04-03
- fix: change mermaid
- fix: mermaid
- chore: melhorias de angulos
- chore: add readme.md
- feat: Implementando um RAG do zero em Python
