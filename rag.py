# %%
# numpy: biblioteca para operações matemáticas com vetores e matrizes
# ollama: biblioteca para usar modelos de linguagem locais (LLMs e embeddings)
import numpy as np
import ollama

# Base de conhecimento: lista de strings que o RAG vai consultar para responder perguntas.
# Em RAG (Retrieval-Augmented Generation), esses documentos são a "memória" do sistema.
documents = [
    "Machine learning é um campo da inteligência artificial que permite que computadores aprendam padrões a partir de dados.",
    "O aprendizado de máquina dá aos sistemas a capacidade de melhorar seu desempenho sem serem explicitamente programados.",
    "Em vez de seguir apenas regras fixas, o machine learning descobre relações escondidas nos dados.",
    "Esse campo combina estatística, algoritmos e poder computacional para extrair conhecimento.",
    "O objetivo é criar modelos capazes de generalizar além dos exemplos vistos no treinamento.",
    "Aplicações de machine learning vão desde recomendações de filmes até diagnósticos médicos.",
    "Os algoritmos de aprendizado de máquina transformam dados brutos em previsões úteis.",
    "Diferente de um software tradicional, o ML adapta-se conforme novos dados chegam.",
    "O aprendizado pode ser supervisionado, não supervisionado ou por reforço, dependendo do tipo de problema.",
    "Na prática, machine learning é o motor que impulsiona muitos avanços em visão computacional e processamento de linguagem natural.",
    "Mais do que encontrar padrões, o machine learning ajuda a tomar decisões baseadas em evidências.",
]

# %%
# Constantes com os nomes dos modelos usados.
# Separar em constantes facilita trocar o modelo em um único lugar.
EMBED_MODEL = "embeddinggemma:latest"  # modelo para gerar embeddings (vetores numéricos de texto)
TEXT_MODEL = "gemma4:e2b"              # modelo para gerar a resposta final em linguagem natural

# Gera os embeddings de todos os documentos da base de conhecimento.
# Um embedding é uma lista de números que representa o "significado" de um texto.
# Textos com significados parecidos terão vetores numericamente próximos.
# np.array(...) transforma a lista de listas em uma matriz NumPy (mais eficiente para cálculos).
doc_embeddings = np.array([
    # Para cada documento, pedimos ao ollama para gerar seu vetor de embedding.
    # ["embedding"] acessa o campo "embedding" do dicionário retornado pela API.
    ollama.embeddings(model=EMBED_MODEL, prompt=doc)["embedding"]
    for doc in documents  # list comprehension: percorre cada doc na lista documents
])

doc_embeddings  # exibe a matriz de embeddings no notebook

# %%
def cosine_similarity(a, b):
    """
    Calcula a similaridade de cosseno entre dois vetores.
    Retorna um valor entre -1 e 1: quanto mais próximo de 1, mais similares são os textos.

    Fórmula: cos(θ) = (a · b) / (|a| * |b|)
    - np.dot(a, b): produto escalar (soma dos produtos elemento a elemento)
    - np.linalg.norm: calcula a magnitude (comprimento) de um vetor
    """
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# %%
def retrieve(query, top_k=3):
    """
    Etapa de RECUPERAÇÃO do RAG: dado uma pergunta, encontra os documentos
    mais relevantes na base de conhecimento usando similaridade de cosseno.

    top_k=3 significa que retorna os 3 documentos mais similares por padrão.
    """
    # CORREÇÃO: era `model.encode([query])[0]` — `model` nunca foi definido.
    # Agora usamos ollama.embeddings, igual ao que foi feito para os documentos.
    # Isso converte a pergunta do usuário em um vetor numérico para poder compará-la.
    query_embedding = ollama.embeddings(model=EMBED_MODEL, prompt=query)["embedding"]

    # Lista que vai acumular pares (índice do documento, similaridade)
    similarities = []

    for i, doc_emb in enumerate(doc_embeddings):
        # enumerate retorna o índice `i` e o valor `doc_emb` a cada iteração
        sim = cosine_similarity(query_embedding, doc_emb)  # compara pergunta com documento i
        similarities.append((i, sim))                      # guarda o índice e a similaridade

    # Ordena do mais similar para o menos similar (reverse=True = decrescente)
    # key=lambda x: x[1] diz para ordenar pelo segundo elemento da tupla (a similaridade)
    similarities.sort(key=lambda x: x[1], reverse=True)

    # Retorna os top_k documentos mais relevantes com seus scores de similaridade
    # [:top_k] fatia a lista para pegar só os primeiros top_k elementos
    return [(documents[i], sim) for i, sim in similarities[:top_k]]

# %%
def generate_answer(query, retrieve_docs):
    """
    Etapa de GERAÇÃO do RAG: usa os documentos recuperados como contexto
    e pede ao LLM para gerar uma resposta fundamentada neles.

    Isso evita alucinações: o modelo só pode usar o que está no contexto.
    """
    # Une os documentos recuperados em um único bloco de texto separado por quebras de linha.
    # `doc for doc, _ in retrieve_docs`: o `_` é convenção Python para ignorar o score.
    context = "\n".join([doc for doc, _ in retrieve_docs])

    # CORREÇÃO: era `client.chat.completions.create(...)` — `client` nunca foi definido.
    # Esse era código da API da OpenAI. Aqui usamos ollama.chat, a API correta para modelos locais.
    response = ollama.chat(
        model=TEXT_MODEL,  # usa a constante definida no topo, não um valor fixo repetido
        messages=[
            {
                "role": "system",
                # Instrução que define o comportamento do modelo.
                # Limitar ao contexto é uma técnica RAG para evitar que o modelo "invente".
                "content": "Você é um especialista em machine learning. Use apenas o contexto fornecido para responder as perguntas."
            },
            {
                "role": "user",
                # CORREÇÃO: era `"context": ...` — chave inválida na API de chat.
                # A chave correta é "content", que carrega o texto da mensagem do usuário.
                "content": f"Context:\n{context}\n\nPergunta: {query}"
                # f-string: permite inserir variáveis Python dentro de uma string com {variavel}
            },
        ],
    )

    # CORREÇÃO: era `response.choices[0].message.content` — sintaxe da API da OpenAI.
    # ollama.chat retorna um dicionário. Acessamos a resposta com chaves de dicionário.
    # response["message"] é o dicionário da mensagem, e ["content"] é o texto gerado.
    return response["message"]["content"]

# %%
def rag(query, top_k=3):
    """
    Função principal que orquestra o pipeline RAG completo:
    1. retrieve: busca os documentos mais relevantes para a pergunta
    2. generate_answer: gera a resposta usando esses documentos como contexto

    Retorna a resposta gerada e os documentos que foram usados como base.
    """
    retrieved = retrieve(query, top_k)        # etapa de recuperação
    answer = generate_answer(query, retrieved) # etapa de geração
    return answer, retrieved                   # retorna ambos para fins de transparência/debug

# %%
answer, docs = rag("O que é machine learning?")
print(answer)
print(docs)

# %%
for doc, similarity in docs:
    print(f" - {similarity:.3f}: {doc}")
# %%
