"""
Insurance Document Intelligence Assistant
Evaluation Module - RAG Evaluator (Official RAGAS + Custom Embeddings)

Hybrid evaluation approach for minimal API calls:
  - faithfulness: Official RAGAS metric (LLM judge)
  - answer_relevancy: Official RAGAS metric (LLM judge)
  - context_precision: Custom embedding-based (0 LLM calls)
  - context_recall: Custom embedding-based (0 LLM calls)

Uses llama-3.1-8b-instant for evaluation (high rate limits on Groq free tier).
"""

import os
import logging
import numpy as np
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings

# Official RAGAS imports
from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics import Faithfulness, ResponseRelevancy
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

from ..security import get_audit_logger

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Structured evaluation output matching RAGAS format."""
    context_precision: float = 0.0
    context_recall: float = 0.0
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    overall_score: float = 0.0
    confidence_level: str = "Low"

    def to_dict(self) -> dict:
        return {
            "context_precision": round(self.context_precision, 4),
            "context_recall": round(self.context_recall, 4),
            "faithfulness": round(self.faithfulness, 4),
            "answer_relevancy": round(self.answer_relevancy, 4),
            "overall_score": round(self.overall_score, 4),
            "confidence_level": self.confidence_level,
        }


class RAGEvaluator:
    """
    Evaluates RAG pipeline quality using official RAGAS + embedding metrics.

    Strategy to minimize API calls:
    - faithfulness + answer_relevancy: Official RAGAS (LLM judge, ~2 calls)
    - context_precision + context_recall: Embedding cosine similarity (0 calls)
    """

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY required for evaluation")

        # Use fast model for evaluation to avoid Groq rate limits
        eval_model = os.getenv("EVAL_LLM_MODEL", "llama-3.1-8b-instant")

        chat_groq = ChatGroq(
            api_key=api_key,
            model_name=eval_model,
            temperature=0.0,
            max_tokens=500,
        )
        self.ragas_llm = LangchainLLMWrapper(chat_groq)

        # HuggingFace embeddings for both RAGAS and custom context metrics
        self.hf_embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.ragas_embeddings = LangchainEmbeddingsWrapper(self.hf_embeddings)

        # Official RAGAS metrics (LLM-based only)
        self.ragas_metrics = [
            Faithfulness(llm=self.ragas_llm),
            ResponseRelevancy(llm=self.ragas_llm, embeddings=self.ragas_embeddings),
        ]

        self.audit_logger = get_audit_logger()

    def _compute_context_precision(self, question: str, contexts: list[str]) -> float:
        """Embedding-based context precision: avg cosine similarity of chunks to question."""
        try:
            q_emb = self.hf_embeddings.embed_query(question)
            c_embs = self.hf_embeddings.embed_documents(contexts)
            # Cosine similarity
            q_vec = np.array(q_emb)
            scores = []
            for c_emb in c_embs:
                c_vec = np.array(c_emb)
                cos_sim = np.dot(q_vec, c_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(c_vec) + 1e-10)
                scores.append(max(0.0, cos_sim))
            # Precision = fraction of chunks above relevance threshold
            threshold = 0.3
            relevant = sum(1 for s in scores if s >= threshold)
            return relevant / max(len(scores), 1)
        except Exception as e:
            logger.warning("Context precision embedding failed: %s", e)
            return 0.0

    def _compute_context_recall(self, answer: str, contexts: list[str]) -> float:
        """Embedding-based context recall: how well contexts cover the answer."""
        try:
            a_emb = self.hf_embeddings.embed_query(answer)
            c_embs = self.hf_embeddings.embed_documents(contexts)
            # Max cosine similarity between answer and any context chunk
            a_vec = np.array(a_emb)
            max_sim = 0.0
            for c_emb in c_embs:
                c_vec = np.array(c_emb)
                cos_sim = np.dot(a_vec, c_vec) / (np.linalg.norm(a_vec) * np.linalg.norm(c_vec) + 1e-10)
                max_sim = max(max_sim, cos_sim)
            return max(0.0, min(max_sim, 1.0))
        except Exception as e:
            logger.warning("Context recall embedding failed: %s", e)
            return 0.0

    def evaluate(
        self,
        question: str,
        ground_truth: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Run hybrid RAGAS + embedding evaluation.

        1. Invokes RAG chain for answer + sources
        2. Computes context_precision/recall via embeddings (fast, 0 LLM calls)
        3. Computes faithfulness/answer_relevancy via official RAGAS (2 LLM calls)
        4. Logs results

        Args:
            question: The question to evaluate
            ground_truth: Optional ground-truth answer

        Returns:
            EvaluationResult with all metrics
        """
        from ..rag.chain import get_rag_chain

        # Step 1: Get RAG response
        rag_chain = get_rag_chain()
        rag_response = rag_chain.invoke(question, mask_pii=True)

        answer = rag_response.answer
        sources = rag_response.sources
        retrieved_contexts = [s["text"] for s in sources] if sources else ["No context retrieved."]

        result = EvaluationResult()

        # Step 2: Fast embedding-based context metrics (0 LLM calls)
        result.context_precision = self._compute_context_precision(question, retrieved_contexts)
        result.context_recall = self._compute_context_recall(answer, retrieved_contexts)

        # Step 3: Official RAGAS metrics (faithfulness + answer_relevancy)
        try:
            sample = SingleTurnSample(
                user_input=question,
                response=answer,
                retrieved_contexts=retrieved_contexts,
                reference=ground_truth or answer,
            )
            dataset = EvaluationDataset(samples=[sample])

            ragas_result = evaluate(
                dataset=dataset,
                metrics=self.ragas_metrics,
                llm=self.ragas_llm,
                embeddings=self.ragas_embeddings,
            )

            scores_df = ragas_result.to_pandas()
            row = scores_df.iloc[0]

            result.faithfulness = max(0.0, min(float(row.get("faithfulness", 0.0)), 1.0))
            result.answer_relevancy = max(0.0, min(float(row.get("answer_relevancy", 0.0)), 1.0))

        except Exception as e:
            logger.warning("RAGAS evaluation failed: %s", e)

        # Step 4: Overall score & confidence
        scores = [
            result.context_precision,
            result.context_recall,
            result.faithfulness,
            result.answer_relevancy,
        ]
        result.overall_score = sum(scores) / len(scores)

        if result.overall_score >= 0.8:
            result.confidence_level = "High"
        elif result.overall_score >= 0.5:
            result.confidence_level = "Medium"
        else:
            result.confidence_level = "Low"

        # Step 5: Audit log
        self.audit_logger.log(
            "rag_evaluation",
            "evaluation",
            {
                "question_length": len(question),
                "answer_length": len(answer),
                "sources_count": len(sources),
                "metrics": result.to_dict(),
                "library": "ragas",
                "ragas_metrics": ["faithfulness", "answer_relevancy"],
                "embedding_metrics": ["context_precision", "context_recall"],
            },
        )

        return result


# Global instance
_evaluator = None


def get_evaluator() -> RAGEvaluator:
    """Get the global RAGEvaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = RAGEvaluator()
    return _evaluator
