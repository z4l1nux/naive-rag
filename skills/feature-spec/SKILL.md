---
name: feature-spec
description: Inicia uma nova funcionalidade do roadmap criando branch, entrevistando o usuário e gerando o spec em specs/.
---

# Feature Spec

## Workflow

### 1. Identificar a próxima funcionalidade

Leia `specs/roadmap.md`. Encontre a **primeira fase que contém pelo menos um item `[ ]`** (não concluído). Extraia o nome do item para usar como slug do branch e do diretório.

Exemplo: `- [ ] Re-ranking pós-retrieval` → slug `reranking`

### 2. Criar a branch

```bash
git checkout -b YYYY-MM-DD-<slug>
```

Use a data de hoje no formato `YYYY-MM-DD`. Exemplo: `2026-04-21-reranking`.

### 3. Entrevistar o usuário (AskUserQuestion — 3 perguntas agrupadas)

Faça exatamente **3 perguntas em uma única chamada** antes de escrever qualquer arquivo:

- **Escopo** — O que entra no primeiro PR desta funcionalidade? Quais partes ficam fora?
- **Decisões** — Há restrições técnicas ou preferências já decididas? (ex.: biblioteca específica, sem novas dependências)
- **Contexto** — Há casos de uso concretos ou exemplos que devem guiar a implementação?

### 4. Ler o contexto da constituição

Leia em paralelo:
- `specs/mission.md`
- `specs/tech-stack.md`

Use o conteúdo para garantir que o spec seja coerente com os princípios e a stack existentes.

### 5. Criar o diretório de spec

```
specs/YYYY-MM-DD-<slug>/
├── plan.md          tarefas a implementar, em ordem
├── requirements.md  decisões e justificativas
└── validation.md    como verificar que funciona
```

**`plan.md`** — lista de tarefas `[ ]` ordenadas pela sequência de implementação. Cada tarefa deve referenciar o arquivo ou módulo que será criado/modificado.

**`requirements.md`** — para cada decisão não-óbvia: o que foi decidido, por que, e o que foi descartado.

**`validation.md`** — smoke tests com `curl` ou comandos concretos cobrindo o caminho feliz e os casos de erro esperados.

## Constraints
- Nunca escrever os arquivos de spec antes de completar o passo 3 (entrevista).
- As 3 perguntas devem ser enviadas em **uma única chamada** `AskUserQuestion`.
- O spec deve ser coerente com `specs/mission.md` — nada que contrarie os princípios do projeto.
- Não adicionar dependências que contradigam `specs/tech-stack.md` sem justificar em `requirements.md`.
- Não implementar código nesta skill — ela termina com os três arquivos de spec criados.
