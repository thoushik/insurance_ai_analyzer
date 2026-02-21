"""
Insurance Document Intelligence Assistant
Evaluation Module - RAG Evaluator

Computes RAGAS-style metrics for RAG pipeline quality using LLM-as-judge:
  - context_precision: Are retrieved chunks relevant to the question?
  - context_recall: Do retrieved chunks cover the answer claims?
  - faithfulness: Is the answer grounded in the context (hallucination detection)?
  - answer_relevancy: Does the answer directly address the question?

All metrics return 0.0-1.0 floats. Uses the existing Groq LLM for evaluation.
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, field

from dotenv import load_dotenv
load_dotenv()

from langchain_groq import ChatGroq

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


# ── Consolidated LLM-as-Judge Prompt Template ───────────────────────

EVALUATION_PROMPT = """You are an expert RAG system evaluator. Given a question, an answer, and the retrieved context, compute four quality metrics.

Question: {question}

Answer: {answer}

Retrieved Context:
{context}

Ground Truth (if available): {ground_truth}

Instructions for the 4 metrics (score each from 0.0 to 1.0):

1. CONTEXT PRECISION (0.0 to 1.0):
   - What ratio of the retrieved chunks are genuinely relevant to the question?
   - 1.0 = all relevant, 0.0 = none relevant.

2. CONTEXT RECALL (0.0 to 1.0):
   - Does the context include all the information needed to answer the question optimally?
   - 1.0 = fully supported/sufficient, 0.0 = completely insufficient.

3. FAITHFULNESS (0.0 to 1.0):
   - Is the answer entirely grounded in the provided context, without hallucinations?
   - 1.0 = completely faithful, 0.0 = contains major hallucinations.

4. ANSWER RELEVANCY (0.0 to 1.0):
   - How directly and completely does the answer address the actual question asked?
   - 1.0 = direct/complete, 0.0 = irrelevant evasion.

Return ONLY a valid JSON object matching this exact format (do not include markdown blocks or any other text):
{{"context_precision": <float>, "context_recall": <float>, "faithfulness": <float>, "answer_relevancy": <float>}}"""


class RAGEvaluator:
    """
    Evaluates RAG pipeline quality using LLM-as-judge pattern.

    Computes four RAGAS-style metrics independently of the main
    chat pipeline. Uses the existing Groq LLM for evaluation.
    """

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY required for evaluation")

        model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

        self.llm = ChatGroq(
            api_key=api_key,
            model_name=model,
            temperature=0.0,  # Deterministic for evaluation
            max_tokens=500,
        )
        self.audit_logger = get_audit_logger()

    def evaluate(
        self,
        question: str,
        ground_truth: Optional[str] = None,
    ) -> EvaluationResult:
        """
        Run full RAGAS-style evaluation on a question.

        1. Invokes the RAG chain to get answer + sources
        2. Computes all four metrics via a single LLM call for efficiency
        3. Logs results via audit logger

        Args:
            question: The question to evaluate
            ground_truth: Optional ground-truth answer for recall

        Returns:
            EvaluationResult with all metrics
        """
        from ..rag.chain import get_rag_chain
        
        # Step 1: Get RAG response (uses existing pipeline)
        rag_chain = get_rag_chain()
        rag_response = rag_chain.invoke(question, mask_pii=True)

        answer = rag_response.answer
        sources = rag_response.sources

        # Build context string from sources
        context = "\n\n---\n\n".join(
            f"[Chunk {s['index']}] (Source: {s['source']}, Relevance: {s['relevance']})\n{s['text']}"
            for s in sources
        )

        if not context.strip():
            context = "No context retrieved."

        # Step 2: Compute all metrics via a single LLM call for efficiency
        prompt = EVALUATION_PROMPT.format(
            question=question,
            answer=answer,
            context=context,
            ground_truth=ground_truth or "None",
        )
        
        result = EvaluationResult()
        try:
            llm_response = self.llm.invoke(prompt)
            data = self._parse_json(llm_response.content)
            
            result.context_precision = max(0.0, min(float(data.get("context_precision", 0.0)), 1.0))
            result.context_recall = max(0.0, min(float(data.get("context_recall", 0.0)), 1.0))
            result.faithfulness = max(0.0, min(float(data.get("faithfulness", 0.0)), 1.0))
            result.answer_relevancy = max(0.0, min(float(data.get("answer_relevancy", 0.0)), 1.0))
        except Exception as e:
            logger.warning("Evaluation failed during LLM call: %s", e)

        # Step 3: Compute overall score and confidence
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

        # Step 4: Audit log (counts/scores only, no raw content)
        self.audit_logger.log(
            "rag_evaluation",
            "evaluation",
            {
                "question_length": len(question),
                "answer_length": len(answer),
                "sources_count": len(sources),
                "metrics": result.to_dict(),
            },
        )

        return result

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _parse_json(text: str) -> dict:
        """Parse JSON from LLM response, handling markdown code fences."""
        cleaned = text.strip()
        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (the fences)
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        return json.loads(cleaned)


# Global instance
_evaluator = None


def get_evaluator() -> RAGEvaluator:
    """Get the global RAGEvaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = RAGEvaluator()
    return _evaluator
