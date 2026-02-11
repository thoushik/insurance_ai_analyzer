"""
Insurance Document Intelligence Assistant
LLM Module

Provides Groq API integration and prompt management.
"""

from .client import LLMClient, get_llm_client
from .prompts import (
    MASTER_SYSTEM_PROMPT,
    get_system_prompt,
    get_ingestion_confirmation,
    get_executive_summary_prompt,
    get_document_prompt,
    get_sheet_prompt,
    get_formula_prompt,
    get_calculation_type_prompt,
)
from .response_handler import ResponseHandler, get_response_handler

__all__ = [
    "LLMClient",
    "get_llm_client",
    "MASTER_SYSTEM_PROMPT",
    "get_system_prompt",
    "get_ingestion_confirmation",
    "get_executive_summary_prompt",
    "get_document_prompt",
    "get_sheet_prompt",
    "get_formula_prompt",
    "get_calculation_type_prompt",
    "ResponseHandler",
    "get_response_handler",
]
