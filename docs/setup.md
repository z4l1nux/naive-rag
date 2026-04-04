# Configuracao e Instalacao

## Prerequisitos

| Ferramenta | Versao minima | Para que serve |
|------------|--------------|----------------|
| Docker + Compose | 24+ | Rodar API e PostgreSQL |
| Ollama | qualquer | Rodar os modelos localmente |
| uv (opcional) | qualquer | Apenas para desenvolvimento local sem Docker |

---

## 1. Instalar o Ollama

O Ollama roda fora do Docker, diretamente no host.

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama
```

Inicie o servidor (deixe rodando em terminal separado):

```bash
ollama serve
# servidor disponivel em http://localhost:11434
```

### Baixar os modelos

```bash
# Modelo de embedding — converte texto em vetor numerico (768 dims)
ollama pull embeddinggemma:latest

# Modelo de texto — gera a resposta final a partir do contexto
ollama pull gemma4:e2b
```

Para verificar:

```bash
ollama list
# deve listar embeddinggemma:latest e gemma4:e2b
```

### Trocar de modelo

Altere as variaveis no `docker-compose.yml`:

```yaml
EMBED_MODEL: nomic-embed-text   # outro modelo de embedding
TEXT_MODEL: llama3.2            # outro modelo de texto
EMBEDDING_DIM: "768"            # dimensoes do novo modelo de embedding
```

> Se trocar o modelo de embedding, o `EMBEDDING_DIM` deve bater com as dimensoes que o novo modelo produz. E necessario recriar o banco com `docker compose down -v`.

---

## 2. Rodar com Docker (recomendado)

```bash
git clone <url>
cd naive-rag
docker compose up --build
```

Acesse `http://localhost:3000`.

### Parar sem perder dados

```bash
docker compose down
# ou Ctrl+C no terminal
```

### Parar e remover tudo (incluindo dados)

```bash
docker compose down -v
```

O `-v` remove o volume `pgdata`. Use apenas se quiser comecar do zero (necessario ao trocar o modelo de embedding).

---

## 3. Desenvolvimento local (sem Docker)

### 3.1 Instalar uv

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3.2 Subir apenas o Postgres

```bash
docker compose up postgres -d
```

### 3.3 Instalar dependencias

```bash
# Apenas dependencias de producao
uv sync

# Com dependencias de desenvolvimento (ipykernel, groq, sentence-transformers)
uv sync --dev
```

### 3.4 Configurar variaveis de ambiente

```bash
cp .env.example .env
```

O `.env.example` ja vem com os valores corretos para o Postgres do Docker:

```env
DATABASE_URL=postgres://raguser:ragpass@localhost:5432/ragdb
OLLAMA_HOST=http://localhost:11434
EMBED_MODEL=embeddinggemma:latest
TEXT_MODEL=gemma4:e2b
EMBEDDING_DIM=768
PORT=3000
```

### 3.5 Rodar a API

```bash
uv run uvicorn src.main:app --reload --port 3000
```

O `--reload` reinicia o servidor automaticamente ao salvar qualquer arquivo em `src/`.

---

## 4. Rodar o material educacional (notebook / script)

```bash
# Instalar dependencias de dev (inclui ipykernel)
uv sync --dev

# Script direto
uv run python rag.py

# Notebook no VS Code
# Abra rag.ipynb, clique em "Select Kernel" e escolha o .venv do projeto
```

---

## 5. Variaveis de ambiente — referencia completa

| Variavel | Padrao | Obrigatoria | Descricao |
|----------|--------|-------------|-----------|
| `DATABASE_URL` | — | Sim | Connection string PostgreSQL |
| `OLLAMA_HOST` | `http://localhost:11434` | Nao | Endereco do servidor Ollama |
| `EMBED_MODEL` | `embeddinggemma:latest` | Nao | Modelo de embedding |
| `TEXT_MODEL` | `gemma4:e2b` | Nao | Modelo de geracao de texto |
| `EMBEDDING_DIM` | `768` | Nao | Dimensoes do vetor (deve bater com `EMBED_MODEL`) |
| `PORT` | `3000` | Nao | Porta HTTP da API |

---

## 6. Como o Docker acessa o Ollama do host

Em Linux, o container nao pode acessar `localhost` do host diretamente. O `docker-compose.yml` usa:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Isso mapeia `host.docker.internal` para o IP do host dentro da rede Docker. No macOS e Windows isso e automatico com Docker Desktop.

---

## 7. Limites de arquivo no upload

O limite padrao e **20 MB** por arquivo, configurado em `src/routes/upload.py`:

```python
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
```

PDFs com muitas paginas podem levar varios minutos — cada chunk exige uma chamada ao Ollama para gerar o embedding.
