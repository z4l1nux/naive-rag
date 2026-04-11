# RAG com pgvector e Python

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white">
  <img src="https://img.shields.io/badge/pgvector-pg17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">
  <img src="https://img.shields.io/badge/Ollama-Local%20LLM-FF6600?style=for-the-badge">
</p>

Pipeline RAG (Retrieval-Augmented Generation) completo com banco de dados vetorial, API REST com streaming e interface web. Roda inteiramente local — sem nenhuma API externa paga.

> `rag.py` e `rag.ipynb` na raiz sao o material educacional original que deu origem a este projeto. A aplicacao web vive em `src/`.

---

## Quick start

**Prerequisito:** Ollama rodando com os modelos baixados.

```bash
ollama pull embeddinggemma:latest
ollama pull gemma4:latest
```

**Subir tudo:**

```bash
git clone <url>
cd naive-rag
docker compose up --build
```

Acesse `http://localhost:3000`. Adicione documentos ou importe arquivos e faca perguntas.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Runtime | Python 3.12 + uv |
| API | FastAPI + uvicorn com StreamingResponse (SSE) |
| Banco vetorial | PostgreSQL 17 + pgvector (HNSW) |
| Embeddings | Ollama (`embeddinggemma:latest`, 768 dims) |
| Gerador de texto | Ollama (`gemma4:latest`) |
| Containers | Docker Compose |
| Parsers de arquivo | `pypdf`, `python-docx` |

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
│   ├── main.py           FastAPI app, inicializa DB e monta rotas
│   ├── db.py             pool psycopg2, schema, queries pgvector
│   ├── embeddings.py     cliente Ollama async
│   ├── rag.py            pipeline RAG com streaming (AsyncGenerator)
│   ├── chunker.py        recursive character splitter
│   ├── parsers.py        extracao de texto por tipo de arquivo
│   └── routes/
│       ├── documents.py  CRUD de documentos e arquivos
│       ├── query.py      endpoint de consulta SSE
│       └── upload.py     upload e ingestao de arquivos
└── public/
    ├── index.html
    ├── style.css
    └── app.js
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
| `EMBED_MODEL` | `embeddinggemma:latest` | Modelo de embedding |
| `TEXT_MODEL` | `gemma4:latest` | Modelo gerador de texto |
| `EMBEDDING_DIM` | `768` | Dimensoes do vetor (deve bater com o modelo) |
| `PORT` | `3000` | Porta da API |

> Se trocar o modelo de embedding, ajuste `EMBEDDING_DIM` e recrie o banco com `docker compose down -v`.

---

## Desenvolvimento local (sem Docker)

```bash
# Instalar dependencias (incluindo dev para o notebook)
uv sync --dev

# Subir apenas o Postgres
docker compose up postgres -d

# Rodar a API com hot reload
cp .env.example .env
uv run uvicorn src.main:app --reload --port 3000
```

---

## Documentacao

| Documento | Conteudo |
|-----------|---------|
| [Conceitos RAG](docs/rag-concepts.md) | O que e RAG, embeddings, similaridade de cosseno |
| [Arquitetura](docs/architecture.md) | Fluxo de dados, modulos, decisoes de design |
| [Configuracao](docs/setup.md) | Docker, Ollama, Postgres, desenvolvimento local |
| [Chunking](docs/chunking.md) | Estrategia de divisao de texto, parametros, trade-offs |
| [API](docs/api.md) | Referencia completa dos endpoints |
| [TurboQuant KV Cache](docs/turboquant.md) | Modos de quantizacao, formula de memoria, grafico de comparacao e endpoints |

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
```

Detalhes completos em [docs/api.md](docs/api.md).
