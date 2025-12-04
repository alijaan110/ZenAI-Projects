import os
import json

import streamlit as st
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain

from vectorize_documents import embeddings

working_dir = os.path.dirname(os.path.abspath(__file__))
config_data = json.load(open(f"{working_dir}/config.json"))
OPENAI_API_KEY = config_data["OPENAI_API_KEY"]
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY


def setup_vectorstore():
    persist_directory = f"{working_dir}/vector_db_dir"
    embedddings = HuggingFaceEmbeddings()
    vectorstore = Chroma(persist_directory=persist_directory,
                         embedding_function=embeddings)
    return vectorstore


def chat_chain(vectorstore):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0
    )
    
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 5}  # Retrieve top 5 most relevant chunks
    )
    
    memory = ConversationBufferMemory(
        llm=llm,
        output_key="answer",
        memory_key="chat_history",
        return_messages=True
    )
    
    # Strong system prompt to prevent hallucinations
    from langchain.prompts import PromptTemplate
    
    system_prompt = """You are Zen AI — a friendly, professional, and helpful assistant. 
    You provide insights about businesses using stored data, including reviews, ratings, strengths, drawbacks, recommendations, sentiment analysis, and other related information. 
    Answer clearly, accurately, and professionally.

    =====================
    GUIDELINES
    =====================

    1. **Greetings & Casual Talk**
    - Respond naturally and politely to greetings, thanks or casual conversation.
    - Examples of appropriate responses:
    * For "hello" → "Hello! I'm Zen AI, your assistant. How can I help you today?"
    * For "thanks" → you must say: "You're welcome! Is there anything else I can help with?"
    * For "welcome" → "Thanks for being here! What would you like to know?"
    2. **Business Insights**
    - Only answer using the information in your stored business data.
    - Provide concise, structured, and clear responses.
    - Use bullet points or short paragraphs for clarity.
    - If information is missing, respond: "I don’t have that information."

    3. **Avoid Hallucinations**
    - Never guess or invent facts.
    - Do not add external knowledge.
    - If unsure, respond: "I’m not sure based on the information I have."

    4. **Out-of-Scope Questions**
    - For unrelated questions, respond: "I can’t provide an answer to that."

    5. **Answer Quality**
    - Do not repeat previous answers; provide new or concise responses based on the user’s query
    - Always read and understand the user’s question thoroughly before responding.
    - Highlight key insights, trends, or recommendations when relevant.
    - Keep responses concise, professional, and easy to read.

Context:
{context}

Chat History:
{chat_history}

User Question: {question}

Zen AI Response:"""

    qa_prompt = PromptTemplate(
        template=system_prompt,
        input_variables=["context", "chat_history", "question"]
    )
    
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        memory=memory,
        verbose=True,
        return_source_documents=True,
        combine_docs_chain_kwargs={"prompt": qa_prompt}
    )

    return chain


st.set_page_config(
    page_title="ZenAI",
    page_icon="📚",
    layout="centered"
)

st.title("🧘 Zen AI - Your Helpful Assistant")

# Add sidebar with information
# with st.sidebar:
#     st.header("📋 About Zen AI")
#     st.markdown("""
#     **Zen AI** is your intelligent document assistant that:
    
#     ✅ Answers questions **only** from your documents  
#     ✅ Never hallucinates or makes up information  
#     ✅ Provides accurate, grounded responses  
#     ✅ Clearly states when information is unavailable  
    
#     **Supported Formats:**
#     - PDF, TXT, DOCX, DOC
#     - XLSX, XLS, CSV, JSON
    
#     **Tips for best results:**
#     - Ask specific questions about your documents
#     - Reference particular topics or sections
#     - Request summaries or comparisons
#     """)
    
#     st.divider()
#     st.caption("Powered by OpenAI GPT-4o-mini")

# st.markdown("### Ask questions about your documents with confidence")
st.caption("Powered by AxeeCom, LLC")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = setup_vectorstore()

if "conversationsal_chain" not in st.session_state:
    st.session_state.conversationsal_chain = chat_chain(st.session_state.vectorstore)


for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Ask AI...")

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        response = st.session_state.conversationsal_chain({"question": user_input})
        assistant_response = response["answer"]
        st.markdown(assistant_response)
        
        # Show source documents for transparency
        # with st.expander("📚 View Source Documents"):
        #     source_docs = response.get("source_documents", [])
        #     if source_docs:
        #         for idx, doc in enumerate(source_docs[:3], 1):  # Show top 3 sources
        #             st.markdown(f"**Source {idx}:**")
        #             st.text(doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content)
        #             st.divider()
        #     else:
        #         st.info("No source documents found for this response.")
        
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_response})