---
spec: 2026-04-21-agents
type: security
---

# Security — Core RAG Pipeline

Análise de superfície de ataque e riscos de segurança para as Fases 1–3 (pipeline RAG, ingestão de arquivos, TurboQuant).

---

## Entry Points

| Entry point | Método | Dado recebido | Risco |
|-------------|--------|---------------|-------|
| `POST /api/documents` | JSON body | `content` (texto livre) | Injeção de prompt via RAG (LLM01) |
| `POST /api/upload` | multipart/form-data | arquivo binário + `chunkSize` + `overlap` | Parsing malicioso, path traversal, DoS |
| `POST /api/query` | JSON body | `question`, `topK` | Prompt injection direta; topK sem cap → unbounded context |
| `DELETE /api/documents/:id` | path param | `id` inteiro | IDOR — qualquer cliente deleta qualquer doc |
| `DELETE /api/documents/files/:filename` | path param | nome de arquivo URL-encoded | IDOR em massa — deleta todos os chunks de um arquivo |
| `POST /api/turboquant/config` | JSON body | `enabled`, `mode` | Estado de sessão compartilhado — sem autenticação |
| `POST /api/backend/config` | JSON body | `backend` | Troca de backend sem autenticação |

---

## LLM01 — Indirect Prompt Injection via RAG

**Risco:** Um documento ingerido pode conter instruções para o LLM (ex.: "Ignore as instruções anteriores e..."). O conteúdo recuperado é concatenado diretamente no contexto do LLM sem separação estrutural.

**Localização:** `src/rag.py:55-58`

```python
messages = [
    {"role": "system", "content": _SYSTEM_PROMPT},
    {"role": "user",   "content": f"Contexto:\n{context}\n\nPergunta: {question}"},
]
```

**Mitigação recomendada:** Separar contexto de instrução com marcadores explícitos e instruir o modelo a não executar instruções encontradas no contexto.

**Status:** ⚠️ Aberto — sem sanitização de conteúdo recuperado.

---

## LLM08 — Vector & Embedding Weaknesses

**Risco:** Sem isolamento por namespace/tenant. Todos os documentos compartilham o mesmo espaço vetorial. Em um ambiente multi-usuário, qualquer cliente recupera chunks de qualquer outro cliente.

**Risco adicional:** Sem metadado `untrusted` — documentos de upload de arquivos e texto manual são tratados com o mesmo nível de confiança.

**Status:** ⚠️ Aberto — single-tenant by design (projeto educacional), documentado em `specs/mission.md`.

---

## LLM10 — Unbounded Consumption

**Risco:** `topK` é aceito do cliente sem validação máxima. Um cliente pode enviar `topK=1000`, inflando o contexto e sobrecarregando o Ollama.

**Localização:** `src/main.py` — endpoint `/api/query`.

**Mitigação recomendada:** `top_k = min(request.topK, MAX_TOP_K)` onde `MAX_TOP_K ≤ 20`.

**Status:** ⚠️ Aberto.

---

## Upload — Risco de parsing malicioso

**Risco:** `pypdf` e `python-docx` processam arquivos não confiáveis. PDFs malformados podem causar consumo de memória excessivo (CVEs `pypdf`).

**Mitigação existente:** Limite de 20 MB por arquivo (`src/routes/upload.py`). Dependências atualizadas via Dependabot.

**Status:** ✅ Mitigado parcialmente — tamanho limitado, deps atualizadas.

---

## Ausência de autenticação

**Risco:** Todos os endpoints são públicos. Qualquer pessoa com acesso à rede pode ingerir, deletar e consultar documentos, e alterar configurações de backend/TurboQuant.

**Status:** ⚠️ Aceito — projeto educacional, deploy local. Não planejado para Fases 1–3.

---

## Dockerfile — processo root

**Risco:** Container rodava como root. Escalada de privilégios via exploit do processo.

**Mitigação aplicada:** `adduser appuser` + `USER appuser` no Dockerfile.

**Status:** ✅ Corrigido em 2026-04-21.

---

## SQL Injection (DDL)

**Risco:** `_col_type` e `_ops_class` são interpolados em DDL. Valores derivados de `EMBEDDING_DIM` (integer validado) e flag binária — não de input do usuário.

**Localização:** `src/db.py:23-47` — constantes de módulo com `# nosemgrep` documentado.

**Status:** ✅ Falso positivo documentado e suprimido.
