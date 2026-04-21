# Plan — Fase 4: Re-ranking pós-retrieval

Entrega completa conforme roadmap: spike de tecnologia → lógica de reranking → config API → métricas comparativas.

---

## Passo 0 — Spike de tecnologia

Antes de qualquer código de produção, validar as duas abordagens candidatas.

- [ ] **Spike A — `sentence-transformers`**
  - Instalar `sentence-transformers` em ambiente isolado (`uv add --dev`)
  - Carregar `cross-encoder/ms-marco-MiniLM-L-6-v2` (~85MB)
  - Medir: latência por par (query, chunk) em CPU, footprint de memória, tamanho de imagem Docker

- [ ] **Spike B — `llama-server /rerank`**
  - Verificar se a versão atual do llama.cpp tem endpoint `POST /rerank`
  - Baixar um modelo cross-encoder em GGUF (ex.: `ms-marco-MiniLM-L-6-v2.gguf`)
  - Medir: latência por par, overhead de rede vs. in-process, API contract

- [ ] **Decisão documentada** — registrar em `requirements.md` qual abordagem foi escolhida e por quê, com os números do spike.

---

## Passo 1 — Módulo de reranking

- [ ] `src/reranker.py` — estado, configuração e função de scoring
  - Estado em memória: `{"enabled": false, "top_n": 10, "top_k": 3}` (thread-safe, padrão `backend.py`)
  - `get_config() → dict`
  - `set_config(enabled, top_n, top_k) → dict`
  - `rerank(query: str, docs: list[dict], top_k: int) → list[dict]` — recebe os `top_n` do pgvector, devolve `top_k` reordenados por score cross-encoder; retorna `docs` inalterado se `enabled=False`

---

## Passo 2 — Integração no pipeline RAG

- [ ] `src/rag.py` — inserir chamada ao reranker entre `find_similar()` e a montagem do contexto
  ```
  docs = find_similar(query_embedding, top_n)   # top_n aumentado
  docs = reranker.rerank(question, docs, top_k)  # reduz para top_k
  context = "\n\n".join(d["content"] for d in docs)
  ```
- [ ] `src/db.py` — nenhuma mudança (a query já aceita `top_k` variável via `LIMIT %s`)

---

## Passo 3 — Config API

- [ ] `src/main.py` — três endpoints novos:
  - `GET  /api/reranker/config` — retorna estado atual
  - `POST /api/reranker/config` — altera `enabled`, `top_n`, `top_k`
  - Validação: `top_n > top_k`, ambos positivos; valores inválidos retornam 422

---

## Passo 4 — Métricas comparativas

- [ ] `src/reranker.py` — `record_metric(query, docs_before, docs_after, latency_ms) → dict`
  - Captura: posição de cada doc antes e depois do reranking, delta de score, latência
  - Ring buffer de 50 registros (mesmo padrão do `turboquant.py`)

- [ ] `src/main.py` — endpoint `GET /api/reranker/metrics`
  - Retorna `{"records": [...], "summary": {"avg_latency_ms": ..., "avg_rank_delta": ...}}`

- [ ] `src/rag.py` — emitir evento SSE `{"type": "reranker", "record": {...}}` após o evento `sources`, quando reranker estiver ativo

---

## Passo 5 — Documentação

- [ ] `docs/reranking.md` — conceito de cross-encoder vs. bi-encoder, parâmetros `top_n`/`top_k`, como iniciar o modelo, exemplos de comparação com/sem reranker
- [ ] `README.md` — adicionar linha na tabela de stack e endpoint na seção de API
- [ ] `specs/tech-stack.md` — adicionar reranker na tabela principal, remover da tabela de lacunas
- [ ] `specs/roadmap.md` — marcar itens da Fase 4 como ✅
