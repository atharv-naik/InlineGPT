from dotenv import load_dotenv
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_mistralai import ChatMistralAI
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain_mistralai.embeddings import MistralAIEmbeddings
from pydantic import BaseModel
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_core.documents import Document
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv(override=True)


# model = ChatMistralAI(model_name='codestral-2405')
model_local = ChatOllama(model="orca-mini")
parser = StrOutputParser()
# embeddings = MistralAIEmbeddings()
embeddings_local = OllamaEmbeddings(model="orca-mini")
vectorstore = Chroma(embedding_function=embeddings_local)
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)

system_template = (
    "You're a helpful AI. Answer the query with a factual answer."
    "If you don't know the answer or are not sure, just say 'I don't know'."
    "Be sure to use latex when needed like for mathematical equations."
    "For code snippets, use the highlight.js packages and wrap the code segments with appropriate html tags to render code blocks in html with syntax highlighting like in code editors."
    "Example code block: <pre><code class='language-python'>print('Hello World')</code></pre>"
    "Any explainations to the code blocks must stay outside the <pre> and <code> tags."
)

rag_template = """Answer the following question based on the provided context from the webpage content.:
<context>
{context}
</context>

Question: {input}"""

prompt = ChatPromptTemplate.from_messages(
    [
        SystemMessage(content=system_template),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)



runnable = prompt | model_local

store = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = ChatMessageHistory()
    return store[session_id]

chain = RunnableWithMessageHistory(
    runnable,
    get_session_history,
    input_messages_key="query",
    history_messages_key="history",
)

class MessageModel(BaseModel):
    query: str
    session_id: str

class PageContentModel(BaseModel):
    context: dict
    session_id: str


app = FastAPI()

# allow all
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# [POST] /chat/page-content/?context=webpagecontent&session_id=123
@app.post("/chat/page-content/")
async def page_content(message: PageContentModel):
    global chain, vectorstore

    pagecontext = message.context
    session_id = message.session_id

    # alter the chain for RAG

    document = [
        Document(page_content=pagecontext.get('content'), metadata={"title": pagecontext.get('title'), "source": pagecontext.get('url'), "session_id": session_id})
        ]
    splits = text_splitter.split_documents(document)
    vectorstore.add_documents(splits)

    logging.info(f"Added document: {pagecontext.get('title')}")

    retriever = vectorstore.as_retriever()

    ### Contextualize question ###
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(
        model_local, retriever, contextualize_q_prompt
    )

    ### Answer question ###
    system_prompt = (
        "You are an assistant for question-answering tasks. "
        "Answer the question based only on the following pieces of retrieved context."
        "If you don't know the answer, say that you "
        "don't know. Use three sentences maximum and keep the "
        "answer concise or elaborate if aked to."
        "Instructions for the answer format: "
        "You may use latex for mathematical equations and "
        "highlight.js for code snippets by wrapping the code segments "
        "like this -> <pre><code>some code</code></pre> tags wherever needed."
        "\n\n"
        "<context>"
        "{context}"
        "</context>"
    )
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    question_answer_chain = create_stuff_documents_chain(model_local, qa_prompt)

    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    chain = RunnableWithMessageHistory(
                rag_chain,
                get_session_history,
                input_messages_key="input",
                history_messages_key="chat_history",
                output_messages_key="answer",
            )
    
    logging.info("Chain altered for RAG")


async def handle_invoke(input, session_id, retry=2, retry_delay=60):
    import time
    while retry > 0:
        try:
            response = chain.invoke({
                "input": input,
            },
                config={"configurable": {"session_id": session_id}}
            )
            return response
        except Exception as e:
            retry -= 1
            logging.error(f"Error: {e}")
            logging.info(f"Retrying in {retry_delay} seconds")
            time.sleep(retry_delay)
    logging.error("Failed to get response")
    return False



# [POST] /chat/?query=Hello&session_id=123
@app.post("/chat/")
async def chat(message: MessageModel):
    query = message.query
    session_id = message.session_id

    response = await handle_invoke(query, session_id)
    if response: return response['answer']
    return Response(status_code=500, content="Failed to get response")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
