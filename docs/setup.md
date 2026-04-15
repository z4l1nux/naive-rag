# Configuracao e Instalacao

## Prerequisitos

| Ferramenta | Versao minima | Para que serve |
|------------|--------------|----------------|
| Docker + Compose | 24+ | Rodar API e PostgreSQL |
| Ollama | qualquer | Embeddings e modelo de texto (backend padrao) |
| llama.cpp | build recente | Backend alternativo com KV Cache quantizado (opcional) |
| uv | qualquer | Apenas para desenvolvimento local sem Docker |
| cmake + g++ | qualquer | Apenas para compilar o llama.cpp |

---

## 1. Ollama — backend padrao

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
# Modelo de embedding — sempre necessario, independente do backend de texto
ollama pull embeddinggemma:latest   # 768 dims

# Modelo de texto — usado quando o backend Ollama estiver selecionado
ollama pull gemma4:latest
```

Para verificar:

```bash
ollama list
# deve listar embeddinggemma:latest e gemma4:latest
```

### Quantizacao da KV Cache no Ollama (opcional)

O Ollama suporta quantizacao nativa da KV Cache via variavel de ambiente do servidor.
Defina antes de iniciar `ollama serve`:

```bash
# 4-bit — reducao de ~75% vs FP16, maior economia de VRAM
OLLAMA_KV_CACHE_TYPE=q4_0 ollama serve

# 8-bit — reducao de ~50% vs FP16, melhor qualidade
OLLAMA_KV_CACHE_TYPE=q8_0 ollama serve
```

> Isso e diferente do TurboQuant: o Ollama aplica quantizacao simples (4 ou 8 bits)
> nos tensores K/V a nivel de servidor. O TurboQuant ajusta parametros de contexto/batch
> por requisicao para simular diferentes niveis de compressao.

### Trocar modelo de texto (Ollama)

Altere as variaveis no `docker-compose.yml`:

```yaml
TEXT_MODEL: llama3.2   # qualquer modelo disponivel no Ollama
```

### Trocar modelo de embedding

```yaml
EMBED_MODEL: nomic-embed-text
EMBEDDING_DIM: "768"   # ajuste conforme o novo modelo
```

> Ao trocar o modelo de embedding e necessario recriar o banco: `docker compose down -v`.

---

## 2. llama.cpp — backend com KV Cache real (opcional)

O llama.cpp permite quantizacao **real** dos tensores K e V da KV Cache, diferente do
Ollama que usa parametros de contexto como aproximacao. O backend e selecionado via
toggle na interface — os dois podem coexistir.

> Os embeddings continuam sendo gerados pelo Ollama independente do backend selecionado.

### 2.1 Compilar o llama-server

```bash
# Dentro do diretorio do projeto (ou qualquer outro local)
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp

# Sem GPU (CPU apenas)
cmake -B build
cmake --build build --config Release -j$(nproc)

# Com GPU NVIDIA (requer CUDA toolkit instalado)
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release -j$(nproc)
```

O binario gerado sera `build/bin/llama-server`.

### 2.2 Baixar o modelo GGUF

O modelo recomendado e o Gemma 3 12B IT QAT Q4_0 (oficial Google, ~7 GB).
O repositorio e gated — e necessario aceitar a licenca Gemma no HuggingFace
e fazer login com um token antes de baixar.

**Passo 1 — aceitar a licenca:**

Acesse e clique em "Agree and access repository":
`https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-gguf`

**Passo 2 — fazer login:**

```bash
# Criar token em: https://huggingface.co/settings/tokens (tipo: Read)
hf auth login
# Cole o token quando solicitado
```

**Passo 3 — baixar:**

```bash
# A partir do diretorio llama.cpp/
hf download google/gemma-3-12b-it-qat-q4_0-gguf \
  --repo-type model \
  --include "*.gguf" \
  --local-dir ./models/gemma-3-12b
```

Apos o download, verifique o nome exato do arquivo:

```bash
ls ./models/gemma-3-12b/
# gemma-3-12b-it-q4_0.gguf  mmproj-model-f16-12B.gguf
```

### 2.3 Iniciar o llama-server

O servidor deve escutar em `0.0.0.0` para que o container Docker acesse via
`host.docker.internal`:

```bash
# KV Cache Q4_0 — reducao real de ~75% vs FP16 (recomendado)
./build/bin/llama-server \
  --model ./models/gemma-3-12b/gemma-3-12b-it-q4_0.gguf \
  --cache-type-k q4_0 \
  --cache-type-v q4_0 \
  --ctx-size 4096 \
  --host 0.0.0.0 \
  --port 8080

# KV Cache Q8_0 — reducao de ~50%, maior qualidade
./build/bin/llama-server \
  --model ./models/gemma-3-12b/gemma-3-12b-it-q4_0.gguf \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --ctx-size 4096 \
  --host 0.0.0.0 \
  --port 8080

# FP16 — sem quantizacao KV Cache (baseline)
./build/bin/llama-server \
  --model ./models/gemma-3-12b/gemma-3-12b-it-q4_0.gguf \
  --ctx-size 4096 \
  --host 0.0.0.0 \
  --port 8080
