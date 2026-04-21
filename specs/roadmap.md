# Roadmap

## Fase 1 — Core RAG ✅

Pipeline mínimo funcional: pergunta → embedding → busca vetorial → geração.

- ✅ Script educacional (`rag.py` na raiz) com embeddings em memória
- ✅ Notebook passo a passo (`rag.ipynb`)
- ✅ Chunking com recursive character splitter (`src/chunker.py`)
- ✅ Cliente Ollama async para embeddings (`src/embeddings.py`)
- ✅ PostgreSQL + pgvector com índice HNSW (`src/db.py`)
- ✅ Pipeline RAG com streaming SSE (`src/rag.py`)
- ✅ API FastAPI com endpoint `/api/query` (`src/main.py`)
- ✅ Frontend vanilla HTML/CSS/JS (`public/`)
- ✅ Docker Compose (API + PostgreSQL)

## Fase 2 — Ingestão de arquivos ✅

Suporte a upload de documentos reais com controle de chunking.

- ✅ Parsers para PDF, DOCX, MD, TXT (`src/parsers.py`)
- ✅ Endpoint `POST /api/upload` com `chunkSize` e `overlap` configuráveis
- ✅ CRUD de documentos avulsos (`POST/GET/DELETE /api/documents`)
- ✅ Gestão de arquivos por `source_file` (`GET/DELETE /api/documents/files`)
- ✅ Migração automática de schema (`ALTER TABLE ADD COLUMN IF NOT EXISTS`)

## Fase 3 — Backends alternativos e quantização ✅

Suporte a llama.cpp com quantização real da KV Cache.

- ✅ Abstração de backend (`src/backend.py`) — Ollama | llama.cpp
- ✅ Cliente HTTP async para llama.cpp via `httpx` (`src/rag.py`)
- ✅ TurboQuant: estado, métricas e fórmula de memória KV (`src/turboquant.py`)
  - ✅ Modo standard (8-bit): ~50% de redução de memória
  - ✅ Modo aggressive (3-bit TQ): ~73% de redução de memória
- ✅ API de configuração e métricas TurboQuant (`/api/turboquant/*`)
- ✅ API de alternância de backend (`/api/backend/config`)

## Fase 4 — Qualidade de retrieval ✅

Melhorar a precisão das respostas com um segundo passo de reranking.

- ✅ **Re-ranking pós-retrieval** — `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers`, aplicado entre `find_similar()` e montagem do contexto (`src/reranker.py`)
- ✅ Endpoint de configuração do reranker (`GET/POST /api/reranker/config` com validação `top_n > top_k`)
- ✅ Métricas comparativas: latência, rank_changes e avg_rank_improvement (`GET /api/reranker/metrics`)
- ✅ Evento SSE `{"type": "reranker"}` emitido após `sources` quando ativo
- ✅ Painel Reranker no frontend — toggle, top-N/top-K configuráveis, cards de latência/candidatos/melhoria, badges ↑/↓/= por fonte
- ✅ System prompt melhorado — permite inferência quando o contexto descreve algo indiretamente
- ✅ TurboQuant Aggressive corrigido — removido `num_keep=5` que truncava prompts desnecessariamente

## Backlog (sem prioridade definida)

- [ ] Avaliação automática de qualidade RAG (faithfulness, answer relevancy, context recall)
- [ ] Parsers adicionais: Excel (`.xlsx`), HTML, imagens com OCR
- [ ] Busca híbrida: vetorial + full-text (pgvector + `tsvector`)
