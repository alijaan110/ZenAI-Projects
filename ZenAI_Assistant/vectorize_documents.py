import os
from langchain_community.document_loaders import (
    UnstructuredFileLoader,
    DirectoryLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredExcelLoader,
    CSVLoader,
    JSONLoader
)
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

# Loading the embedding model
embeddings = HuggingFaceEmbeddings()

def load_documents_from_directory(directory_path="data"):
    """Load documents of various formats from directory"""
    all_documents = []
    
    # Define loaders for different file types
    file_type_loaders = {
        "*.pdf": UnstructuredFileLoader,
        "*.txt": TextLoader,
        "*.docx": UnstructuredWordDocumentLoader,
        "*.doc": UnstructuredWordDocumentLoader,
        "*.xlsx": UnstructuredExcelLoader,
        "*.xls": UnstructuredExcelLoader,
        "*.csv": CSVLoader,
    }
    
    # Load each file type
    for glob_pattern, loader_cls in file_type_loaders.items():
        try:
            loader = DirectoryLoader(
                path=directory_path,
                glob=glob_pattern,
                loader_cls=loader_cls,
                show_progress=True
            )
            docs = loader.load()
            all_documents.extend(docs)
            print(f"Loaded {len(docs)} documents matching {glob_pattern}")
        except Exception as e:
            print(f"Error loading {glob_pattern}: {str(e)}")
    
    # Handle JSON files separately (requires special handling)
    try:
        json_files = [f for f in os.listdir(directory_path) if f.endswith('.json')]
        for json_file in json_files:
            try:
                json_loader = JSONLoader(
                    file_path=os.path.join(directory_path, json_file),
                    jq_schema='.',
                    text_content=False
                )
                docs = json_loader.load()
                all_documents.extend(docs)
                print(f"Loaded JSON file: {json_file}")
            except Exception as e:
                print(f"Error loading {json_file}: {str(e)}")
    except Exception as e:
        print(f"Error processing JSON files: {str(e)}")
    
    return all_documents


# Load all documents
print("Loading documents from 'data' directory...")
documents = load_documents_from_directory("data")
print(f"Total documents loaded: {len(documents)}")

if len(documents) == 0:
    print("No documents found! Please add files to the 'data' directory.")
else:
    # Split documents into chunks
    text_splitter = CharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=500
    )
    text_chunks = text_splitter.split_documents(documents)
    print(f"Created {len(text_chunks)} text chunks")

    # Create vector database
    vectordb = Chroma.from_documents(
        documents=text_chunks,
        embedding=embeddings,
        persist_directory="vector_db_dir"
    )

    print("✅ Documents Vectorized Successfully!")
    print(f"Supported formats: PDF, TXT, DOCX, DOC, XLSX, XLS, CSV, JSON")