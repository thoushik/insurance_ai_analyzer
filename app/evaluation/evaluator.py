"""
Insurance Document Intelligence Assistant
Evaluation Module - RAG Evaluator (Single LLM Call)

Evaluates RAG pipeline quality using ONE consolidated LLM call:
  - context_precision: How relevant the retrieved chunks are to the question
  - context_recall: How well the chunks cover the answer
  - faithfulness: Whether the answer is grounded in the context
  - answer_relevancy: How directly the answer addresses the question

Uses llama-3.1-8b-instant for evaluation (high rate limits on Groq free tier).
Token-optimized: top 3 chunks, truncated context/answer.
"""

import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq

from ..security import get_audit_logger

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────
MAX_CHUNKS = 3          # Only use top 3 retrieved chunks
MAX_CHUNK_CHARS = 500   # Truncate each chunk to 500 chars
MAX_ANSWER_CHARS = 1000 # Truncate answer to 1000 chars


@dataclass
class EvaluationResult:
    """Structured evaluation output."""
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


def _extract_metric(text: str, metric_name: str) -> float:
    """
    Extract a single metric float from LLM text output.
    Tries JSON key match first, then falls back to nearby float.
    Always returns 0.5 on failure (never 0.0).
    """
    # 1. Try strict JSON key: "metric_name": 0.85
    pattern = rf'"{metric_name}"\s*:\s*([\d.]+)'
    match = re.search(pattern, text)
    if match:
        val = float(match.group(1))
        return max(0.0, min(val, 1.0))

    # 2. Fallback: never return 0.0, return 0.5 as neutral
    return 0.5


class RAGEvaluator:
    """
    Evaluates RAG pipeline quality using a SINGLE consolidated LLM call.

    Strategy:
    - ONE prompt asks the LLM to score all 4 metrics at once
    - Input is truncated to minimize token usage
    - Regex extraction with 0.5 fallback (never 0.0)
    """

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY required for evaluation")

        eval_model = os.getenv("EVAL_LLM_MODEL", "llama-3.1-8b-instant")

        self.llm = ChatGroq(
            api_key=api_key,
            model_name=eval_model,
            temperature=0.0,
            max_tokens=300,
        )

        self.audit_logger = get_audit_logger()

    def evaluate(
        self,
        question: str,
        ground_truth: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Run single-call evaluation for a question.

        1. Invokes RAG chain for a fresh answer + sources
        2. Truncates inputs to minimize tokens
        3. Sends ONE LLM prompt for all 4 metrics
        4. Extracts scores via regex (fallback = 0.5)
        5. Prints results to terminal and logs to audit

        Args:
            question: The question to evaluate
            ground_truth: Optional ground-truth answer (unused currently)

        Returns:
            EvaluationResult with all metrics
        """
        from ..rag.chain import get_rag_chain

        # ── Step 1: Get fresh RAG response for this exact question ──
        rag_chain = get_rag_chain()
        rag_response = rag_chain.invoke(question, mask_pii=True)

        answer = rag_response.answer or ""
        sources = rag_response.sources or []
        retrieved_contexts = [s["text"] for s in sources] if sources else []

        # Guard: ensure we have a real answer before evaluating
        if not answer.strip():
            logger.warning("Empty answer from RAG chain, skipping evaluation")
            result = EvaluationResult(
                context_precision=0.5, context_recall=0.5,
                faithfulness=0.5, answer_relevancy=0.5,
                overall_score=0.5, confidence_level="Low",
            )
            self._log_and_print(question, result)
            return result

        # ── Step 2: Truncate inputs to reduce token usage ──
        truncated_contexts = []
        for ctx in retrieved_contexts[:MAX_CHUNKS]:
            truncated_contexts.append(ctx[:MAX_CHUNK_CHARS])

        context_str = "\n---\n".join(truncated_contexts) if truncated_contexts else "No context."
        answer_str = answer[:MAX_ANSWER_CHARS]

        # ── Step 3: Single LLM call for ALL 4 metrics ──
        eval_prompt = f"""You are a strict RAG evaluation API. Score the following on 4 metrics.

Question: {question}

Context (retrieved documents):
{context_str}

Answer (generated by AI):
{answer_str}

Score each metric from 0.0 to 1.0:
- context_precision: Are the retrieved chunks relevant to the question? (1.0 = all relevant, 0.0 = none relevant)
- context_recall: Do the chunks contain enough info to answer fully? (1.0 = complete coverage, 0.0 = no coverage)
- faithfulness: Is the answer grounded in the context with no hallucinations? (1.0 = fully grounded, 0.0 = hallucinated)
- answer_relevancy: Does the answer directly address the question? (1.0 = perfect answer, 0.0 = irrelevant)

Output ONLY valid JSON, nothing else:
{{"context_precision": float, "context_recall": float, "faithfulness": float, "answer_relevancy": float}}"""

        result = EvaluationResult()

        try:
            llm_response = self.llm.invoke(eval_prompt)
            raw_text = llm_response.content

            # Extract each metric independently with regex
            result.context_precision = _extract_metric(raw_text, "context_precision")
            result.context_recall = _extract_metric(raw_text, "context_recall")
            result.faithfulness = _extract_metric(raw_text, "faithfulness")
            result.answer_relevancy = _extract_metric(raw_text, "answer_relevancy")

        except Exception as e:
            logger.warning("Evaluation LLM call failed: %s", e)
            result.context_precision = 0.5
            result.context_recall = 0.5
            result.faithfulness = 0.5
            result.answer_relevancy = 0.5

        # ── Step 4: Compute overall score & confidence ──
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

        # ── Step 5: Print to terminal + audit log ──
        self._log_and_print(question, result)

        return result

    def _log_and_print(self, question: str, result: EvaluationResult):
        """Print evaluation to terminal and write to audit log."""
        timestamp = datetime.now(timezone.utc).isoformat()
        scores = result.to_dict()

        # Terminal output
        print("\n" + "=" * 60)
        print("EVALUATION RESULT")
        print(f"  Timestamp     : {timestamp}")
        print(f"  Question      : {question[:80]}")
        print(f"  Precision     : {scores['context_precision']}")
        print(f"  Recall        : {scores['context_recall']}")
        print(f"  Faithfulness  : {scores['faithfulness']}")
        print(f"  Relevancy     : {scores['answer_relevancy']}")
        print(f"  Overall       : {scores['overall_score']}")
        print(f"  Confidence    : {scores['confidence_level']}")
        print("=" * 60 + "\n")

        # Audit log
        self.audit_logger.log(
            "rag_evaluation",
            "evaluation",
            {
                "event_type": "rag_evaluation",
                "question": question,
                "scores": scores,
                "timestamp": timestamp,
            },
        )


# Global instance
_evaluator = None


def get_evaluator() -> RAGEvaluator:
    """Get the global RAGEvaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = RAGEvaluator()
    return _evaluator
