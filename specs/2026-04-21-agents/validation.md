# Validation — como verificar que o sistema ainda funciona

Checklist de smoke tests para validar o sistema após mudanças, atualizações de dependência ou troca de modelo.

---

## Pré-requisitos

```bash
ollama serve                          # Ollama rodando no host
ollama pull embeddinggemma:latest     # modelo de embeddings presente
ollama pull gemma4:latest             # modelo de geração presente
docker compose up --build -d          # API + Postgres no ar
```

Aguardar o log `Database ready.` antes de prosseguir.

---

## 1. Health da API

```bash
curl -s http://localhost:3001/api/documents | python3 -m json.tool
# Esperado: [] (array vazio ou lista de docs existentes)
```

Qualquer resposta 2xx confirma que FastAPI inicializou, `init_db()` rodou e o pool de conexões está ativo.

---

## 2. Ingestão de documento de texto

```bash
curl -s -X POST http://localhost:3001/api/documents \
  -H "Content-Type: application/json" \
  -d '{"content": "O pgvector é uma extensão do PostgreSQL para busca vetorial."}' \
  | python3 -m json.tool
# Esperado: objeto com id, content, created_at
```

Valida: `get_embedding()` → Ollama → `insert_document()` → pgvector.

---

## 3. Upload de arquivo

```bash
# Criar um arquivo de teste
echo "RAG combina recuperação de documentos com geração de texto por LLMs." > /tmp/test.txt

curl -s -X POST http://localhost:3001/api/upload \
  -F "file=@/tmp/test.txt" \
  -F "chunkSize=500" \
  -F "overlap=50" \
  | python3 -m json.tool
# Esperado: {"source": "test.txt", "chunks": 1}
```

Valida: `validate_file()` → `extract_text()` → `chunk_text()` → loop de embeddings → `insert_document()`.

---

## 4. Listagem de arquivos

```bash
curl -s http://localhost:3001/api/documents/files | python3 -m json.tool
# Esperado: [{"source_file": "test.txt", "chunk_count": 1, "created_at": "..."}]
```

Valida: `list_files()` com `GROUP BY source_file`.

---

## 5. Query RAG com streaming

```bash
curl -s -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "O que é pgvector?", "topK": 3}'
# Esperado: linhas SSE começando com "data: "
# Sequência: tokens → sources → metrics
```

Verificar que:
- Pelo menos um evento `{"type": "token", ...}` é emitido
- Um evento `{"type": "sources", "sources": [...]}` aparece ao final
- Um evento `{"type": "metrics", ...}` é emitido (apenas se backend Ollama)

---

## 6. TurboQuant — configuração e métricas

```bash
# Verificar estado inicial (off)
curl -s http://localhost:3001/api/turboquant/config
# Esperado: {"enabled": false, "mode": "off"}

# Ativar modo standard
curl -s -X POST http://localhost:3001/api/turboquant/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "mode": "standard"}'
# Esperado: {"enabled": true, "mode": "standard"}

# Fazer uma query e checar métricas
curl -s -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "O que é pgvector?"}' > /dev/null

curl -s http://localhost:3001/api/turboquant/metrics | python3 -m json.tool
# Esperado: records com pelo menos 1 entrada, summary com dados para "standard"

# Restaurar para off
curl -s -X POST http://localhost:3001/api/turboquant/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "mode": "off"}'
```

---

## 7. Alternância de backend

```bash
curl -s http://localhost:3001/api/backend/config
# Esperado: {"backend": "ollama", "llamacpp_host": "...", "llamacpp_model": "..."}

curl -s -X POST http://localhost:3001/api/backend/config \
  -H "Content-Type: application/json" \
  -d '{"backend": "llamacpp"}'
# Esperado: {"backend": "llamacpp", ...}

# Query com backend llamacpp (llama-server pode estar offline — verificar erro gracioso)
curl -s -N -X POST http://localhost:3001/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "teste"}' | head -1
# Esperado se server offline: data: {"type": "error", "message": "llama.cpp server nao encontrado..."}

# Restaurar para ollama
curl -s -X POST http://localhost:3001/api/backend/config \
  -H "Content-Type: application/json" \
  -d '{"backend": "ollama"}'
```

---

## 8. Remoção de dados

```bash
# Remover arquivo e seus chunks
curl -s -X DELETE "http://localhost:3001/api/documents/files/test.txt"
# Esperado: {"deleted": 1}

# Verificar que sumiu
curl -s http://localhost:3001/api/documents/files
# Esperado: [] ou lista sem test.txt
```

---

## 9. Regressão de schema (halfvec)

Válido apenas ao trocar `EMBEDDING_DIM` para um valor > 2000:

```bash
# No .env, ajustar EMBEDDING_DIM=3072 (ex.: modelos nomic v2)
# Então:
docker compose down -v   # apaga o volume do Postgres
docker compose up --build -d
# Verificar que a tabela criada usa halfvec(3072) e não vector(3072)
docker compose exec postgres psql -U rag -d rag \
  -c "\d documents"
# Esperado: coluna embedding do tipo halfvec(3072)
```

---

## Cleanup após os testes

```bash
# Remover arquivo de teste (se ainda existir)
curl -s -X DELETE "http://localhost:3001/api/documents/files/test.txt"

# Remover documentos avulsos criados no passo 2
# Liste os ids primeiro:
curl -s http://localhost:3001/api/documents | python3 -c "import sys,json; [print(d['id']) for d in json.load(sys.stdin)]"
# Então para cada id:
curl -s -X DELETE http://localhost:3001/api/documents/<id>

# Ou destruir o volume do Postgres para estado completamente limpo:
# docker compose down -v && docker compose up -d
```

---

## Indicadores de falha

| Sintoma | Causa provável |
|---------|---------------|
| `curl /api/documents` retorna 500 | Postgres não inicializou ou `DATABASE_URL` errada |
| `get_embedding` falha com timeout | Ollama não está rodando ou modelo não baixado |
| Query SSE retorna `{"type":"error","message":"..."}` | Modelo Ollama não disponível |
| Upload retorna `{"detail": "Tipo de arquivo nao suportado"}` | Extensão fora de `{pdf, docx, md, txt}` |
| Upload retorna 500 com `Erro ao extrair texto` | `pypdf` ou `python-docx` não instalados (`uv sync`) |
| Métricas TurboQuant vazias após query | Backend ativo é `llamacpp` (métricas são estimativas, verificar código) |
