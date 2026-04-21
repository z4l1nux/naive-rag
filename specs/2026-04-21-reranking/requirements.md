# Requirements — Re-ranking pós-retrieval

Decisões de design para a Fase 4. A seção "Spike" será preenchida com os números reais após o Passo 0.

---

## Contexto e motivação

O retrieval atual retorna `top_k` chunks por **similaridade cosseno entre embeddings** (bi-encoder). Bi-encoders são rápidos mas produzem scores aproximados: o embedding da query e o embedding do chunk são gerados independentemente, sem atenção cruzada entre eles.

Um **cross-encoder** recebe o par `(query, chunk)` concatenado e produz um score de relevância com atenção full sobre os dois textos. É mais lento, mas significativamente mais preciso para discriminar qual chunk responde melhor à pergunta.

O padrão clássico é: bi-encoder busca `top_n` candidatos rápidos → cross-encoder reranqueia para `top_k` finais. `top_n` tipicamente 3–5× maior que `top_k`.

---

## Spike — critérios de decisão

**Ollama foi descartado como backend de reranking.** O Ollama não tem API de rerank nativa. O workaround documentado (gerar embedding de `query + chunk` concatenados e usar heurísticas de magnitude vetorial) não é um cross-encoder real — o próprio autor admite ser uma "simplified approach". Não produz scores de relevância confiáveis.

As duas candidatas reais são `sentence-transformers` (in-process) e `llama-server /rerank` (HTTP local).

A escolha entre elas será guiada por:

| Critério | Peso |
|----------|------|
| Latência por par (query, chunk) em CPU | Alto |
| Sem nova infraestrutura de servidor | Médio |
| Tamanho de imagem Docker resultante | Médio |
| Facilidade de troca de modelo | Baixo |

**Threshold de aceitação:** latência total de reranking (para `top_n=10`) abaixo de 2s em CPU para não degradar a experiência de streaming.

> **Decisão:** `sentence-transformers` com `cross-encoder/ms-marco-MiniLM-L-6-v2`.
> `llama-server /rerank` foi descartado por ser endpoint experimental — requer verificação de versão e download de GGUF adicional, sem vantagem prática para uso educacional local.
> `sentence-transformers` entrega cross-encoder real em ~5 linhas, modelo de ~85MB, zero servidor extra.

---

## Posição do reranker no pipeline

O reranker se insere entre `find_similar()` e a montagem do contexto em `src/rag.py`. Isso é deliberado:

- Não afeta o banco de dados — nenhuma mudança em schema ou queries
- Não afeta embeddings — o modelo de embedding continua sendo o mesmo
- É completamente opcional: `enabled=False` retorna o pipeline original intacto

Quando desativado, `top_n` não é usado — a query ao pgvector é feita diretamente com `top_k` (comportamento atual preservado).

---

## Parâmetros `top_n` e `top_k`

- `top_n` (entrada do reranker) — quantos candidatos o pgvector retorna para o cross-encoder avaliar. Padrão: `10`.
- `top_k` (saída do reranker) — quantos chunks entram no contexto final. Padrão: `3` (mesmo valor atual).
- Invariante: `top_n > top_k`. A API retorna 422 se violado.
- Aumentar `top_n` eleva latência do reranker linearmente. Aumentar `top_k` eleva o tamanho do contexto e o custo de geração.

---

## Estado em memória

Mesmo padrão de `backend.py` e `turboquant.py`:

- `threading.Lock()` para thread safety
- Estado resetado ao reiniciar o servidor (comportamento esperado para laboratório)
- Sem persistência — configuração de sessão de experimento

---

## Métricas e evento SSE

O evento `{"type": "reranker", ...}` é emitido **após** `sources` no stream SSE. O cliente pode ignorar se não estiver exibindo métricas. Isso mantém retrocompatibilidade com clientes que só consomem `token` e `sources`.

Os campos de métricas capturados por inferência:
- `rank_before` / `rank_after` por doc — para visualizar quanto cada chunk subiu ou desceu
- `score_cross_encoder` — score bruto do modelo
- `latency_ms` — tempo total do passo de reranking (todos os pares)

---

## O que não entra neste PR

- **Busca híbrida** (pgvector + tsvector) — backlog, escopo separado
- **Fine-tuning do cross-encoder** — fora do escopo educacional
- **Múltiplos modelos de reranker simultâneos** — uma única configuração ativa por vez
- **Persistência de métricas** — ring buffer em memória (50 registros), sem banco
