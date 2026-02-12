
import chromadb
import os
from pathlib import Path

def inspect_chroma():
    project_root = Path(__file__).parent.parent.resolve()
    db_path = project_root / "cache" / "chromadb"
    
    if not db_path.exists():
        print("DB_MISSING")
        return

    try:
        client = chromadb.PersistentClient(path=str(db_path))
        collection = client.get_collection("insurance_documents")
        
        # Get all documents
        results = collection.get()
        documents = results['documents']
        
        # Exact string match we expect from excel_parser.py
        target = "Cell: F24"
        
        found = False
        count = 0
        for i, doc in enumerate(documents):
            if target in doc:
                found = True
                count += 1
                source = metadatas[i].get('source', 'Unknown')
                sheet = metadatas[i].get('sheet', 'Unknown')
                print(f"\n--- MATCH {count} ---")
                print(f"Source: {source}")
                print(f"Sheet: {sheet}")
                print(f"Content:\n{doc.replace(chr(10), ' ')}")
        
        if found:
            print(f"STATUS: FOUND {count} CHUNKS")
        else:
            print("STATUS: NOT_FOUND")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    inspect_chroma()
