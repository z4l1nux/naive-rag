# API Reference

Base URL: `http://localhost:3001`

---

## Documentos

### `GET /api/documents`

Retorna todos os documentos adicionados manualmente (sem `source_file`).

**Resposta `200`**

```json
[
  {
    "id": 1,
    "content": "Machine learning e um campo da inteligencia artificial...",
    "source_file": null,
    "chunk_index": null,
    "created_at": "2026-04-04T21:00:00.000Z"
  }
]
```

---

### `POST /api/documents`

Adiciona um documento de texto. Gera o embedding automaticamente.

**Body `application/json`**

```json
{ "content": "Texto do documento..." }
```

**Resposta `201`**

```json
{
  "id": 2,
  "content": "Texto do documento...",
  "source_file": null,
  "chunk_index": null,
  "created_at": "2026-04-04T21:00:00.000Z"
}
```

**Erros**

| Status | Motivo |
|--------|--------|
| `400` | `content` ausente ou vazio |
| `500` | Falha no embedding ou no banco |

---

### `DELETE /api/documents/:id`

Remove um documento pelo id.

**Resposta `204`** — sem corpo.

**Erros**

| Status | Motivo |
|--------|--------|
| `400` | `id` nao e um numero valido |
| `404` | Documento nao encontrado |

---

## Arquivos importados

### `GET /api/documents/files`

Retorna os arquivos importados agrupados por `source_file`, com a contagem de chunks.

**Resposta `200`**

```json
[
  {
    "source_file": "relatorio-anual.pdf",
    "chunk_count": 47,
    "created_at": "2026-04-04T21:30:00.000Z"
  },
  {
    "source_file": "manual-tecnico.docx",
    "chunk_count": 12,
    "created_at": "2026-04-04T20:00:00.000Z"
  }
]
```

---

### `DELETE /api/documents/files/:filename`

Remove todos os chunks de um arquivo importado.

**Parametro de rota:** `filename` deve ser URL-encoded se contiver espacos ou caracteres especiais.

```bash
# exemplo
curl -X DELETE "http://localhost:3001/api/documents/files/relatorio%20anual.pdf"
```

**Resposta `200`**

```json
{ "deleted": 47 }
```

**Erros**

| Status | Motivo |
|--------|--------|
| `404` | Arquivo nao encontrado |

---

## Upload de arquivo

### `POST /api/upload`

Importa um arquivo, divide em chunks, gera embeddings e armazena tudo no banco.

**Body `multipart/form-data`**

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `file` | File | Sim | Arquivo a importar (PDF, DOCX, MD, TXT) |
| `chunkSize` | string | Nao | Tamanho maximo do chunk em caracteres (padrao: `1000`) |
| `overlap` | string | Nao | Overlap entre chunks em caracteres (padrao: `150`) |

```bash
# exemplo com curl
curl -X POST http://localhost:3001/api/upload \
  -F "file=@/caminho/para/documento.pdf" \
  -F "chunkSize=800" \
  -F "overlap=100"
```

**Resposta `200`**

```json
{
  "source": "documento.pdf",
  "chunks": 23
}
```

**Erros**

| Status | Motivo |
|--------|--------|
| `400` | Nenhum arquivo enviado |
| `400` | Extensao nao suportada |
| `400` | Nenhum texto encontrado no arquivo |
| `500` | Falha no parsing, embedding ou banco |

**Extensoes suportadas:** `.pdf`, `.docx`, `.md`, `.txt`

**Limite de tamanho:** 20 MB por arquivo.

---

## Consulta RAG

### `POST /api/query`

Realiza uma consulta RAG. A resposta e transmitida em tempo real via **Server-Sent Events** (SSE).

**Body `application/json`**

```json
{
  "question": "O que e machine learning?",
  "topK": 3
}
```

| Campo | Tipo | Padrao | Descricao |
|-------|------|--------|-----------|
| `question` | string | — | Pergunta do usuario |
| `topK` | number | `3` | Quantos chunks usar como contexto |

**Headers da resposta**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

**Formato dos eventos SSE**

Cada evento segue o formato `data: <json>\n\n`.

**Evento `token`** — enviado para cada fragmento de texto gerado:

```
data: {"type":"token","content":"Machine "}

data: {"type":"token","content":"learning "}

data: {"type":"token","content":"e um..."}
```

**Evento `sources`** — enviado uma vez ao final, com as fontes consultadas (ja rerankeadas se o reranker estiver ativo):

```
data: {"type":"sources","sources":[
  {"id":1,"content":"Machine learning e...","source_file":"manual.pdf","similarity":0.9231},
  {"id":5,"content":"O aprendizado pode...","source_file":null,"similarity":0.8714},
  {"id":3,"content":"Aplicacoes incluem...","source_file":"manual.pdf","similarity":0.8012}
]}
```

