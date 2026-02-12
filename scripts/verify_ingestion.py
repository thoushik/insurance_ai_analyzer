
"""
Utility script to verify ingested documents and sheets.
Run this to see what files the system knows about.
"""
import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv

def verify_ingestion():
    load_dotenv()
    
    print("\n" + "="*60)
    print("VERIFYING INGESTED DOCUMENTS & SHEETS")
    print("="*60)
    
    try:
        from app.ingestion import get_document_registry
        registry = get_document_registry()
        
        if not registry.documents:
            print("No documents found in registry.")
            return

        print(f"Total Documents: {len(registry.documents)}\n")
        
        for doc_id, entry in registry.documents.items():
            print(f"📄 Document: {entry.filename}")
            print(f"   ID: {doc_id}")
            print(f"   Type: {entry.doc_type}")
            
            if entry.doc_type == "excel":
                sheets = entry.metadata.get("sheets", [])
                print(f"   Sheets ({len(sheets)}):")
                for s in sheets:
                    s_name = s.get("name") if isinstance(s, dict) else s.name
                    print(f"    - {s_name}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Error accessing registry: {e}")

if __name__ == "__main__":
    verify_ingestion()
