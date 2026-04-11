# TurboQuant KV Cache

TurboQuant e uma aproximacao local do conceito apresentado no paper Google ICLR 2026 que reduz o uso de memoria da KV Cache de modelos de linguagem aplicando quantizacao nos tensores K e V durante a inferencia.

---

## Modos disponiveis

| Modo | Quantizacao | Parametros Ollama | Reducao de memoria estimada |
|------|-------------|-------------------|-----------------------------|
| OFF | FP16 (padrao) | — (defaults do Ollama) | baseline |
| Standard (8-bit) | 8-bit | `num_ctx=4096, num_batch=256` | ~50% |
| TurboQuant (3-bit) | 3-bit | `num_ctx=4096, num_batch=512, num_keep=5` | ~73% |

---

## Formula de memoria da KV Cache

A memoria ocupada pela KV Cache e calculada pela formula:

```
tokens × 2 × hidden_dim × layers × bytes_per_value
```

Onde:
- `×2` — tensores K e V separados
- `hidden_dim` — `head_dim(256) × num_kv_heads(8) = 2048` (`n_embd_k_gqa` real do Gemma 3 12B)
- `layers` — 48 camadas transformer (8 non-SWA global + 40 SWA sliding window)
- `bytes_per_value` — FP16=2.0 | 8-bit=1.0 | 3-bit≈0.375

As constantes estao definidas em `src/turboquant.py`:

```python
HIDDEN_DIM = 2048   # head_dim(256) × num_kv_heads(8) = n_embd_k_gqa
LAYERS     = 48     # 8 non-SWA + 40 SWA
BYTES_FP16 = 2.0
BYTES_8BIT = 1.0
BYTES_3BIT = 0.375
```

---

## Como o grafico de comparacao funciona

O grafico de "Comparacao de Modos" **nao executa 3 inferencias por query**. Cada pergunta roda uma unica inferencia, no modo que estiver selecionado no momento.

O backend mantem um ring buffer de ate 50 registros em memoria (`collections.deque`), agrupados por modo. Apos cada inferencia, o servidor retorna as medias historicas acumuladas de cada grupo:

```python
# src/turboquant.py
def get_summary() -> dict:
    return {
        "off":        summarise([r for r in records if r["mode"] == "off"]),
        "standard":   summarise([r for r in records if r["mode"] == "standard"]),
        "aggressive": summarise([r for r in records if r["mode"] == "aggressive"]),
    }
```

O frontend exibe os 3 grupos sempre. Se um modo ainda nao tem dados, a barra aparece como `"—"`. Os dados acumulados sao resetados ao reiniciar o container (estado em memoria, sem persistencia — comportamento esperado para demonstracao).

**Exemplo:** se voce fizer 5 queries em TurboQuant, as barras OFF e Standard aparecerao como `"—"` ate que voce alterne para esses modos e faca pelo menos uma query em cada.

---

## Metricas registradas por inferencia

Cada registro armazena os seguintes campos, extraidos diretamente do response do Ollama:

| Campo | Descricao |
|-------|-----------|
| `total_ms` | Tempo total da chamada |
| `load_ms` | Tempo de carregamento do modelo |
| `prompt_eval_ms` | Tempo de avaliacao do prompt (prefill) |
| `eval_ms` | Tempo de geracao dos tokens (decode) |
| `tokens_per_sec` | Tokens gerados por segundo (`gen_tokens / eval_s`) |
| `kv_bytes` | Estimativa de memoria KV no modo atual |
| `kv_bytes_fp16` | Estimativa de memoria KV em FP16 (baseline) |
| `memory_reduction` | Reducao percentual em relacao ao FP16 |

---

## Backend llama.cpp — quantizacao real da KV Cache

