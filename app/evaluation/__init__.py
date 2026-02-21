"""
Insurance Document Intelligence Assistant
Evaluation Module

Provides quantitative evaluation of RAG pipeline quality
using RAGAS-style metrics and Giskard-style robustness testing.
"""

from .evaluator import RAGEvaluator, get_evaluator
from .robustness import RobustnessTester, get_robustness_tester

__all__ = [
    "RAGEvaluator",
    "get_evaluator",
    "RobustnessTester",
    "get_robustness_tester",
]
