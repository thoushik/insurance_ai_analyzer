
import os
import openpyxl
from pathlib import Path

def debug_excel_content():
    # Calculate paths
    project_root = Path(__file__).parent.parent.resolve()
    uploads_dir = project_root / "data" / "uploads"
    
    print(f"Scanning uploads in: {uploads_dir}")
    
    if not uploads_dir.exists():
        print("Uploads directory not found.")
        return

    excel_files = list(uploads_dir.glob("*.xlsx"))
    print(f"Found {len(excel_files)} Excel files.")
    
    for string_path in excel_files:
        print(f"\nChecking file: {string_path.name}")
        try:
            wb = openpyxl.load_workbook(string_path, data_only=False)
            
            # Look for Hindsight IBNR sheet (fuzzy match)
            target_sheet = None
            for name in wb.sheetnames:
                if "hindsight" in name.lower() and "ibnr" in name.lower():
                    target_sheet = wb[name]
                    print(f"  Found target sheet: {name}")
                    break
            
            if target_sheet:
                # Check F24
                cell = target_sheet["F24"]
                print(f"  Cell F24 Content: {cell.value}")
                print(f"  Cell F24 Type: {type(cell.value)}")
                
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    print("  -> It IS a formula.")
                else:
                    print("  -> It is NOT a formula (Value/Input).")
            else:
                print("  'Hindsight IBNR' sheet not found in this workbook.")
                
            wb.close()
            
        except Exception as e:
            print(f"  Error reading file: {e}")

if __name__ == "__main__":
    debug_excel_content()
