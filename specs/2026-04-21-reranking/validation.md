# Validation — Re-ranking pós-retrieval

Smoke tests para verificar que o reranker funciona corretamente e não regride o pipeline existente.

---

## Pré-requisitos

```bash
# Stack no ar com reranker configurado
docker compose up --build -d
# Aguardar "Database ready." nos logs

# Pelo menos 5 documentos indexados com conteúdo variado
# (necessário para top_n=10 ter candidatos suficientes)
```

---

## 1. Estado inicial (desativado por padrão)

```bash
curl -s http://localhost:3001/api/reranker/config | python3 -m json.tool
# Esperado:
# {
#   "enabled": false,
#   "top_n": 10,
#   "top_k": 3
# }
```

---

## 2. Ativar o reranker

```bash
curl -s -X POST http://localhost:3001/api/reranker/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "top_n": 10, "top_k": 3}' \
  | python3 -m json.tool
# Esperado: {"enabled": true, "top_n": 10, "top_k": 3}
```

---

## 3. Validação de invariante top_n > top_k

```bash
curl -s -X POST http://localhost:3001/api/reranker/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "top_n": 2, "top_k": 5}'
# Esperado: HTTP 422 com mensagem de erro descritiva
```

---

## 4. Query com reranker ativo — verificar evento SSE

```bash
curl -s -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "O que é pgvector?", "topK": 3}'
# Esperado: sequência de eventos SSE:
#   data: {"type": "token", ...}          (múltiplos)
#   data: {"type": "sources", ...}        (top_k docs rerankeados)
#   data: {"type": "reranker", "record": {"latency_ms": ..., ...}}
#   data: {"type": "metrics", ...}        (TurboQuant, se ativo)
```

Verificar que `sources` contém exatamente `top_k` (3) documentos.

---

## 5. Comparação de ranking com e sem reranker

```bash
# Sem reranker
curl -s -X POST http://localhost:3001/api/reranker/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "top_n": 10, "top_k": 3}'

curl -s -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "sua pergunta de teste"}' \
  | grep '"type":"sources"' | python3 -m json.tool

# Com reranker
curl -s -X POST http://localhost:3001/api/reranker/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "top_n": 10, "top_k": 3}'

curl -s -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "sua pergunta de teste"}' \
  | grep '"type":"sources"' | python3 -m json.tool
```

Comparar os `id` e `similarity` dos docs em cada resposta. Com reranker ativo, a ordem deve diferir da similaridade cosseno pura.

---

## 6. Métricas de reranking

```bash
# Após pelo menos 1 query com reranker ativo:
curl -s http://localhost:3001/api/reranker/metrics | python3 -m json.tool
# Esperado:
# {
#   "records": [{"latency_ms": ..., "rank_before": [...], "rank_after": [...], ...}],
#   "summary": {"avg_latency_ms": ..., "avg_rank_delta": ...}
# }
```

---

## 7. Regressão — pipeline sem reranker deve ser idêntico ao anterior

```bash
curl -s -X POST http://localhost:3001/api/reranker/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "top_n": 10, "top_k": 3}'

curl -s -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "O que é pgvector?", "topK": 3}'
# Esperado: SEM evento {"type": "reranker"} no stream
# Demais eventos (token, sources, metrics) devem funcionar normalmente
```

---

## 8. Benchmark de latência (spike)

Script para medir latência do reranker isolada, a ser usado no Passo 0 do plan:

```python
import time
# sentence-transformers
from sentence_transformers import CrossEncoder
model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

query = "O que é pgvector?"
chunks = ["chunk de teste " * 50] * 10  # simula top_n=10

start = time.perf_counter()
pairs = [(query, c) for c in chunks]
scores = model.predict(pairs)
elapsed = (time.perf_counter() - start) * 1000
print(f"sentence-transformers: {elapsed:.1f}ms para {len(chunks)} pares")
```

**Threshold de aceitação:** < 2000ms em CPU para `top_n=10`.

---

## Cleanup

```bash
# Desativar reranker após testes
curl -s -X POST http://localhost:3001/api/reranker/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "top_n": 10, "top_k": 3}'
```

---

## Indicadores de falha

| Sintoma | Causa provável |
|---------|---------------|
| Evento `reranker` ausente com `enabled=true` | `reranker.rerank()` não está sendo chamado em `src/rag.py` |
| `sources` com mais de `top_k` docs | `reranker.rerank()` não está truncando corretamente |
| `sources` com `top_n` docs (sem redução) | Reranker ativo mas retornando lista original sem corte |
| Latência total > 5s com reranker | `top_n` muito alto ou modelo não carregado em GPU |
| HTTP 500 na primeira query com reranker | Modelo não encontrado ou `sentence-transformers` não instalado |
| Invariante `top_n > top_k` não retorna 422 | Validação ausente em `POST /api/reranker/config` |
