
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.rag.chain import get_rag_chain

def load_env():
    env_path = project_root / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ[key] = value

def verify_response_format():
    load_env()
    print("=== VERIFYING RAG RESPONSE FORMAT ===")
    
    chain = get_rag_chain()
    
    # Test 1: Excel Analysis
    print("\n--- Test 1: Excel Analysis (Formula Breakdown) ---")
    excel_query = "Analyze the formula in cell G26 of Hindsight IBNR"
    excel_response = chain.invoke(excel_query, k=5)
    print(f"Query: {excel_query}")
    print("Response Preview:")
    print(excel_response.answer[:500])
    
    if "**Formula Breakdown:**" in excel_response.answer:
        print("\n[SUCCESS] Structured Excel headers found.")
    else:
        print("\n[FAILURE] Structured Excel headers NOT found.")

    # Test 2: PDF Citations
    print("\n--- Test 2: PDF Citations (Exact Page) ---")
    pdf_query = "What does the survey say about underwriting?"
    pdf_response = chain.invoke(pdf_query, k=5)
    print(f"Query: {pdf_query}")
    print("Response Preview:")
    print(pdf_response.answer[:500])
    
    if "(Source:" in pdf_response.answer and ", Page " in pdf_response.answer:
        print("\n[SUCCESS] Exact PDF citation format found.")
    elif "[Source" in pdf_response.answer:
        print("\n[FAILURE] Still using [Source N] format!")
    else:
        print("\n[WARNING] No citations found.")

if __name__ == "__main__":
    verify_response_format()
