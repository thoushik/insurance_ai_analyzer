"""
Insurance Document Intelligence Assistant
VectorStore Module

Provides ChromaDB vector storage and HuggingFace embeddings
for RAG-based document retrieval.
"""

from .embeddings import get_embeddings, EmbeddingModel
from .chroma_store import get_vector_store, VectorStore, DocumentChunk

__all__ = [
    "get_embeddings",
    "EmbeddingModel", 
    "get_vector_store",
    "VectorStore",
    "DocumentChunk"
]
