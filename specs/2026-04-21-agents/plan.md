# Plan — naive-rag (retroativo)

Registro das tarefas concluídas, derivado do estado atual do código.

---

## Fase 1 — Core RAG

- [x] Script educacional mínimo `rag.py` (raiz) — pipeline com embeddings em memória, sem banco
- [x] Notebook `rag.ipynb` — versão explorável passo a passo do mesmo script
- [x] `src/embeddings.py` — `AsyncClient` Ollama, expõe `get_embedding(text)` e `client`
- [x] `src/db.py` — `init_db()` com DDL idempotente, `ThreadedConnectionPool`, `find_similar()` com distância cosseno via operador `<=>`
- [x] `src/chunker.py` — recursive character text splitter; separadores em cascata `\n\n > \n > ". " > " "`; sobreposição de contexto entre chunks
- [x] `src/rag.py` — `rag_stream()` como `AsyncGenerator` produzindo linhas SSE: tokens, fontes e métricas
- [x] `src/routes/query.py` — `POST /api/query` com `StreamingResponse` e headers anti-buffering
- [x] `src/main.py` — FastAPI com `lifespan` para `init_db()`, rotas montadas antes do `StaticFiles`
- [x] `public/` — frontend vanilla (HTML + CSS + JS) servido como arquivos estáticos
- [x] `docker-compose.yml` + `Dockerfile` — API e PostgreSQL em containers; Ollama no host

## Fase 2 — Ingestão de arquivos

- [x] `src/parsers.py` — `extract_text()` para PDF (`pypdf`), DOCX (`python-docx`), MD, TXT; `validate_file()` com lista de extensões suportadas; lazy import das bibliotecas pesadas
- [x] `src/routes/upload.py` — `POST /api/upload` multipart; limite de 20 MB; `chunkSize` e `overlap` via `Form`; ingestão sequencial de chunks
- [x] `src/routes/documents.py` — CRUD completo: `POST/GET/DELETE /api/documents` (docs avulsos) + `GET/DELETE /api/documents/files` (por `source_file`)
- [x] `src/db.py` — migração automática não-destrutiva: `ALTER TABLE ADD COLUMN IF NOT EXISTS source_file TEXT` e `chunk_index INTEGER`
- [x] `src/db.py` — `list_files()` agrupado por `source_file` com contagem de chunks; `delete_file()` em lote

## Fase 3 — Backends alternativos e TurboQuant

- [x] `src/backend.py` — estado de backend em memória (`ollama | llamacpp`), thread-safe com `threading.Lock`
- [x] `src/rag.py` — branch llama.cpp via `httpx.AsyncClient` streamando da API OpenAI-compatible do `llama-server`; coleta de `usage` no chunk final para métricas
- [x] `src/turboquant.py` — estado de modo (`off | standard | aggressive`), fórmula de memória KV (`tokens × 2 × hidden_dim × layers × bpv`), ring buffer de 50 métricas, `get_summary()` com médias por modo
- [x] `src/main.py` — endpoints `GET/POST /api/turboquant/config`, `GET /api/turboquant/metrics`, `GET/POST /api/backend/config`
- [x] `src/db.py` — suporte a `halfvec` automático para `EMBEDDING_DIM > 2000` (ops class e cast type ajustados)
- [x] `docs/turboquant.md` — documentação da fórmula, modos, endpoints e como iniciar o llama-server
