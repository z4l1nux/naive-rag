# Requirements — decisões de design (retroativo)

Decisões arquiteturais derivadas do código implementado e da documentação existente.

---

## Infraestrutura

**Docker Compose isola PostgreSQL; Ollama fica no host.**
O Ollama precisa de acesso à GPU diretamente. Containerizá-lo exige configuração de passthrough de dispositivo e complica o setup. A solução foi deixá-lo no host e acessá-lo via `host.docker.internal` a partir do container da API.

**PostgreSQL em vez de banco vetorial dedicado (Pinecone, Weaviate, Qdrant).**
O pgvector é suficiente para o volume educacional deste projeto, não exige um serviço adicional, e mantém a stack simples: um container a menos, nenhuma nova API para aprender.

**HNSW em vez de IVFFlat.**
IVFFlat exige pré-treinamento com um número mínimo de vetores e degrada em datasets pequenos. HNSW funciona corretamente desde o primeiro documento inserido, sem configuração adicional.

---

## API e streaming

**FastAPI em vez de Flask.**
FastAPI tem suporte nativo a `async/await`, validação automática via Pydantic, e `StreamingResponse` que aceita `AsyncGenerator` diretamente — os três são necessários para SSE sem workarounds.

**SSE em vez de WebSocket.**
A comunicação é unidirecional: servidor envia tokens, cliente só lê. SSE é mais simples, funciona sobre HTTP, e não exige upgrade de protocolo.

**Rotas de API registradas antes do `StaticFiles`.**
O `StaticFiles` do FastAPI captura qualquer rota não reconhecida. Se registrado primeiro, interceptaria `/api/*` antes dos routers. A ordem em `main.py` é deliberada.

**Header `X-Accel-Buffering: no` em respostas SSE.**
Nginx e outros proxies reversos fazem buffer de respostas por padrão. Sem esse header, o cliente recebe todos os tokens de uma vez ao final da geração, destruindo a experiência de streaming.

---

## Banco de dados

**`psycopg2` (síncrono) em vez de `asyncpg`.**
O psycopg2 é o driver mais estável e documentado para PostgreSQL em Python. O FastAPI delega chamadas síncronas a um threadpool automaticamente. Para queries simples de INSERT/SELECT, a diferença de throughput é negligível.

**`ThreadedConnectionPool` com `minconn=1, maxconn=5`.**
Evita criar uma conexão nova por request sem over-provisionar conexões no Postgres. O pool é gerenciado pelo context manager `get_db()`.

**`autocommit=True` apenas no DDL de inicialização.**
`CREATE EXTENSION`, `CREATE TABLE` e `CREATE INDEX` não podem rodar dentro de uma transação no PostgreSQL. A conexão de `init_db()` usa `autocommit` e é fechada imediatamente após. Todas as queries de dados usam transações normais via `get_db()`.

**Migração automática não-destrutiva com `ALTER TABLE ADD COLUMN IF NOT EXISTS`.**
Permite que instâncias criadas antes do suporte a upload de arquivos evoluam o schema sem `docker compose down -v`. Sem ORM, sem migration runner — o DDL fica em `init_db()`.

**`halfvec` condicional para `EMBEDDING_DIM > 2000`.**
`vector` no pgvector suporta até 2000 dimensões para índices HNSW. Modelos com dimensões maiores precisam de `halfvec`. A lógica em `db.py` seleciona o tipo e a ops class automaticamente via `EMBEDDING_DIM`.

---

## Chunking e ingestão

**Recursive character text splitter sem dependências externas.**
A lógica em `src/chunker.py` é idêntica em comportamento ao `RecursiveCharacterTextSplitter` do LangChain, mas implementada em ~70 linhas. Elimina uma dependência pesada para algo que é conceitualmente simples.

