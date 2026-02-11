"""
Insurance Document Intelligence Assistant
RAG Module

Provides retrieval-augmented generation for grounded,
document-based responses.
"""

from .retriever import get_retriever, DocumentRetriever
from .chain import get_rag_chain, RAGChain

__all__ = [
    "get_retriever",
    "DocumentRetriever",
    "get_rag_chain",
    "RAGChain"
]