O toggle "llama.cpp" na interface troca o backend de geracao de texto para o
[llama-server](https://github.com/ggml-org/llama.cpp), que implementa quantizacao
**real** dos tensores K e V via flags de startup — diferente do Ollama que apenas
ajusta parametros de contexto/batch.

> Os embeddings continuam sendo gerados pelo Ollama (`embeddinggemma:latest`)
> independente do backend selecionado.

---

### 1. Instalar o llama.cpp

```bash
# Clonar e compilar (requer cmake e compilador C++)
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_CUDA=ON   # remova DGGML_CUDA=ON se nao tiver GPU NVIDIA
cmake --build build --config Release -j$(nproc)
```

O binario gerado sera `build/bin/llama-server`.

---

### 2. Baixar o modelo GGUF do HuggingFace

O modelo recomendado e o Gemma 3 12B IT com quantizacao QAT Q4_0 (oficial Google):

```
https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-gguf
```

O repositorio e gated — aceite a licenca em
`https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-gguf` e faca login:

```bash
# huggingface-cli esta depreciado — use hf
hf auth login   # crie um token Read em https://huggingface.co/settings/tokens

# Baixar o modelo (~7 GB)
hf download google/gemma-3-12b-it-qat-q4_0-gguf \
  --repo-type model \
  --include "*.gguf" \
  --local-dir ./models/gemma-3-12b
```

Apos o download, verifique o nome exato:

```bash
ls ./models/gemma-3-12b/
# gemma-3-12b-it-q4_0.gguf  mmproj-model-f16-12B.gguf
```

---

### 3. Iniciar o llama-server com KV Cache quantizado

O servidor deve escutar em `0.0.0.0` para que o container Docker acesse via
`host.docker.internal`. O nome do arquivo GGUF e `gemma-3-12b-it-q4_0.gguf`
(sem `qat` no nome apos o download):

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
```

> Sem `--host 0.0.0.0` o servidor escuta apenas em `127.0.0.1` e o container
> Docker nao consegue alcancar o servico via `host.docker.internal`.

Tipos de quantizacao disponiveis para `--cache-type-k/v`:

| Tipo | Bits | Reducao vs FP16 |
|------|------|-----------------|
| `f16` | 16 | baseline |
| `q8_0` | 8 | ~50% |
| `q4_0` | 4 | ~75% |
| `q4_1` | 4+ | ~75% |
| `iq4_nl` | 4 | ~75% (non-linear) |

---

### 4. Ativar o backend na interface

Com o llama-server rodando na porta 8080, clique em **llama.cpp** no painel
TurboQuant KV Cache. O host e modelo sao configurados pelas variaveis de ambiente:

```env
LLAMACPP_HOST=http://localhost:8080
LLAMACPP_MODEL=gemma-3-12b
```

A API do llama-server e compativel com OpenAI (`/v1/chat/completions`), entao
o campo `model` e apenas um label — o servidor usa o modelo carregado no startup.

---

### Comparacao das abordagens

| | Ollama (TurboQuant) | llama.cpp |
|---|---|---|
| Quantizacao KV Cache | Simulada via params | Real (tensores K/V) |
| Controle por request | Sim (num_ctx, num_batch) | Nao (fixo no startup) |
| Medicao de memoria | Estimativa por formula | Estimativa por formula |
| Setup | Zero (ja instalado) | Requer compilacao + download GGUF |
| Embeddings | Ollama | Ollama (sempre) |

---

## Endpoints da API

| Metodo | Rota | Descricao |
|--------|------|-----------|
| `GET` | `/api/turboquant/config` | Retorna o modo atual (`enabled`, `mode`) |
| `POST` | `/api/turboquant/config` | Altera o modo (`enabled: bool`, `mode: "off"\|"standard"\|"aggressive"`) |
| `GET` | `/api/turboquant/metrics` | Retorna os ultimos 50 registros e as medias por modo |
| `GET` | `/api/backend/config` | Retorna o backend ativo e host/model do llama.cpp |
| `POST` | `/api/backend/config` | Alterna backend (`backend: "ollama"\|"llamacpp"`) |

Exemplo de ativacao via curl:

```bash
# Ativar TurboQuant 3-bit
curl -X POST http://localhost:3001/api/turboquant/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "mode": "aggressive"}'

# Verificar modo atual
curl http://localhost:3001/api/turboquant/config

# Ver metricas acumuladas
curl http://localhost:3001/api/turboquant/metrics
```
