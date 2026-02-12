
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.rag.retriever import get_retriever

def verify_context():
    print("=== VERIFYING CONTEXT STRING FORMATTING ===")
    
    retriever = get_retriever()
    
    # Use a query likely to hit a PDF
    query = "Executive Summary"
    
    print(f"Query: {query}")
    results = retriever.retrieve(query, k=5)
    
    print(f"Retrieved {len(results)} chunks.")
    
    context = retriever.get_context_string(query, k=5)
    
    print("\n--- Context String Preview ---")
    print(context[:1000])
    
    if "Page:" in context:
        print("\n[SUCCESS] 'Page:' found in context string.")
    else:
        print("\n[FAILURE] 'Page:' NOT found in context string (or no PDF chunks retrieved).")
        # Check if any PDF chunks were retrieved
        pdf_chunks = [r for r in results if r.chunk_type != "excel"]
        if not pdf_chunks:
            print("  (Note: No PDF chunks were found, so Page info wouldn't appear regardless)")

if __name__ == "__main__":
    verify_context()
