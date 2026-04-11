# RAG com pgvector e Python

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white">
  <img src="https://img.shields.io/badge/pgvector-pg17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">
  <img src="https://img.shields.io/badge/Ollama-Local%20LLM-FF6600?style=for-the-badge">
  <img src="https://img.shields.io/badge/llama.cpp-GGUF-8B5CF6?style=for-the-badge">
</p>

Pipeline RAG (Retrieval-Augmented Generation) completo com banco de dados vetorial, API REST com streaming e interface web. Roda inteiramente local — sem nenhuma API externa paga.

Suporta dois backends de inferencia: **Ollama** (padrao, zero configuracao) e **llama.cpp** com quantizacao real da KV Cache via `--cache-type-k/v`.

> `rag.py` e `rag.ipynb` na raiz sao o material educacional original que deu origem a este projeto. A aplicacao web vive em `src/`.

---

## Quick start

### 1. Iniciar o Ollama

O Ollama deve estar rodando no host antes de subir os containers:

```bash
# Instalar (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Iniciar o servidor (deixe em terminal separado)
ollama serve

# Baixar os modelos necessarios
ollama pull embeddinggemma:latest   # embeddings (768 dims)
ollama pull gemma4:latest           # geracao de texto
```

### 2. Subir a aplicacao

```bash
git clone <url>
cd naive-rag
docker compose up --build
```

Acesse `http://localhost:3001`. Adicione documentos ou importe arquivos e faca perguntas.

> Para usar o backend llama.cpp com quantizacao real da KV Cache, veja [docs/turboquant.md](docs/turboquant.md).

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Runtime | Python 3.12 + uv |
| API | FastAPI + uvicorn com StreamingResponse (SSE) |
| Banco vetorial | PostgreSQL 17 + pgvector (HNSW) |
| Embeddings | Ollama (`embeddinggemma:latest`, 768 dims) |
| Gerador de texto | Ollama (`gemma4:latest`) ou llama.cpp (GGUF) |
| Containers | Docker Compose |
| Parsers de arquivo | `pypdf`, `python-docx` |
| HTTP client | `httpx` (streaming para llama.cpp) |

---

## Estrutura do projeto

```
naive-rag/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pyproject.toml
├── rag.py                material educacional (script original)
├── rag.ipynb             material educacional (notebook original)
├── src/
│   ├── main.py           FastAPI app, rotas e endpoints
│   ├── db.py             pool psycopg2, schema, queries pgvector
│   ├── embeddings.py     cliente Ollama async (sempre usado)
│   ├── rag.py            pipeline RAG com streaming (Ollama + llama.cpp)
│   ├── turboquant.py     estado, metricas e formula KV Cache
│   ├── backend.py        selecao de backend (ollama | llamacpp)
│   ├── chunker.py        recursive character splitter
│   ├── parsers.py        extracao de texto por tipo de arquivo
│   └── routes/
│       ├── documents.py  CRUD de documentos e arquivos
│       ├── query.py      endpoint de consulta SSE
│       └── upload.py     upload e ingestao de arquivos
├── public/
│   ├── index.html
│   ├── style.css
│   └── app.js
└── llama.cpp/            (opcional) servidor llama.cpp compilado localmente
    └── models/
        └── gemma-3-12b/  modelo GGUF para KV Cache real
```

---

## Variaveis de ambiente

Copie `.env.example` para `.env` para desenvolvimento local:

```bash
cp .env.example .env
```

| Variavel | Padrao | Descricao |
|----------|--------|-----------|
| `DATABASE_URL` | `postgres://...` | Connection string do PostgreSQL |
| `OLLAMA_HOST` | `http://localhost:11434` | Endereco do servidor Ollama |
| `EMBED_MODEL` | `embeddinggemma:latest` | Modelo de embedding (sempre Ollama) |
| `TEXT_MODEL` | `gemma4:latest` | Modelo gerador de texto (backend Ollama) |
| `EMBEDDING_DIM` | `768` | Dimensoes do vetor (deve bater com o modelo) |
| `LLAMACPP_HOST` | `http://localhost:8080` | Endereco do llama-server (backend opcional) |
| `LLAMACPP_MODEL` | `gemma-3-12b` | Label do modelo no llama-server |
| `PORT` | `3001` | Porta da API |

> Se trocar o modelo de embedding, ajuste `EMBEDDING_DIM` e recrie o banco com `docker compose down -v`.

---

## Servicos e portas

| Servico | Porta | Descricao |
|---------|-------|-----------|
| API RAG | `3001` | FastAPI + interface web |
| PostgreSQL | `5433` | pgvector (mapeado do container) |
| Ollama | `11434` | Servidor Ollama no host |
| llama-server | `8080` | llama.cpp no host (opcional) |

---

## Desenvolvimento local (sem Docker)

```bash
# Instalar dependencias
uv sync --dev

# Subir apenas o Postgres
docker compose up postgres -d

# Configurar variaveis
cp .env.example .env

# Rodar a API com hot reload
uv run uvicorn src.main:app --reload --port 3001
```

---

## Documentacao

| Documento | Conteudo |
|-----------|---------|
| [Conceitos RAG](docs/rag-concepts.md) | O que e RAG, embeddings, similaridade de cosseno |
| [Arquitetura](docs/architecture.md) | Fluxo de dados, modulos, decisoes de design |
| [Configuracao](docs/setup.md) | Docker, Ollama, llama.cpp, Postgres, desenvolvimento local |
| [Chunking](docs/chunking.md) | Estrategia de divisao de texto, parametros, trade-offs |
| [API](docs/api.md) | Referencia completa dos endpoints |
| [TurboQuant KV Cache](docs/turboquant.md) | Modos de quantizacao, backend llama.cpp, formula de memoria e endpoints |

---

## API — resumo rapido

```
POST /api/documents          adiciona documento de texto
GET  /api/documents          lista documentos avulsos
DELETE /api/documents/{id}   remove documento por id

GET  /api/documents/files              lista arquivos importados
DELETE /api/documents/files/{filename} remove todos os chunks de um arquivo

POST /api/upload             importa arquivo (PDF, DOCX, MD, TXT) — multipart/form-data
POST /api/query              consulta RAG — resposta em SSE (text/event-stream)

GET  /api/turboquant/config  retorna modo TurboQuant atual
POST /api/turboquant/config  altera modo TurboQuant
GET  /api/turboquant/metrics ultimos 50 registros de inferencia e medias por modo

GET  /api/backend/config     retorna backend ativo (ollama | llamacpp)
POST /api/backend/config     alterna backend de inferencia
```

Detalhes completos em [docs/api.md](docs/api.md).
