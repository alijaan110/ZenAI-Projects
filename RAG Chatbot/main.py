# Minimal FastAPI RAG Chatbot - 3 Files Only
# Structure:
# rag-chatbot/
# ├── main.py
# ├── requirements.txt
# ├── .env
# └── data/  (your documents)

# ============================================================================
# File: main.py
# ============================================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import json
from pathlib import Path
import openai
from dotenv import load_dotenv
import PyPDF2
from docx import Document
import pandas as pd
import chromadb
from chromadb.config import Settings

load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHUNK_SIZE = 1000
TOP_K = 3
DATA_DIR = "./data"
CHROMA_DIR = "./chroma_db"

openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = None

# Global Storage
conversations = {}

# Strong System Prompt to Control Hallucination
SYSTEM_PROMPT = """You are a precise and accurate AI assistant. Follow these rules strictly:

1. **ONLY use information from the provided context** to answer questions.
2. **DO NOT make up, infer, or assume information** that is not explicitly stated in the context.
3. **If the context does not contain enough information** to answer the question, you MUST respond with: "I don't have enough information in the provided documents to answer this question accurately."
4. **Quote or reference the source** when possible to show where information came from.
5. **Do not use your general knowledge** - only rely on the context provided.
6. **Be specific and factual** - avoid vague or generic responses.
7. **If asked about something not in the context**, politely state that the information is not available in the documents.
8. **Never fabricate data, statistics, names, dates, or facts** that aren't in the context.

Remember: It's better to say "I don't know based on the provided documents" than to provide incorrect or hallucinated information."""

# Pydantic Models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"

class ChatResponse(BaseModel):
    response: str
    sources: Optional[List[str]] = None

# File Parsers
def parse_file(file_path: Path) -> str:
    ext = file_path.suffix.lower()
    try:
        if ext in ['.txt', '.md']:
            return file_path.read_text(encoding='utf-8')
        elif ext == '.json':
            return json.dumps(json.loads(file_path.read_text()), indent=2)
        elif ext == '.pdf':
            with open(file_path, 'rb') as f:
                return "\n".join([page.extract_text() for page in PyPDF2.PdfReader(f).pages])
        elif ext == '.docx':
            return "\n".join([p.text for p in Document(file_path).paragraphs])
        elif ext == '.csv':
            df = pd.read_csv(file_path)
            return df.to_string(index=False)
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path, sheet_name=None)
            result = []
            for sheet_name, sheet_df in df.items():
                result.append(f"Sheet: {sheet_name}\n{sheet_df.to_string(index=False)}")
            return "\n\n".join(result)
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    return ""

# Chunking
def chunk_text(text: str, source: str) -> List[Dict]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append({"content": chunk, "source": source})
    return chunks

# Embeddings
def get_embeddings(texts: List[str]) -> List[List[float]]:
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in response.data]

# ChromaDB Functions
def build_vector_store():
    global collection
    
    # Delete existing collection if exists
    try:
        chroma_client.delete_collection("documents")
    except:
        pass
    
    # Create new collection
    collection = chroma_client.create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"}
    )
    
    # Load documents
    all_chunks = []
    for file_path in Path(DATA_DIR).rglob('*'):
        if file_path.suffix.lower() in ['.txt', '.md', '.json', '.pdf', '.docx', '.csv', '.xlsx', '.xls']:
            content = parse_file(file_path)
            if content:
                all_chunks.extend(chunk_text(content, str(file_path)))
    
    if not all_chunks:
        print("⚠️  No documents found in data/ directory!")
        return
    
    # Create embeddings and add to ChromaDB
    texts = [chunk["content"] for chunk in all_chunks]
    sources = [chunk["source"] for chunk in all_chunks]
    ids = [f"doc_{i}" for i in range(len(texts))]
    
    # Add in batches (ChromaDB has batch size limits)
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_sources = sources[i:i + batch_size]
        batch_ids = ids[i:i + batch_size]
        
        # Get embeddings for batch
        batch_embeddings = get_embeddings(batch_texts)
        
        # Add to collection
        collection.add(
            documents=batch_texts,
            embeddings=batch_embeddings,
            metadatas=[{"source": src} for src in batch_sources],
            ids=batch_ids
        )
    
    print(f"✅ Indexed {len(all_chunks)} chunks from {len(list(Path(DATA_DIR).rglob('*')))} files")

