# Conceitos RAG

## O que e RAG?

**RAG** = Retrieval-Augmented Generation (Geracao com Recuperacao Aumentada).

Um LLM treinado sozinho tem dois problemas estruturais:

| Problema | O que acontece |
|----------|----------------|
| Conhecimento congelado | O modelo nao sabe o que aconteceu apos o treino |
| Alucinacao | Inventa respostas plausíveis mas factualmente erradas |

O RAG resolve os dois ao dar ao modelo uma **base de conhecimento consultavel em tempo real**. Em vez de depender do que "memorizou", o modelo primeiro **busca** os trechos mais relevantes e so entao **gera** a resposta, fundamentado neles.

```
Sem RAG:   Pergunta ──► LLM ──► Resposta (pode alucinar)

Com RAG:   Pergunta ──► Busca na base ──► LLM + Contexto ──► Resposta fundamentada
```

---

## O pipeline em duas fases

### Fase 1 — Indexacao (feita uma vez)

```
Documento de texto
       │
       ▼
Modelo de Embedding     ← converte texto em vetor numerico
       │
       ▼
pgvector (PostgreSQL)   ← armazena o vetor com indice HNSW
```

Cada documento (ou chunk de documento) e convertido em um vetor e armazenado. Isso e feito uma unica vez por documento.

### Fase 2 — Consulta (feita a cada pergunta)

```
Pergunta do usuario
       │
       ▼
Embedding da pergunta   ← mesmo modelo usado na indexacao
       │
       ▼
Busca por similaridade  ← operador <=> do pgvector (distancia de cosseno)
       │
       ▼
Top-K chunks mais proximos
       │
       ▼
LLM recebe: contexto + pergunta
       │
       ▼
Resposta fundamentada
```

**Resumindo em tres verbos:** Encode → Retrieve → Generate.

---

## O que sao Embeddings?

Um **embedding** e uma representacao numerica do significado de um texto — uma lista de numeros (vetor) onde cada numero captura algum aspecto semantico.

Textos com significados parecidos produzem vetores numericamente proximos. Textos diferentes produzem vetores distantes.

```
"cao" e "cachorro"     → vetores com angulo ~5° (muito proximos)
"cao" e "futebol"      → vetores com angulo ~85° (sem relacao)
"amor" e "odio"        → vetores com angulo ~150° (sentidos opostos)
```

Na pratica os vetores tem centenas de dimensoes (este projeto usa 768), mas a ideia e a mesma: **proximidade no espaco = similaridade de significado**.

### Como o Ollama gera embeddings neste projeto

```python
# src/embeddings.py
res = ollama.embeddings(model="embeddinggemma:latest", prompt=text)
# res["embedding"] = [0.023, -0.415, 0.887, 0.102, ...]  ← 768 numeros
```

O modelo le o texto e produz um vetor de 768 dimensoes. Esse vetor e armazenado na coluna `embedding vector(768)` do PostgreSQL.

---

## Similaridade de Cosseno

Para comparar dois textos, comparamos seus vetores. A metrica usada e a **similaridade de cosseno**.

### Formula

```
cos(θ) = (A · B) / (‖A‖ × ‖B‖)
```

Onde:
- `A · B` = produto escalar: `A[0]×B[0] + A[1]×B[1] + ... + A[n]×B[n]`
- `‖A‖` = norma (comprimento) do vetor A: `√(A[0]² + A[1]² + ...)`

### Interpretacao

| Angulo | cos(θ) | Significado |
|--------|--------|-------------|
| θ ≈ 0° | → 1 | Vetores quase paralelos — textos muito similares |
| θ = 90° | → 0 | Vetores ortogonais — sem relacao semantica |
| θ ≈ 180° | → -1 | Vetores opostos — sentidos contrarios |

### Exemplo numerico em Python

```python
import math

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot   = sum(ai * bi for ai, bi in zip(a, b))
    norm_a = math.sqrt(sum(ai * ai for ai in a))
    norm_b = math.sqrt(sum(bi * bi for bi in b))
    return dot / (norm_a * norm_b)

v1 = [1, 2, 3]
v2 = [4, 5, 6]
# dot = 1×4 + 2×5 + 3×6 = 32
# norm_a = √14 ≈ 3.742  |  norm_b = √77 ≈ 8.775
# similaridade = 32 / (3.742 × 8.775) ≈ 0.974  ← muito similares
```

### Por que cosseno e nao distancia euclidiana?

O cosseno mede o **angulo** entre vetores, nao o comprimento. Um texto curto e um texto longo sobre o mesmo assunto tem o mesmo angulo mas comprimentos diferentes — o cosseno os reconhece como similares corretamente.

### No pgvector

O operador `<=>` calcula a **distancia** de cosseno (1 − similaridade). Por isso a query usa `1 - (embedding <=> $1::vector)` para transformar distancia em similaridade:

```sql
SELECT content,
       ROUND((1 - (embedding <=> $1::vector))::numeric, 4) AS similarity
FROM documents
ORDER BY embedding <=> $1::vector   -- ordena por distancia (menor = mais similar)
LIMIT 3;
```

---

## HNSW — o indice vetorial

Este projeto usa um indice **HNSW** (Hierarchical Navigable Small World) no pgvector:

```sql
CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops);
```

HNSW organiza os vetores em um grafo hierarquico de multiplas camadas. A busca navega do nivel mais alto (poucas conexoes, saltos longos) ate o nivel mais baixo (muitas conexoes, precisao alta), encontrando os vizinhos mais proximos sem precisar comparar com todos os documentos.

| Caracteristica | Valor |
|---------------|-------|
| Complexidade de busca | O(log n) |
| Limite de dimensoes (`vector`) | 2000 |
| Limite de dimensoes (`halfvec`) | 4000 |
| Ideal para | datasets de qualquer tamanho |

> Este projeto usa `vector` para dimensoes <= 2000 e `halfvec` para dimensoes > 2000, automaticamente, com base na variavel `EMBEDDING_DIM`.

---

## Leituras complementares

- [Arquitetura do projeto](architecture.md) — como os modulos se conectam
- [Chunking](chunking.md) — por que e como dividir documentos em pedacos menores
- [API](api.md) — endpoints disponíveis
