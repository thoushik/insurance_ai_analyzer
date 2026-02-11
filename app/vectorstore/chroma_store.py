"""
Insurance Document Intelligence Assistant
VectorStore Module - ChromaDB Store

Manages ChromaDB vector database for document storage and retrieval.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import chromadb
from chromadb.config import Settings

from .embeddings import get_embeddings
from ..security import get_folder_guard, get_audit_logger


@dataclass
class DocumentChunk:
    """Represents a chunk of a document for embedding."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: Optional[str] = None


class VectorStore:
    """
    ChromaDB-based vector store for insurance documents.
    
    Features:
    - Persistent storage in project cache directory
    - Similarity search with metadata filtering
    - Automatic embedding generation
    """
    
    COLLECTION_NAME = "insurance_documents"
    
    def __init__(self):
        self.guard = get_folder_guard()
        self.logger = get_audit_logger()
        self.embeddings = get_embeddings()
        
        # Initialize ChromaDB with persistent storage
        self.db_path = self.guard.cache_dir / "chromadb"
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        try:
            self._init_client()
        except Exception as e:
            # Auto-recover from corrupted database
            print(f"[ChromaDB] Init failed ({e}), resetting database...")
            import shutil
            if self.db_path.exists():
                shutil.rmtree(str(self.db_path), ignore_errors=True)
            self.db_path.mkdir(parents=True, exist_ok=True)
            self._init_client()
            print("[ChromaDB] Recovery successful - fresh database created")
        
        self.logger.log(
            "vectorstore_initialized",
            "vectorstore",
            {
                "db_path": str(self.db_path),
                "collection": self.COLLECTION_NAME,
                "count": self.collection.count()
            }
        )
    
    def _init_client(self):
        """Initialize ChromaDB client and collection."""
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Insurance document chunks"}
        )
    
    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        """
        Add document chunks to the vector store.
        
        Args:
            chunks: List of DocumentChunk objects
            
        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0
        
        # Prepare data for ChromaDB
        texts = [chunk.text for chunk in chunks]
        
        # Sanitize metadata - ChromaDB requires str, int, float, bool, or None
        def sanitize_metadata(meta):
            sanitized = {}
            for key, value in meta.items():
                if isinstance(value, list):
                    sanitized[key] = ", ".join(str(v) for v in value)
                elif isinstance(value, dict):
                    sanitized[key] = str(value)
                elif value is None or isinstance(value, (str, int, float, bool)):
                    sanitized[key] = value
                else:
                    sanitized[key] = str(value)
            return sanitized
        
        metadatas = [sanitize_metadata(chunk.metadata) for chunk in chunks]
        ids = [
            chunk.chunk_id or f"chunk_{i}_{hash(chunk.text) % 10000}"
            for i, chunk in enumerate(chunks)
        ]
        
        # Generate embeddings
        embeddings = self.embeddings.embed_texts(texts)
        
        # Add to collection
        self.collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        
        self.logger.log(
            "chunks_added",
            "vectorstore",
            {"count": len(chunks)}
        )
        
        return len(chunks)
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of results with text, metadata, and score
        """
        # Generate query embedding
        query_embedding = self.embeddings.embed_text(query)
        
        # Build search kwargs
        search_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"]
        }
        
        if filter_metadata:
            search_kwargs["where"] = filter_metadata
        
        # Execute search
        results = self.collection.query(**search_kwargs)
        
        # Format results
        formatted = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append({
                    "text": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0
                })
        
        self.logger.log(
            "vector_search",
            "vectorstore",
            {
                "query": query[:50],
                "results_count": len(formatted)
            }
        )
        
        return formatted
    
    def search_by_type(
        self,
        query: str,
        doc_type: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search with document type filter.
        
        Args:
            query: Search query
            doc_type: Document type (excel, pdf)
            n_results: Number of results
            
        Returns:
            Filtered search results
        """
        return self.search(
            query=query,
            n_results=n_results,
            filter_metadata={"type": doc_type}
        )
    
    def get_document_chunks(self, source: str) -> List[Dict[str, Any]]:
        """
        Get all chunks from a specific source document.
        
        Args:
            source: Source filename
            
        Returns:
            List of chunks from that source
        """
        results = self.collection.get(
            where={"source": source},
            include=["documents", "metadatas"]
        )
        
        formatted = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"]):
                formatted.append({
                    "text": doc,
                    "metadata": results["metadatas"][i] if results["metadatas"] else {}
                })
        
        return formatted
    
    def source_exists(self, source: str) -> bool:
        """
        Check if a document source already exists in the vector store.
        
        Args:
            source: Source filename
            
        Returns:
            True if source has chunks in the store
        """
        try:
            results = self.collection.get(
                where={"source": source},
                limit=1,
                include=[]
            )
            return bool(results and results["ids"])
        except Exception:
            return False
    
    def clear(self):
        """Clear all documents from the collection."""
        self.client.delete_collection(self.COLLECTION_NAME)
        self.collection = self.client.create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "Insurance document chunks"}
        )
        
        self.logger.log(
            "vectorstore_cleared",
            "vectorstore",
            {}
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector store."""
        return {
            "total_chunks": self.collection.count(),
            "collection_name": self.COLLECTION_NAME,
            "db_path": str(self.db_path)
        }


# Global instance
_store = None


def get_vector_store() -> VectorStore:
    """Get the global VectorStore instance."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
