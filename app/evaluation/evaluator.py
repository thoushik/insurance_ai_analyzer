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
from ..rag.chain import get_rag_chain

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


# ── LLM-as-Judge Prompt Templates ───────────────────────────────────

CONTEXT_PRECISION_PROMPT = """You are an expert evaluator. Given a question and retrieved context chunks, judge how relevant each chunk is to answering the question.

Question: {question}

Retrieved Context:
{context}

For each chunk, decide if it is RELEVANT (1) or NOT RELEVANT (0) to answering the question.
Count the number of relevant chunks and the total number of chunks.

Return ONLY a JSON object (no markdown, no explanation):
{{"relevant_count": <int>, "total_count": <int>}}"""

CONTEXT_RECALL_PROMPT = """You are an expert evaluator. Given an answer and the retrieved context, check if the key claims in the answer are supported by the context.

Answer: {answer}

Retrieved Context:
{context}

Ground Truth (if available): {ground_truth}

Instructions:
1. Extract the key factual claims from the answer (up to 10).
2. For each claim, check if it is supported by the context.
3. Count supported claims vs total claims.

Return ONLY a JSON object (no markdown, no explanation):
{{"supported_claims": <int>, "total_claims": <int>}}"""

FAITHFULNESS_PROMPT = """You are a hallucination detection expert. Given an answer and the source context, determine how faithfully the answer reflects ONLY what is stated in the context.

Answer: {answer}

Source Context:
{context}

Instructions:
1. Extract each factual statement from the answer (up to 10).
2. For each statement, verify if it can be directly inferred from the context.
3. A statement is FAITHFUL if the context supports it. It is UNFAITHFUL if it adds information not in the context.

Return ONLY a JSON object (no markdown, no explanation):
{{"faithful_statements": <int>, "total_statements": <int>}}"""

ANSWER_RELEVANCY_PROMPT = """You are an expert evaluator. Given a question and an answer, rate how directly and completely the answer addresses the question.

Question: {question}

Answer: {answer}

Instructions:
Rate the answer relevancy on a scale of 0.0 to 1.0:
- 1.0: The answer directly and completely addresses the question
- 0.7-0.9: The answer mostly addresses the question with minor gaps
- 0.4-0.6: The answer partially addresses the question
- 0.1-0.3: The answer barely addresses the question
- 0.0: The answer does not address the question at all

Return ONLY a JSON object (no markdown, no explanation):
{{"relevancy_score": <float>}}"""


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
        2. Computes all four metrics via LLM-as-judge
        3. Logs results via audit logger

        Args:
            question: The question to evaluate
            ground_truth: Optional ground-truth answer for recall

        Returns:
            EvaluationResult with all metrics
        """
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

        # Step 2: Compute each metric
        result = EvaluationResult()

        result.context_precision = self._eval_context_precision(question, context)
        result.context_recall = self._eval_context_recall(answer, context, ground_truth)
        result.faithfulness = self._eval_faithfulness(answer, context)
        result.answer_relevancy = self._eval_answer_relevancy(question, answer)

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

    # ── Individual Metric Evaluators ─────────────────────────────

    def _eval_context_precision(self, question: str, context: str) -> float:
        """Evaluate how relevant retrieved chunks are to the question."""
        try:
            prompt = CONTEXT_PRECISION_PROMPT.format(
                question=question, context=context
            )
            response = self.llm.invoke(prompt)
            data = self._parse_json(response.content)
            total = data.get("total_count", 1)
            relevant = data.get("relevant_count", 0)
            return min(relevant / max(total, 1), 1.0)
        except Exception as e:
            logger.warning("context_precision eval failed: %s", e)
            return 0.0

    def _eval_context_recall(
        self, answer: str, context: str, ground_truth: Optional[str]
    ) -> float:
        """Evaluate if context covers the answer's claims."""
        try:
            gt = ground_truth or "Not provided"
            prompt = CONTEXT_RECALL_PROMPT.format(
                answer=answer, context=context, ground_truth=gt
            )
            response = self.llm.invoke(prompt)
            data = self._parse_json(response.content)
            total = data.get("total_claims", 1)
            supported = data.get("supported_claims", 0)
            return min(supported / max(total, 1), 1.0)
        except Exception as e:
            logger.warning("context_recall eval failed: %s", e)
            return 0.0

    def _eval_faithfulness(self, answer: str, context: str) -> float:
        """Evaluate if the answer is grounded in the context (hallucination detection)."""
        try:
            prompt = FAITHFULNESS_PROMPT.format(
                answer=answer, context=context
            )
            response = self.llm.invoke(prompt)
            data = self._parse_json(response.content)
            total = data.get("total_statements", 1)
            faithful = data.get("faithful_statements", 0)
            return min(faithful / max(total, 1), 1.0)
        except Exception as e:
            logger.warning("faithfulness eval failed: %s", e)
            return 0.0

    def _eval_answer_relevancy(self, question: str, answer: str) -> float:
        """Evaluate how directly the answer addresses the question."""
        try:
            prompt = ANSWER_RELEVANCY_PROMPT.format(
                question=question, answer=answer
            )
            response = self.llm.invoke(prompt)
            data = self._parse_json(response.content)
            score = data.get("relevancy_score", 0.0)
            return max(0.0, min(float(score), 1.0))
        except Exception as e:
            logger.warning("answer_relevancy eval failed: %s", e)
            return 0.0

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