**Evento `reranker`** — enviado apos `sources` quando o reranker esta habilitado:

```
data: {"type":"reranker",
  "record": {
    "query": "O que e machine learning?",
    "latency_ms": 412.3,
    "num_candidates": 10,
    "top_k": 3,
    "rank_changes": [
      {"id": 3, "from": 5, "to": 0},
      {"id": 1, "from": 1, "to": 1}
    ],
    "avg_rank_improvement": 3.5
  },
  "summary": {
    "count": 1,
    "avg_latency_ms": 412.3,
    "avg_rank_improvement": 3.5
  }
}
```

**Evento `metrics`** — enviado ao final com metricas de performance TurboQuant:

```
data: {"type":"metrics",
  "record": {
    "mode": "aggressive",
    "total_ms": 4210.5,
    "tokens_per_sec": 17.4,
    "prompt_eval_ms": 348.1,
    "kv_bytes": 12345678,
    "memory_reduction": 73.1
  },
  "summary": { "off": {...}, "standard": {...}, "aggressive": {...} }
}
```

**Evento `error`** — enviado em caso de falha:

```
data: {"type":"error","message":"connection refused"}
```

### Consumindo o stream em JavaScript

```javascript
const res = await fetch("/api/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ question: "O que e RAG?", topK: 3 }),
});

const reader  = res.body.getReader();
const decoder = new TextDecoder();
let buffer = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split("\n");
  buffer = lines.pop(); // guarda linha incompleta para a proxima iteracao

  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    const event = JSON.parse(line.slice(6));

    if (event.type === "token")    console.log(event.content);
    if (event.type === "sources")  console.log("Fontes:", event.sources);
    if (event.type === "reranker") console.log("Reranker:", event.record);
    if (event.type === "metrics")  console.log("TurboQuant:", event.record);
    if (event.type === "error")    console.error(event.message);
  }
}
```

### Consumindo o stream com curl

```bash
curl -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question":"O que e machine learning?","topK":3}'
```

**Erros**

| Status | Motivo |
|--------|--------|
| `400` | `question` ausente ou vazio |

---

---

## Reranker

### `GET /api/reranker/config`

Retorna a configuracao atual do reranker.

**Resposta `200`**

```json
{ "enabled": false, "top_n": 10, "top_k": 3 }
```

---

### `POST /api/reranker/config`

Atualiza a configuracao do reranker.

**Body `application/json`**

```json
{ "enabled": true, "top_n": 10, "top_k": 3 }
```

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `enabled` | boolean | Liga/desliga o reranker |
| `top_n` | integer | Candidatos buscados no pgvector (deve ser > `top_k`) |
| `top_k` | integer | Chunks finais passados ao LLM |

**Erros**

| Status | Motivo |
|--------|--------|
| `422` | `top_n` <= `top_k` |

---

### `GET /api/reranker/metrics`

Retorna o historico de metricas do reranker (ultimas 50 inferencias, ring buffer).

**Resposta `200`**

```json
[
  {
    "query": "O que e machine learning?",
    "latency_ms": 412.3,
    "num_candidates": 10,
    "top_k": 3,
    "rank_changes": [{"id": 3, "from": 5, "to": 0}],
    "avg_rank_improvement": 3.5
  }
]
```

---

## TurboQuant KV Cache

### `GET /api/turboquant/config`

Retorna a configuracao atual do TurboQuant.

**Resposta `200`**

```json
{ "enabled": false, "mode": "off" }
```

---

### `POST /api/turboquant/config`

**Body `application/json`**

```json
{ "enabled": true, "mode": "standard" }
```

`mode` aceita: `"off"`, `"standard"` (8-bit, ~50% reducao), `"aggressive"` (3-bit, ~73% reducao).

---

### `GET /api/turboquant/metrics`

Retorna o historico de metricas TurboQuant (ultimas 50 inferencias).

---

## Backend

### `GET /api/backend/config`

Retorna o backend ativo.

**Resposta `200`**

```json
{ "backend": "ollama" }
```

---

### `POST /api/backend/config`

Alterna o backend de geracao de texto.

**Body `application/json`**

```json
{ "backend": "llamacpp" }
```

`backend` aceita: `"ollama"` ou `"llamacpp"`. Embeddings sempre via Ollama independente do backend ativo.

---

## Codigos de erro comuns

| Codigo | Significado |
|--------|-------------|
| `400 Bad Request` | Parametro obrigatorio ausente ou invalido |
| `404 Not Found` | Recurso nao encontrado |
| `500 Internal Server Error` | Falha no Ollama, no banco ou no parser |

Todos os erros retornam `application/json` com o campo `error`:

```json
{ "error": "descricao do problema" }
```
