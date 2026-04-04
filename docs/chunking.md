# Chunking — Divisao de Texto

## Por que dividir documentos em chunks?

Os modelos de embedding tem um limite de tokens por entrada (tipicamente 512 tokens para modelos leves). Documentos maiores que esse limite precisam ser divididos. Alem disso, chunks menores tendem a produzir embeddings mais precisos — um vetor que representa um paragrafo focado e mais discriminativo do que um vetor que representa um documento inteiro.

O ideal e que cada chunk contenha **uma ideia coesa**: um paragrafo, uma secao, uma resposta a uma pergunta.

---

## A estrategia deste projeto: Recursive Character Splitter

O algoritmo tenta dividir no separador mais "natural" possivel, em cascata:

```
1. \n\n  (paragrafo em branco)     — separador preferido
2. \n    (quebra de linha)
3. ". "  (fim de sentenca)
4. " "   (espaco entre palavras)   — ultimo recurso
```

Para cada nivel, o algoritmo so desce para o proximo separador se o chunk ainda estiver acima do tamanho maximo. Isso preserva a estrutura logica do texto o maximo possivel.

### Exemplo

Texto original (simplificado):

```
Machine learning permite que computadores aprendam padroes a partir de dados.
O aprendizado pode ser supervisionado ou nao supervisionado.

Redes neurais sao compostas por camadas de neuronios artificiais.
Cada camada transforma a entrada de uma forma especifica.
```

Com `chunkSize=120` e `overlap=20`:

```
Chunk 0: "Machine learning permite que computadores aprendam padroes a partir de dados.\n
          O aprendizado pode ser supervisionado ou nao supervisionado."

Chunk 1: "nao supervisionado.\n\nRedes neurais sao compostas por camadas de neuronios."
          ^─── overlap ───^

Chunk 2: "por camadas de neuronios artificiais.\nCada camada transforma a entrada..."
          ^─── overlap ───^
```

O overlap garante que ideias que estao na fronteira entre dois chunks nao se percam — o contexto final do chunk anterior aparece no inicio do proximo.

---

## Parametros

### `chunkSize` (padrao: 1000 caracteres)

Tamanho maximo de cada chunk em **caracteres** (nao tokens). O modelo `embeddinggemma:latest` suporta ate 512 tokens; 1000 caracteres em portugues/ingles corresponde aproximadamente a 200-300 tokens, deixando margem confortavel.

| Valor | Efeito |
|-------|--------|
| Menor (ex: 400) | Chunks mais precisos e focados, mais chamadas de embedding |
| Maior (ex: 2000) | Mais contexto por chunk, risco de diluir o significado |

Para perguntas factuais curtas (datas, nomes, definicoes), chunks menores (~400) tendem a recuperar melhor. Para perguntas que precisam de contexto amplo (resumos, comparacoes), chunks maiores (~1500) sao melhores.

### `overlap` (padrao: 150 caracteres)

Quantos caracteres do final de um chunk sao repetidos no inicio do proximo.

| Valor | Efeito |
|-------|--------|
| 0 | Sem overlap — ideias na fronteira podem ser perdidas |
| 10-20% do chunkSize | Recomendado — preserva contexto sem duplicar demais |
| >30% do chunkSize | Muita repeticao, aumenta custos de embedding desnecessariamente |

---

## Tipos de arquivo e suas particularidades

### PDF

`pdf-parse` extrai o texto linearizado do PDF. A qualidade depende de como o PDF foi gerado:

- **PDFs gerados digitalmente** (Word exportado, LaTeX) → excelente qualidade de texto
- **PDFs escaneados** (imagens de paginas) → texto nao e extraido (seria necessario OCR)
- **PDFs com colunas multiplas** → a ordem de leitura pode ser incorreta

### DOCX

`mammoth` extrai o texto bruto, sem formatacao. Tabelas e listas sao convertidas para texto plano. O resultado e geralmente de boa qualidade.

### Markdown

O arquivo e lido como texto puro. A sintaxe markdown (` # `, `**`, `- `) e preservada nos chunks. Isso e intencional — os separadores de paragrafo (`\n\n`) ainda funcionam corretamente na maioria dos arquivos `.md`.

### TXT

Leitura direta como UTF-8. Funciona com qualquer encoding que o Node.js suporte.

---

## Como ajustar os parametros

Na interface web, ao selecionar um arquivo na aba **Arquivo**, dois campos aparecem:

- **Tamanho do chunk** — valor em caracteres (padrao 1000)
- **Overlap** — valor em caracteres (padrao 150)

Via API (curl):

```bash
curl -X POST http://localhost:3000/api/upload \
  -F "file=@documento.pdf" \
  -F "chunkSize=800" \
  -F "overlap=100"
```

---

## Quantos chunks por arquivo?

Estimativa aproximada:

| Tamanho do arquivo | Chunk 1000 chars | Chunk 500 chars |
|-------------------|-----------------|----------------|
| 1 pagina (~3000 chars) | ~3 chunks | ~6 chunks |
| 10 paginas (~30000 chars) | ~30 chunks | ~60 chunks |
| 100 paginas (~300000 chars) | ~300 chunks | ~600 chunks |

Cada chunk gera uma chamada de embedding ao Ollama. Para arquivos grandes, o processo pode levar alguns minutos dependendo do hardware.

---

## Proximos passos possiveis

- **Chunking semantico**: usar o proprio embedding para detectar mudancas de topico e dividir nos pontos de ruptura semantica, em vez de apenas por contagem de caracteres.
- **Parent-child chunks**: armazenar chunks pequenos para retrieval preciso, mas passar um chunk maior (o "pai") como contexto para o LLM.
- **Metadados de pagina**: para PDFs, armazenar o numero da pagina de cada chunk para citar a fonte com precisao.
