# Arquitetura

## Visao geral

```
                        ┌─────────────┐
                        │   Browser   │
                        └──────┬──────┘
                               │ HTTP / SSE
                        ┌──────▼──────┐
                        │  FastAPI     │  :3000
                        │  (uvicorn)  │
                        └──┬───┬───┬──┘
                           │   │   │
              ┌────────────┘   │   └────────────┐
              │                │                │
       ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
       │  PostgreSQL  │  │    Ollama   │  │   public/   │
       │  + pgvector  │  │  (host)     │  │  (static)   │
       └─────────────┘  └─────────────┘  └─────────────┘
```

O Ollama roda no host (fora do Docker). O container da API o acessa via `host.docker.internal`.

---

## Modulos do backend

### `src/main.py` — servidor

Ponto de entrada. Usa o `lifespan` do FastAPI para inicializar o banco antes de aceitar requisicoes. Monta as rotas de API e serve os arquivos estaticos do frontend via `StaticFiles`.

As rotas de API sao registradas **antes** do `StaticFiles`, garantindo que `/api/*` nunca seja interceptado pelos arquivos estaticos.

### `src/db.py` — banco de dados

Gerencia toda a comunicacao com o PostgreSQL via `psycopg2`. Responsabilidades:
- Cria a extensao `vector`, a tabela e o indice HNSW na inicializacao (usando `autocommit` para DDL)
- Executa migracao automatica (`ALTER TABLE ADD COLUMN IF NOT EXISTS`)
- Seleciona entre `vector` e `halfvec` com base em `EMBEDDING_DIM`
- Expoe um `ThreadedConnectionPool` via context manager `get_db()`
- Exporta funcoes tipadas: `insert_document`, `list_documents`, `list_files`, `find_similar`, etc.

### `src/embeddings.py` — cliente Ollama

Instancia o `AsyncClient` do ollama com o host configurado via `OLLAMA_HOST`. Exporta `get_embedding(text)` e o proprio `client` para uso na geracao de texto.

### `src/rag.py` — pipeline RAG

Orquestra as duas etapas como um `AsyncGenerator` que produz linhas SSE prontas para envio:

```
rag_stream(question)
   │
   ├─ get_embedding(question)         ← embedding da pergunta (async)
   ├─ find_similar(embedding, top_k)  ← busca no pgvector (sync, threadpool)
   ├─ client.chat(stream=True)        ← geracao com streaming (async)
   │
   ├─ yield "data: {token}\\n\\n"         ← um token por vez
   └─ yield "data: {sources}\\n\\n"       ← fontes ao final
```

O `StreamingResponse` do FastAPI itera diretamente sobre esse generator, transmitindo cada linha para o cliente assim que ela e produzida.

### `src/chunker.py` — divisor de texto

Recursive character text splitter identico em logica ao do projeto TypeScript. Testa separadores em cascata: `\n\n` > `\n` > `. ` > ` `.

Detalhes em [chunking.md](chunking.md).

### `src/parsers.py` — extracao de texto

| Extensao | Biblioteca | Observacao |
|----------|-----------|------------|
| `.pdf` | `pypdf` | Extrai texto de todas as paginas |
| `.docx` | `python-docx` | Extrai paragrafos como texto bruto |
| `.md` | — | Lido como UTF-8 |
| `.txt` | — | Lido como UTF-8 |

### `src/routes/documents.py` — CRUD

```
GET    /api/documents                   documentos avulsos (source_file IS NULL)
POST   /api/documents                   cria documento + embedding
DELETE /api/documents/{id}              remove por id
GET    /api/documents/files             agrupa por source_file com contagem de chunks
DELETE /api/documents/files/{filename}  remove todos os chunks de um arquivo
```

### `src/routes/upload.py` — ingestao de arquivos

Recebe `multipart/form-data` com `UploadFile` e os campos `chunkSize` e `overlap` via `Form`. Processa os chunks **sequencialmente** para nao sobrecarregar o Ollama.

### `src/routes/query.py` — consulta RAG

Recebe `{ question, topK }` e retorna um `StreamingResponse` com `media_type="text/event-stream"`. O header `X-Accel-Buffering: no` desativa o buffering do nginx se houver um proxy reverso na frente.

---

## Schema do banco

```sql
CREATE TABLE documents (
  id          SERIAL PRIMARY KEY,
  content     TEXT NOT NULL,
  embedding   vector(768),        -- ou halfvec(N) se EMBEDDING_DIM > 2000
  source_file TEXT,               -- NULL para documentos avulsos
  chunk_index INTEGER,            -- posicao do chunk dentro do arquivo
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX documents_embedding_hnsw_idx
ON documents USING hnsw (embedding vector_cosine_ops);
```

---

## Fluxo de dados: upload de arquivo

```
Browser              FastAPI              Ollama        PostgreSQL
   │                    │                    │               │
   │── POST /upload ───►│                    │               │
   │   (multipart)      │── extract_text() ──► parsers       │
   │                    │◄─ raw_text ─────────               │
   │                    │── chunk_text() ────► chunker        │
   │                    │◄─ chunks[] ─────────               │
   │                    │                    │               │
   │                    │  para cada chunk:  │               │
   │                    │── get_embedding() ►│               │
   │                    │◄─ vector[] ────────│               │
   │                    │── INSERT ──────────────────────────►│
   │                    │◄─ ok ───────────────────────────────│
   │                    │                    │               │
   │◄── {source,chunks} │                    │               │
```

## Fluxo de dados: consulta RAG

```
Browser              FastAPI              Ollama        PostgreSQL
   │                    │                    │               │
   │── POST /query ─────►│                    │               │
   │                    │── get_embedding() ─►│               │
   │                    │◄─ queryVector[] ────│               │
   │                    │── SELECT ... ORDER BY <=> ─────────►│
   │                    │◄─ top-K chunks ──────────────────────│
   │                    │                    │               │
   │                    │── chat(stream) ────►│               │
   │◄── data:{token} ───│◄─ token... ─────────│               │
   │◄── data:{token} ───│◄─ token... ─────────│               │
   │◄── data:{sources} ─│  (stream encerrado) │               │
```

---

## Diferenca entre `src/rag.py` e `rag.py`

| Arquivo | Proposito |
|---------|-----------|
| `rag.py` (raiz) | Script educacional — mostra o conceito de RAG com embeddings em memoria, sem banco |
| `src/rag.py` | Pipeline de producao — usa pgvector, streaming SSE, cliente async |

---

## Decisoes de design

**Por que FastAPI e nao Flask?**
FastAPI tem suporte nativo a async/await, validacao via Pydantic, e `StreamingResponse` que aceita generators assincronos diretamente.

**Por que psycopg2 (sync) e nao asyncpg?**
O `psycopg2` e o driver mais estavel e documentado para PostgreSQL em Python. O FastAPI roda chamadas sincronas em um threadpool automaticamente. Para este workload (queries de banco simples), a diferenca de performance e negligivel.

**Por que SSE e nao WebSocket?**
SSE e unidirecional (servidor → cliente), mais simples, funciona sobre HTTP e e suficiente para streaming de texto.

**Por que chunks sequenciais no upload?**
O Ollama e single-thread por padrao. Requisicoes paralelas ficam na fila de qualquer forma — sequencial e mais previsivel e evita timeouts.

**Por que HNSW e nao IVFFlat?**
IVFFlat exige pre-treinamento e degrada em datasets pequenos. HNSW funciona bem desde o primeiro documento.
