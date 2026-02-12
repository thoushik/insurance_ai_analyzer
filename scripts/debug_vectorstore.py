import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.vectorstore import get_vector_store

def debug_query():
    print("Initializing VectorStore...")
    store = get_vector_store()
    
    query = "Explain the formula in cell F24 of the HindsightIBNR sheet"
    print(f"\nQuery: {query}")
    
    # Use raw search
    query_embedding = store.embeddings.embed_text(query)
    results = store.collection.query(
        query_embeddings=[query_embedding],
        n_results=10
    )
    
    print(f"\nResults found: {len(results['documents'][0]) if results['documents'] else 0}")
    
    if results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            dist = results['distances'][0][i]
            print(f"\n--- Result {i+1} ---")
            print(f"Source: {meta.get('source', 'Unknown')}")
            print(f"Distance: {dist}")
            print(f"Content (first 200 chars): {doc[:200]}...")

if __name__ == "__main__":
    debug_query()