```

Tipos de quantizacao disponíveis para `--cache-type-k/v`:

| Tipo | Bits | Reducao vs FP16 |
|------|------|-----------------|
| `f16` | 16 | baseline |
| `q8_0` | 8 | ~50% |
| `q4_0` | 4 | ~75% |
| `iq4_nl` | 4 | ~75% (non-linear) |

O servidor ficara disponivel em `http://localhost:8080`. A interface web em
`http://localhost:8080` permite testar o modelo diretamente.

### 2.4 Ativar o backend na interface

Com o llama-server rodando, clique em **llama.cpp** no painel TurboQuant da
interface RAG. A troca e instantanea e sem necessidade de reiniciar containers.

Para configurar o endereco via variaveis de ambiente (`.env` ou `docker-compose.yml`):

```env
LLAMACPP_HOST=http://localhost:8080
LLAMACPP_MODEL=gemma-3-12b
```

> O campo `LLAMACPP_MODEL` e apenas um label — o llama-server usa o modelo
> carregado no startup independente do valor enviado na requisicao.

---

## 3. Rodar com Docker (recomendado)

Com Ollama rodando no host:

```bash
git clone <url>
cd naive-rag
docker compose up --build
```

Acesse `http://localhost:3001`.

### Reconstruir apos mudancas no codigo

```bash
docker compose up --build api -d
```

> `docker compose restart api` **nao** atualiza o codigo — os arquivos sao
> copiados para dentro da imagem durante o build.

### Parar sem perder dados

```bash
docker compose down
# ou Ctrl+C no terminal
```

### Parar e remover tudo (incluindo dados do banco)

```bash
docker compose down -v
```

O `-v` remove o volume `pgdata`. Use apenas se quiser comecar do zero
(necessario ao trocar o modelo de embedding).

---

## 4. Desenvolvimento local (sem Docker)

### 4.1 Instalar uv

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 4.2 Subir apenas o Postgres

```bash
docker compose up postgres -d
```

### 4.3 Instalar dependencias

```bash
# Apenas dependencias de producao
uv sync

# Com dependencias de desenvolvimento (ipykernel, groq, sentence-transformers)
uv sync --dev
```

### 4.4 Configurar variaveis de ambiente

```bash
cp .env.example .env
```

O `.env.example` ja vem com os valores corretos:

```env
DATABASE_URL=postgres://raguser:ragpass@localhost:5433/ragdb
OLLAMA_HOST=http://localhost:11434
EMBED_MODEL=embeddinggemma:latest
TEXT_MODEL=gemma4:latest
EMBEDDING_DIM=768
PORT=3001
LLAMACPP_HOST=http://localhost:8080
LLAMACPP_MODEL=gemma-3-12b
```

### 4.5 Rodar a API

```bash
uv run uvicorn src.main:app --reload --port 3001
```

O `--reload` reinicia o servidor automaticamente ao salvar qualquer arquivo em `src/`.

---

## 5. Rodar o material educacional (notebook / script)

```bash
# Instalar dependencias de dev (inclui ipykernel)
uv sync --dev

# Script direto
uv run python rag.py

# Notebook no VS Code
# Abra rag.ipynb, clique em "Select Kernel" e escolha o .venv do projeto
```

---

## 6. Variaveis de ambiente — referencia completa

| Variavel | Padrao | Obrigatoria | Descricao |
|----------|--------|-------------|-----------|
| `DATABASE_URL` | — | Sim | Connection string PostgreSQL |
| `OLLAMA_HOST` | `http://localhost:11434` | Nao | Endereco do servidor Ollama |
| `EMBED_MODEL` | `embeddinggemma:latest` | Nao | Modelo de embedding (sempre Ollama) |
| `TEXT_MODEL` | `gemma4:latest` | Nao | Modelo de texto do backend Ollama |
| `EMBEDDING_DIM` | `768` | Nao | Dimensoes do vetor (deve bater com `EMBED_MODEL`) |
| `LLAMACPP_HOST` | `http://localhost:8080` | Nao | Endereco do llama-server |
| `LLAMACPP_MODEL` | `gemma-3-12b` | Nao | Label do modelo no llama-server |
| `PORT` | `3001` | Nao | Porta HTTP da API |

---

## 7. Como o Docker acessa servicos no host

Em Linux, containers nao acessam `localhost` do host diretamente. O `docker-compose.yml` usa:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Isso mapeia `host.docker.internal` para o IP do host dentro da rede Docker.
No macOS e Windows isso e automatico com Docker Desktop.

Isso afeta tanto o Ollama (`OLLAMA_HOST=http://host.docker.internal:11434`)
quanto o llama-server (`LLAMACPP_HOST=http://host.docker.internal:8080`) —
ambos devem escutar em `0.0.0.0` no host para serem acessiveis.

---

## 8. Limites de arquivo no upload

O limite padrao e **20 MB** por arquivo, configurado em `src/routes/upload.py`:

```python
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
```

PDFs com muitas paginas podem levar varios minutos — cada chunk exige uma
chamada ao Ollama para gerar o embedding.

---

## 9. Ordem de inicializacao recomendada

```
1. ollama serve                    # host, terminal 1
2. llama-server (se usar llama.cpp) # host, terminal 2
3. docker compose up --build       # containers
4. http://localhost:3001           # interface web
```
