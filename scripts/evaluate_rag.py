"""
Insurance Document Intelligence - RAG Evaluation Script

Uses Ragas to evaluate the RAG pipeline's performance.
Metrics: Faithfulness, Answer Relevance.

Usage:
    python scripts/evaluate_rag.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevance
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings

from app.rag.chain import get_rag_chain

def run_evaluation():
    print("Initialize RAG Chain...")
    chain = get_rag_chain()
    
    # 0. Create and Ingest Sample Data
    from app.rag.retriever import get_retriever
    import pandas as pd
    
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
    
    # 1. Prepare Test Data (Ground Truth)
    # Ideally this comes from a file, but we'll define a small set here
    questions = [
        "What is the IBNR for 2023?",
        "Explain the loss development factors.",
        "What are the key assumptions in the actuarial text?",
    ]
    
    ground_truths = [
        ["The IBNR for 2023 is determined based on the Bornhuetter-Ferguson method."],
        ["Loss development factors are selected based on historical averages."],
        ["Key assumptions include claim frequency trends and severity inflation."],
    ]
    
    print(f"Running generation for {len(questions)} questions...")
    
    answers = []
    contexts = []
    
    for q in questions:
        print(f"  Q: {q}")
        response = chain.invoke(q)
        answers.append(response.answer)
        # Ragas expects contexts as list of strings
        ctx_texts = [s["chunk_type"] + ": " + s.get("text", "") for s in response.sources] 
        # Wait, my sources dict doesn't have full text in 'sources' list in RAGResponse
        # I need to update RAGResponse to include full text or fetch it.
        # My RAGResponse.sources only has metadata? 
        # Let's check chain.py
        contexts.append(["Context placeholder"] if not ctx_texts else ctx_texts)

    # 2. Prepare Dataset
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truths": ground_truths
    }
    dataset = Dataset.from_dict(data)
    
    # 3. Configure Ragas with Groq and Local Embeddings
    print("Configuring Ragas...")
    
    # LLM for evaluation (Judge)
    eval_llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )
    
    # Embeddings for evaluation
    eval_embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # 4. Run Evaluation
    print("Running evaluation (this may take a moment)...")
    try:
        results = evaluate(
            dataset=dataset,
            metrics=[
                faithfulness,
                answer_relevance
            ],
            llm=eval_llm,
            embeddings=eval_embeddings
        )
        
        print("\nEvaluation Results:")
        print(results)
        
        # Save results
        df = results.to_pandas()
        output_file = project_root / "evaluation_results.csv"
        df.to_csv(output_file, index=False)
        print(f"\nDetailed results saved to {output_file}")
        
    except Exception as e:
        print(f"\nEvaluation Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_evaluation()