**Ingestão sequencial de chunks em vez de paralela.**
O Ollama é single-thread por padrão. Requisições paralelas ficam enfileiradas de qualquer forma. Processamento sequencial é mais previsível, evita timeouts por acúmulo de requisições pendentes, e simplifica o tratamento de erros.

**Limite de 20 MB por arquivo.**
Arquivos maiores produzem centenas de chunks e podem travar o Ollama por minutos. 20 MB cobre a grande maioria de PDFs e DOCXs educacionais.

**Lazy import de `pypdf` e `python-docx` em `parsers.py`.**
As bibliotecas são importadas apenas quando o tipo de arquivo correspondente é processado. Reduz o tempo de inicialização da API e o footprint de memória base.

---

## TurboQuant e backends

**Embeddings sempre via Ollama, independente do backend de texto.**
O `llama-server` não tem API de embeddings compatível de forma simples. Separar as responsabilidades simplifica o código: Ollama → embeddings, backend configurável → geração de texto.

**Estado de backend e TurboQuant em memória (reset no restart).**
Ambos são configurações de sessão de experimento, não configuração persistente. Reiniciar o servidor volta ao estado padrão deliberadamente — comportamento esperado para uso educacional/laboratorial.

**Fórmula KV Cache baseada na arquitetura do Gemma 3 12B.**
`tokens × 2 × hidden_dim × layers × bytes_per_value`, onde `hidden_dim = head_dim(256) × num_kv_heads(8) = 2048` e `layers = 48`. Os valores são hardcoded para Gemma 3 12B porque é o modelo de referência do projeto. A fórmula é exibida nos docs como material educacional. Se outro modelo for usado, as métricas de memória estarão erradas — isso é limitação conhecida e documentada, não bug.

**Métricas TurboQuant com backend llama.cpp são estimativas.**
O llama-server expõe `prompt_tokens` e `completion_tokens` via `usage` no chunk final, mas não separa `prompt_eval_duration` de `eval_duration`. O campo `eval_duration` recebe o tempo total de inferência como aproximação. Os valores de `tokens_per_sec` e `memory_reduction` são calculados corretamente, mas `prompt_eval_ms` sempre aparece como `0` para llama.cpp.

**Ring buffer de 50 registros para métricas TurboQuant.**
Sem banco, sem disco. `collections.deque(maxlen=50)` garante que métricas antigas sejam descartadas automaticamente — zero risco de memory leak em sessões longas.

---

## Non-Functional Requirements

### Segurança

| Requisito | Decisão | Status |
|-----------|---------|--------|
| Container não-root | `USER appuser` no Dockerfile — processo uvicorn roda sem privilégios root | ✅ |
| Dependências sem CVEs conhecidos | `pip-audit` no CI via `vet-sca-reusable.yml`; Dependabot ativo | ✅ |
| Sem segredos em código | TruffleHog no git history via `trufflehog.yml` | ✅ |
| SAST sem findings blocking | Semgrep `auto` ruleset em todo push/PR via `cicd.semgrep-reusable.yml` | ✅ |
| SQL Injection (DDL) | Constantes de módulo com nosemgrep documentado — DDL não parametrizável no PostgreSQL | ✅ falso positivo documentado |
| Prompt injection (LLM01) | Sistema instrui o modelo a usar apenas o contexto; sem sanitização de conteúdo recuperado | ⚠️ aceito para projeto educacional |
| Autenticação | Sem autenticação — todos os endpoints públicos | ⚠️ aceito — deploy local |
| Upload de arquivos maliciosos | Limite de 20 MB; extensões restritas a `{pdf,docx,md,txt}`; deps atualizadas | ✅ parcialmente |

### Performance

| Requisito | Decisão |
|-----------|---------|
| Ingestão não bloqueia servidor | Processamento sequencial de chunks em threadpool do FastAPI |
| Streaming SSE sem buffering | Header `X-Accel-Buffering: no` |
| Connection pool limitado | `maxconn=5` no `ThreadedConnectionPool` |
