
import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv

def debug_retrieval():
    load_dotenv()
    
    print("\n" + "="*50)
    print("TESTING DETERMINISTIC FORMULA LOOKUP (METADATA ONLY)")
    print("="*50)
    
    # Only import what we need for metadata verification
    from app.ingestion import get_document_registry
    
    registry = get_document_registry()
    
    # We need to find the document containing "Model 1"
    target_sheet_name = "Model 1"
    doc_id = None
    found_doc_name = None
    
    print(f"\nSearching for sheet '{target_sheet_name}'...")
    
    for d_id, entry in registry.documents.items():
        # Check metadata sheets
        meta_sheets = entry.metadata.get("sheets", [])
        for s in meta_sheets:
            if isinstance(s, dict):
                s_name = s.get("name")
            else:
                s_name = s.name
                
            if s_name == target_sheet_name:
                doc_id = d_id
                found_doc_name = entry.filename
                print(f"Found sheet '{target_sheet_name}' in document: {found_doc_name} (ID: {doc_id})")
                break
        if doc_id:
            break
            
    if doc_id:
        # We want to check if the metadata exists
        print(f"Checking metadata for doc_id {doc_id}...")
        
        # Access metadata directly from the document entry (persisted)
        entry = registry.documents[doc_id]
        metadata = entry.metadata
        
        if metadata:
            sheets = metadata.get('sheets', [])
            target_sheet = None
            for s in sheets:
                # s is a dict here since it came from JSON
                name = s.get('name')
                if name == target_sheet_name:
                    target_sheet = s
                    break
            
            if target_sheet:
                print(f"Found sheet: {target_sheet.get('name')}")
                formulas = target_sheet.get('sample_formulas', [])
                print(f"Total formulas indexed: {len(formulas)}")
                
                # Print first 5 formulas to verify metadata richness
                print("Sample formulas from index:")
                for f in formulas[:5]:
                    print(f" - Cell: {f.get('cell')}")
                    print(f"   Formula: {f.get('formula')}")
                    print(f"   Value: {f.get('value')}")
                    print(f"   Type: {f.get('data_type')}")
                    print(f"   Format: {f.get('number_format')}")
                    print("")
            else:
                print(f"Sheet '{target_sheet_name}' not found in metadata.")
                print(f"Available sheets: {[s.get('name') for s in sheets]}")
        else:
            print("Metadata not available in entry.")
    else:
        print(f"Could not find sheet '{target_sheet_name}' in any document.")
        print("Available documents and sheets:")
        for d_id, entry in registry.documents.items():
            print(f"- {entry.filename}")
            meta_sheets = entry.metadata.get("sheets", [])
            for s in meta_sheets:
                if isinstance(s, dict):
                    print(f"  - {s.get('name')}")
                else:
                    print(f"  - {s.name}")

if __name__ == "__main__":
    debug_retrieval()
