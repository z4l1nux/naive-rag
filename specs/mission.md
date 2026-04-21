# Mission

## Propósito

naive-rag é uma **referência educacional** de pipeline RAG completo, rodando inteiramente local — sem nenhuma API externa paga.

O objetivo é mostrar, com código legível e sem mágica, como cada peça de um sistema RAG funciona: chunking, embeddings, busca vetorial, geração com streaming. Clareza e simplicidade têm precedência sobre otimizações prematuras.

## Princípios

- **Local-first** — tudo roda na sua máquina. Sem OpenAI, sem custos por token, sem dados saindo do ambiente.
- **Explícito sobre implícito** — cada módulo faz uma coisa e a faz de forma óbvia. O código é o documento.
- **Zero abstrações desnecessárias** — sem frameworks de orquestração (LangChain, LlamaIndex). A pipeline está visível em `src/rag.py`.
- **Experimental por natureza** — é um laboratório pessoal. Novas técnicas (quantização, reranking) entram como experimentos, não como features de produto.

## O que este projeto não é

- Não é um produto para usuários finais.
- Não é um template production-ready para escalar a múltiplos usuários.
- Não tem SLA, versionamento de API estável ou suporte.

## Artefatos educacionais

| Arquivo | Propósito |
|---------|-----------|
| `rag.py` (raiz) | Script original — RAG mínimo com embeddings em memória |
| `rag.ipynb` | Notebook explorável passo a passo |
| `src/` | Aplicação web completa como extensão natural dos scripts acima |
