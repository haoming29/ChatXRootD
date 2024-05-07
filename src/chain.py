import os
from typing import List, Dict

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnablePassthrough,
    RunnableParallel,
)
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


llm = ChatOpenAI(model="gpt-3.5-turbo-0125")

vectorstore = FAISS.load_local(
    folder_path=os.path.join(os.getcwd(), "embeddings"),
    embeddings=OpenAIEmbeddings(),
    allow_dangerous_deserialization=True,
)

# Retrieve and generate using the relevant snippets of the blog.
retriever = vectorstore.as_retriever(search_type="mmr")
# prompt = hub.pull("rlm/rag-prompt")

template = """You are an assistant for question-answering tasks.
You will be asked questions about XRootD, or eXtended Request Daemon.
Use the following pieces of retrieved context to answer the question.
Use your existing knowledge to answer the question if the retrieved context
does not contain useful information.
Do not mention the context to the user. Do now let user know you are given a retrieved context.
If the user is asking questions irrelavent to XRootD or simply chat with you on random topics, answer them based on your existing knowledge.
If you don't know the answer or nothing is provided in the context, just say: Sorry, I don't know.

{context}

Question: {question}

Answer:"""
custom_rag_prompt = PromptTemplate.from_template(template)


def format_docs(docs: List[Document]):
    return "\n\n".join(doc.page_content for doc in docs)


def extract_sources(docs: List[Document]):
    sources = []
    for doc in docs:
        sources.append(doc.metadata.get("source"))
    return sources


rag_chain_from_docs = (
    RunnablePassthrough.assign(context=(lambda x: format_docs(x["context"])))
    | custom_rag_prompt
    | llm
    | StrOutputParser()
)

rag_chain_with_source = RunnableParallel(
    {"context": retriever, "question": RunnablePassthrough()}
).assign(answer=rag_chain_from_docs)


def answer_question(question: str) -> Dict:
    answer = rag_chain_with_source.invoke(question)
    answer["context"] = extract_sources(answer["context"])
    return answer
