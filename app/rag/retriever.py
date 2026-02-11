"""
Insurance Document Intelligence Assistant
RAG Module - Retriever

Wraps ChromaDB for semantic document retrieval.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from ..vectorstore import get_vector_store, VectorStore, DocumentChunk
from ..ingestion import get_excel_parser, get_pdf_parser
from ..security import get_folder_guard, get_audit_logger


@dataclass
class RetrievalResult:
    """Result from document retrieval."""
    text: str
    source: str
    chunk_type: str
    metadata: Dict[str, Any]
    relevance_score: float
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
            "relevance_score": self.relevance_score
        }


class DocumentRetriever:
    """
    Manages document ingestion and retrieval for RAG.
    
    Features:
    - Ingest Excel and PDF files into vector store
    - Semantic search with citation tracking
    - Metadata filtering by document type, sheet, etc.
    """
    
    def __init__(self):
        self.guard = get_folder_guard()
        self.logger = get_audit_logger()
        self.vector_store = get_vector_store()
        self.excel_parser = get_excel_parser()
        self.pdf_parser = get_pdf_parser()
    
    def ingest_document(self, filepath: str) -> int:
        """
        Ingest a document into the vector store.
        
        Args:
            filepath: Path to the document
            
        Returns:
            Number of chunks created
        """
        safe_path = self.guard.validate_path(filepath)
        suffix = safe_path.suffix.lower()
        
        # Skip if already indexed in vector store
        if self.vector_store.source_exists(safe_path.name):
            self.logger.log(
                "document_skipped_rag",
                "rag",
                {"file": safe_path.name, "reason": "already_indexed"}
            )
            return 0
        
        # Get chunks based on file type
        if suffix in [".xlsx", ".xls"]:
            chunks = self.excel_parser.to_chunks(safe_path)
        elif suffix == ".pdf":
            chunks = self.pdf_parser.to_chunks(safe_path)
        else:
            self.logger.log(
                "unsupported_file",
                "rag",
                {"file": str(safe_path)},
                status="error"
            )
            return 0
        
        # Convert to DocumentChunk objects
        doc_chunks = [
            DocumentChunk(
                text=chunk["text"],
                metadata=chunk["metadata"],
                chunk_id=f"{safe_path.stem}_{i}"
            )
            for i, chunk in enumerate(chunks)
        ]
        
        # Add to vector store
        count = self.vector_store.add_chunks(doc_chunks)
        
        self.logger.log(
            "document_ingested_rag",
            "rag",
            {
                "file": safe_path.name,
                "chunks": count
            }
        )
        
        return count
    
    def ingest_folder(self, folder_path: str) -> Dict[str, int]:
        """
        Ingest all supported documents from a folder.
        
        Args:
            folder_path: Path to the folder
            
        Returns:
            Dictionary of filename -> chunk count
        """
        from pathlib import Path
        
        safe_path = self.guard.validate_path(folder_path)
        results = {}
        
        supported_extensions = [".xlsx", ".xls", ".pdf"]
        
        for file_path in safe_path.rglob("*"):
            if file_path.suffix.lower() in supported_extensions:
                try:
                    count = self.ingest_document(str(file_path))
                    results[file_path.name] = count
                except Exception as e:
                    self.logger.log(
                        "ingestion_error",
                        "rag",
                        {
                            "file": str(file_path),
                            "error": str(e)
                        },
                        status="error"
                    )
                    results[file_path.name] = 0
        
        return results
    
    def retrieve(
        self,
        query: str,
        k: int = 5,
        doc_type: Optional[str] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: Search query
            k: Number of results
            doc_type: Optional filter (excel/pdf)
            
        Returns:
            List of RetrievalResult objects
        """
        # Build filter
        filter_metadata = None
        if doc_type:
            filter_metadata = {"type": doc_type}
        
        # Search vector store
        results = self.vector_store.search(
            query=query,
            n_results=k,
            filter_metadata=filter_metadata
        )
        
        # Convert to RetrievalResult objects
        retrieval_results = []
        for result in results:
            metadata = result.get("metadata", {})
            retrieval_results.append(
                RetrievalResult(
                    text=result.get("text", ""),
                    source=metadata.get("source", "Unknown"),
                    chunk_type=metadata.get("chunk_type", "Unknown"),
                    metadata=metadata,
                    relevance_score=1.0 - result.get("distance", 0)  # Convert distance to similarity
                )
            )
        
        self.logger.log(
            "rag_retrieval",
            "rag",
            {
                "query": query[:50],
                "results": len(retrieval_results)
            }
        )
        
        return retrieval_results
    
    def get_context_string(
        self,
        query: str,
        k: int = 5
    ) -> str:
        """
        Get a formatted context string for LLM consumption.
        
        Args:
            query: Search query
            k: Number of results
            
        Returns:
            Formatted context string with citations
        """
        results = self.retrieve(query, k)
        
        if not results:
            return "No relevant documents found."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[Source {i}: {result.source}, Type: {result.chunk_type}]\n{result.text}"
            )
        
        return "\n\n---\n\n".join(context_parts)
    
    def clear(self):
        """Clear all documents from the vector store."""
        self.vector_store.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get retriever statistics."""
        return self.vector_store.get_stats()


# Global instance
_retriever = None


def get_retriever() -> DocumentRetriever:
    """Get the global DocumentRetriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = DocumentRetriever()
    return _retriever
