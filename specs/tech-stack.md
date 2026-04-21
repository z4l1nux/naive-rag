# Tech Stack

## Stack atual

| Camada | Tecnologia | Decisão |
|--------|-----------|---------|
| Runtime | Python 3.12 + `uv` | uv para gestão rápida de dependências e ambientes |
| API | FastAPI + uvicorn | Async nativo, `StreamingResponse` para SSE, validação Pydantic |
| Banco vetorial | PostgreSQL 17 + pgvector (HNSW) | HNSW funciona bem desde o 1º documento, sem pré-treinamento |
| Embeddings | Ollama (`embeddinggemma:latest`, 768 dims) | Sempre via Ollama — zero configuração adicional |
| Geração de texto | Ollama (`gemma4:latest`) | Backend padrão, zero configuração |
| Geração de texto (alt) | llama.cpp / `llama-server` (GGUF) | Habilita quantização real da KV Cache |
| KV Cache | TurboQuant (8-bit standard / 3-bit aggressive) | Implementação própria baseada em Google ICLR 2026 |
| Containers | Docker Compose | PostgreSQL em container; Ollama/llama.cpp no host |
| Parsers | `pypdf`, `python-docx` | PDF e DOCX; MD e TXT lidos como UTF-8 puro |
| HTTP client | `httpx` (async) | Streaming para llama.cpp; `psycopg2` para PostgreSQL |
| Chunking | Recursive character splitter (próprio) | Sem dependências externas; lógica em `src/chunker.py` |
| Re-ranking | `sentence-transformers` (`cross-encoder/ms-marco-MiniLM-L-6-v2`) | Cross-encoder local; lazy-load no primeiro uso; on/off via API |
| Frontend | HTML + CSS + JS vanilla | Sem framework — mantém o foco no backend |

## Decisões de design notáveis

**Por que psycopg2 (sync) em vez de asyncpg?**
Driver mais estável e documentado. O FastAPI delega chamadas síncronas a um threadpool. Para este workload a diferença é negligível.

**Por que SSE em vez de WebSocket?**
SSE é unidirecional e suficiente para streaming de texto. Mais simples, funciona sobre HTTP padrão.

**Por que `halfvec` condicional?**
pgvector suporta `vector` até 2000 dims. Modelos maiores (ex.: `nomic-embed-text`, 1536 dims) cabem em `vector`; modelos com > 2000 dims usam `halfvec` automaticamente via `EMBEDDING_DIM`.

## Lacunas conhecidas

| Lacuna | Impacto | Status |
|--------|---------|--------|
| ~~Re-ranking~~ | Implementado — `src/reranker.py` | ✅ Fase 4 |
| Avaliação RAG | Sem métricas automáticas de qualidade (faithfulness, relevancy, recall) | Backlog |
| Parsers adicionais | Sem suporte a Excel, HTML, imagens com OCR | Backlog |
| Busca híbrida | Sem combinação de busca vetorial + full-text (BM25/tsvector) | Não planejado |
| Multi-coleção | Todos os documentos compartilham o mesmo namespace vetorial | Não planejado |