def load_vector_store():
    global collection
    try:
        collection = chroma_client.get_collection("documents")
        doc_count = collection.count()
        print(f"✅ Loaded ChromaDB collection with {doc_count} documents")
        return doc_count > 0
    except:
        print("⚠️  No existing vector store found")
        return False

def search_similar(query: str, k: int = TOP_K) -> List[Dict]:
    if not collection:
        return []
    
    try:
        query_emb = get_embeddings([query])[0]
        
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=k
        )
        
        similar_docs = []
        if results['documents'] and results['documents'][0]:
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                similar_docs.append({
                    "content": doc,
                    "source": metadata.get("source", "unknown")
                })
        
        return similar_docs
    except Exception as e:
        print(f"Error searching: {e}")
        return []

# Chat Function with Strong Anti-Hallucination Measures
def chat_with_rag(message: str, session_id: str) -> Dict:
    # Retrieve context
    similar_docs = search_similar(message)
    
    if not similar_docs:
        return {
            "response": "I don't have any relevant information in my document database to answer your question. Please ensure documents are ingested first.",
            "sources": []
        }
    
    context = "\n\n---\n\n".join([f"Source: {doc['source']}\nContent: {doc['content']}" for doc in similar_docs])
    sources = list(set([doc["source"] for doc in similar_docs]))
    
    # Build conversation history
    if session_id not in conversations:
        conversations[session_id] = []
    
    history = conversations[session_id][-6:]  # Last 3 turns
    
    # Create messages with strong anti-hallucination prompt
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Here is the context from the documents:\n\n{context}\n\nRemember: ONLY answer based on this context. If the answer is not in the context, say so clearly."},
        *history,
        {"role": "user", "content": message}
    ]
    
    # Get response
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # Using gpt-4o-mini as requested
        messages=messages,
        temperature=0.1,  # Lower temperature for more factual responses
        max_tokens=800
    )
    
    assistant_msg = response.choices[0].message.content
    
    # Update history (without system messages)
    conversations[session_id].append({"role": "user", "content": message})
    conversations[session_id].append({"role": "assistant", "content": assistant_msg})
    
    return {"response": assistant_msg, "sources": sources}

# FastAPI App
app = FastAPI(title="RAG Chatbot", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    print("🚀 Starting RAG Chatbot...")
    if not load_vector_store():
        print("📚 Building vector store from data/ directory...")
        if Path(DATA_DIR).exists():
            build_vector_store()
        else:
            print(f"⚠️  Creating {DATA_DIR} directory - please add your documents there")
            Path(DATA_DIR).mkdir(exist_ok=True)

@app.get("/")
async def root():
    doc_count = collection.count() if collection else 0
    return {
        "status": "running",
        "model": "gpt-4o-mini",
        "vector_db": "ChromaDB",
        "documents_indexed": doc_count,
        "supported_formats": [".txt", ".md", ".json", ".pdf", ".docx", ".csv", ".xlsx", ".xls"],
        "endpoints": {
            "chat": "POST /chat",
            "ingest": "POST /ingest",
            "health": "GET /health",
            "docs": "GET /docs"
        }
    }

@app.post("/ingest")
async def ingest():
    """Rebuild vector store from data/ directory"""
    try:
        build_vector_store()
        doc_count = collection.count() if collection else 0
        return {
            "status": "success",
            "documents": doc_count,
            "message": f"Successfully indexed documents from {DATA_DIR}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with RAG - answers ONLY from your documents"""
    try:
        if not collection or collection.count() == 0:
            raise HTTPException(
                status_code=400,
                detail="No documents indexed. Please add documents to data/ folder and call POST /ingest"
            )
        
        result = chat_with_rag(request.message, request.session_id)
        return ChatResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    doc_count = collection.count() if collection else 0
    return {
        "status": "healthy",
        "documents_indexed": doc_count,
        "vector_store_loaded": collection is not None,
        "model": "gpt-4o-mini",
        "database": "ChromaDB"
    }

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session"""
    if session_id in conversations:
        del conversations[session_id]
    return {"status": "cleared", "session_id": session_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)