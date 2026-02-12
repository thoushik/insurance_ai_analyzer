import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.rag.retriever import get_retriever

def debug_query():
    print("Initializing retriever...")
    retriever = get_retriever()
    
    query = "Explain the formula in cell F24 of the HindsightIBNR sheet"
    print(f"\nQuery: {query}")
    
    results = retriever.retrieve(query, k=5)
    
    print(f"\nResults found: {len(results)}")
    
    if not results:
        print("No results found.")
    
    for i, res in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(f"Source: {res.source}")
        print(f"Score: {res.relevance_score}")
        print(f"Chunk Type: {res.chunk_type}")
        print(f"Content (first 200 chars): {res.text[:200]}...")

if __name__ == "__main__":
    debug_query()
