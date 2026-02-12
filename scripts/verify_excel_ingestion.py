
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.ingestion.excel_parser import get_excel_parser

def verify_ingestion():
    print("=== VERIFYING EXCEL INGESTION COVERAGE ===")
    
    parser = get_excel_parser()
    data_dir = project_root / "data" / "uploads"
    
    if not data_dir.exists():
        print(f"Uploads folder not found: {data_dir}")
        return

    excel_files = list(data_dir.glob("*.xlsx"))
    print(f"Found {len(excel_files)} Excel files.")
    
    for file_path in excel_files:
        print(f"\nProcessing: {file_path.name}")
        try:
            chunks = parser.to_chunks(file_path)
            
            # Analyze chunks
            sheet_counts = {}
            total_formulas = 0
            
            for chunk in chunks:
                meta = chunk.get("metadata", {})
                sheet = meta.get("sheet", "Unknown")
                c_type = meta.get("chunk_type", "unknown")
                
                if c_type == "formula":
                    sheet_counts[sheet] = sheet_counts.get(sheet, 0) + 1
                    total_formulas += 1
                    
                    # Verify content format
                    if "Value:" not in chunk["text"]:
                        print(f"WARNING: Chunk missing 'Value:' field: {chunk['text'][:50]}...")
            
            print(f"  Total Chunks: {len(chunks)}")
            print(f"  Formula Chunks: {total_formulas}")
            print("  Chunks per Sheet:")
            for sheet, count in sheet_counts.items():
                print(f"    - {sheet}: {count}")
                
            # Check for HindsightIBNR specifically if in filename
            if "Hindsight" in file_path.name:
                if "HindsightIBNR" in sheet_counts:
                    print("  [SUCCESS] HindsightIBNR sheet found.")
                else:
                    print("  [FAILURE] HindsightIBNR sheet NOT found in chunks!")
                    
        except Exception as e:
            print(f"  ERROR processing file: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    verify_ingestion()
