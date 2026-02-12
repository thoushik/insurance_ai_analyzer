
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.vectorstore import get_vector_store
from app.rag.retriever import get_retriever

def diagnose():
    print("=== DIAGNOSING RETRIEVAL SYSTEM ===")
    
    # 1. Check Vector Store
    try:
        vs = get_vector_store()
        count = vs.collection.count()
        print(f"Total Chunks in DB: {count}")
        
        if count == 0:
            print("CRITICAL: Database is empty! Ingestion failed or hasn't run.")
            return
            
        # 2. Check Sources and Types
        print("\nChecking chunk distribution...")
        sample = vs.collection.get(limit=100, include=["metadatas"])
        types = {}
        for m in sample['metadatas']:
            t = m.get('chunk_type', 'unknown')
            types[t] = types.get(t, 0) + 1
        print(f"Sample Chunk Types: {types}")

        retriever = get_retriever()

        # 3. Test "Executive Summary"
        query1 = "provide an Executive Summary"
        print(f"\n--- Test Query 1: '{query1}' ---")
        results1 = retriever.retrieve(query1, k=5)
        print(f"Results returned: {len(results1)}")
        for i, res in enumerate(results1):
            print(f"  {i+1}. [{res.chunk_type}] Source: {res.source} | Score: {res.relevance_score:.4f}")
            print(f"     Text: {res.text[:100]}...")

        # 4. Test "Cell G26"
        query2 = "formula in cell G26 of the Hindsight IBNR sheet"
        print(f"\n--- Test Query 2: '{query2}' ---")
        results2 = retriever.retrieve(query2, k=5)
        print(f"Results returned: {len(results2)}")
        for i, res in enumerate(results2):
            print(f"  {i+1}. [{res.chunk_type}] Source: {res.source} | Score: {res.relevance_score:.4f}")
            print(f"     Text: {res.text[:100]}...")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose()
