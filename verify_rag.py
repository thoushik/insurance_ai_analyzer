
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

def verify_imports():
    print("Verifying imports...")
    try:
        from app.vectorstore import get_embeddings, get_vector_store
        print("✅ VectorStore module imported")
        
        from app.rag import get_retriever, get_rag_chain
        print("✅ RAG module imported")
        
        from app.api.fastapi_app import app
        print("✅ FastAPI app imported")
        
        print("All imports successful!")
        return True
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def verify_embeddings():
    print("\nVerifying embeddings...")
    try:
        from app.vectorstore import get_embeddings
        model = get_embeddings()
        vec = model.embed_text("test")
        if len(vec) == 384:
            print("✅ Embeddings generated successfully (384 dimensions)")
            return True
        else:
            print(f"❌ Embeddings has wrong dimension: {len(vec)}")
            return False
    except Exception as e:
        print(f"❌ Embedding Error: {e}")
        return False

if __name__ == "__main__":
    if verify_imports():
        verify_embeddings()
