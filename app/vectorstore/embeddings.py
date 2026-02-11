"""
Insurance Document Intelligence Assistant
VectorStore Module - Embeddings

Local HuggingFace embeddings for document vectorization.
Uses sentence-transformers/all-MiniLM-L6-v2 for fast, lightweight embeddings.
"""

from typing import List
from dataclasses import dataclass

from langchain_community.embeddings import HuggingFaceEmbeddings

from ..security import get_audit_logger


@dataclass
class EmbeddingModel:
    """
    Wrapper for HuggingFace embedding model.
    
    Features:
    - Local embeddings (no API calls)
    - Fast inference with MiniLM
    - Caches model after first load
    """
    
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    _embeddings: HuggingFaceEmbeddings = None
    
    def __post_init__(self):
        self.logger = get_audit_logger()
    
    def get_embeddings(self) -> HuggingFaceEmbeddings:
        """
        Get the HuggingFace embeddings model.
        Lazy-loads the model on first call.
        
        Returns:
            HuggingFaceEmbeddings instance
        """
        if self._embeddings is None:
            self.logger.log(
                "embedding_model_load",
                "vectorstore",
                {"model": self.model_name}
            )
            
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
        
        return self._embeddings
    
    def embed_text(self, text: str) -> List[float]:
        """
        Embed a single text string.
        
        Args:
            text: Text to embed
            
        Returns:
            List of embedding floats
        """
        embeddings = self.get_embeddings()
        return embeddings.embed_query(text)
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = self.get_embeddings()
        return embeddings.embed_documents(texts)


# Global instance
_model = None


def get_embeddings() -> EmbeddingModel:
    """Get the global EmbeddingModel instance."""
    global _model
    if _model is None:
        _model = EmbeddingModel()
    return _model
