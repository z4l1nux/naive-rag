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
- `hidden_dim` — `head_dim(256) × num_kv_heads(16) = 4096` (Gemma 4 12B)
- `layers` — 32 camadas transformer
- `bytes_per_value` — FP16=2.0 | 8-bit=1.0 | 3-bit≈0.375

As constantes estao definidas em `src/turboquant.py`:

```python
HIDDEN_DIM = 4096
LAYERS     = 32
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

## Endpoints da API

| Metodo | Rota | Descricao |
|--------|------|-----------|
| `GET` | `/api/turboquant/config` | Retorna o modo atual (`enabled`, `mode`) |
| `POST` | `/api/turboquant/config` | Altera o modo (`enabled: bool`, `mode: "off"\|"standard"\|"aggressive"`) |
| `GET` | `/api/turboquant/metrics` | Retorna os ultimos 50 registros e as medias por modo |

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
