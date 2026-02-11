"""
Insurance Document Intelligence - Manual Evaluation Script

Generates answers for a set of test questions and saves them to CSV
for manual review of accuracy and faithfulness.

Usage:
    python scripts/manual_evaluation.py
"""

import sys
import os
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from app.rag.chain import get_rag_chain
from app.rag.retriever import get_retriever

def run_evaluation():
    print("Initialize RAG Chain...")
    chain = get_rag_chain()
    
    # 0. Create and Ingest Sample Data
    print("Creating sample data...")
    data_dir = project_root / "data" / "uploads"
    data_dir.mkdir(parents=True, exist_ok=True)
    sample_file = data_dir / "sample_actuarial_data.xlsx"
    
    # Create a simple DataFrame and save as Excel
    df = pd.DataFrame({
        "Year": [2021, 2022, 2023],
        "IBNR": [1.2e6, 1.4e6, 1.6e6],
        "Loss_Ratio": [0.65, 0.68, 0.72],
        "Notes": [
            "Normal loss development observed.",
            "Higher frequency in Q4 due to storms.",
            "The IBNR for 2023 is determined based on the Bornhuetter-Ferguson method."
        ]
    })
    df.to_excel(sample_file, index=False)
    
    print("Ingesting sample data...")
    retriever = get_retriever()
    retriever.ingest_document(str(sample_file))
    
    # 1. Test Questions
    questions = [
        "What is the IBNR for 2023?",
        "Explain the loss development factors based on the notes.",
        "What are the key assumptions mentioned?",
        "What is the Loss Ratio for 2022?"
    ]
    
    print(f"Running generation for {len(questions)} questions...")
    
    results = []
    
    for q in questions:
        print(f"  Q: {q}")
        try:
            response = chain.invoke(q)
            
            # Format sources for CSV readability
            source_text = "\n".join([f"[{s['chunk_type']}] {s.get('text', '')[:200]}..." for s in response.sources])
            
            results.append({
                "Question": q,
                "Answer": response.answer,
                "Context": source_text,
                "Latency": "N/A" # Could measure time
            })
        except Exception as e:
            print(f"Error answering '{q}': {e}")
            results.append({
                "Question": q,
                "Answer": f"ERROR: {str(e)}",
                "Context": "",
                "Latency": ""
            })

    # 2. Save Results
    df_results = pd.DataFrame(results)
    output_file = project_root / "manual_evaluation_results.csv"
    df_results.to_csv(output_file, index=False)
    
    print(f"\nEvaluation complete!")
    print(f"Results saved to {output_file}")
    print("Please review the CSV file to verify answer quality.")

if __name__ == "__main__":
    run_evaluation()
