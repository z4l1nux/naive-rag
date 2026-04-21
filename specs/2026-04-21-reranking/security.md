---
spec: 2026-04-21-reranking
type: security
---

# Security — Re-ranking pós-retrieval

Análise de superfície de ataque e riscos introduzidos pela Fase 4 (reranker).

---

## Entry Points novos (Fase 4)

| Entry point | Método | Dado recebido | Risco |
|-------------|--------|---------------|-------|
| `POST /api/reranker/config` | JSON body | `enabled`, `top_n`, `top_k` | Estado compartilhado sem autenticação |
| `GET /api/reranker/metrics` | — | — | Exposição de histórico de queries (conteúdo de perguntas) |

---

## LLM10 — Unbounded Consumption ampliado

**Risco:** Com reranker ativo, `top_n` determina quantos candidatos o pgvector retorna. Um cliente pode configurar `top_n=50` (máximo da UI), inflando o custo de retrieval e o tempo de inferência do cross-encoder linearmente.

**Mitigação existente:** Validação `top_n > top_k` (retorna 422 se violado). Sem cap máximo absoluto de `top_n`.

**Mitigação recomendada:** Adicionar `MAX_TOP_N = 50` e `MAX_TOP_K = 20` no servidor, independente do que o cliente enviar.

**Status:** ⚠️ Parcialmente mitigado.

---

## Exposição de histórico via `/api/reranker/metrics`

**Risco:** `GET /api/reranker/metrics` retorna as últimas 50 queries com seu conteúdo textual (`query` field). Em um ambiente com múltiplos usuários, isso expõe perguntas de outros usuários.

**Localização:** `src/reranker.py` — `_record_metric()` armazena `query` no ring buffer.

**Status:** ⚠️ Aberto — aceito para uso educacional single-tenant. Em multi-usuário, exigiria autenticação no endpoint ou remoção do campo `query` das métricas.

---

## Cross-encoder — modelo de ML não validado

**Risco:** `cross-encoder/ms-marco-MiniLM-L-6-v2` é baixado do Hugging Face na primeira execução. Sem verificação de hash/checksum. Um modelo substituído (supply chain) poderia executar código arbitrário via `sentence_transformers`.

**Status:** ⚠️ Risco de supply chain — aceito para projeto educacional local. Em produção: pinning de versão do modelo + verificação de hash.

---

## Lazy-load e bloqueio de thread

**Risco:** O lazy-load do modelo na primeira query bloqueia o thread executor por ~5s enquanto carrega ~85 MB. Não é um risco de segurança direto, mas pode ser usado para DoS coordenado (forçar recarga do modelo via restart + queries simultâneas).

**Status:** ℹ️ Baixo risco — aceito.

---

## Ausência de autenticação (herdado)

Os endpoints de configuração do reranker herdam o mesmo modelo sem autenticação do pipeline principal. Ver `specs/2026-04-21-agents/security.md`.

**Status:** ⚠️ Aceito — projeto educacional.
