"""
Insurance Document Intelligence Assistant
FastAPI Backend

RESTful API with RAG-powered chat endpoints.
"""

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Set up environment before imports
from dotenv import load_dotenv
load_dotenv()

from ..security import get_folder_guard, get_audit_logger
from ..rag import get_retriever, get_rag_chain
from ..ingestion import get_document_registry


# Pydantic models for request/response
class ChatRequest(BaseModel):
    message: str
    k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: list
    query: str


class IngestResponse(BaseModel):
    success: bool
    files_processed: dict
    total_chunks: int


class HealthResponse(BaseModel):
    status: str
    vectorstore_stats: dict
    model: str


# Create FastAPI app
app = FastAPI(
    title="Insurance Document Intelligence Assistant",
    description="RAG-powered insurance document analysis with SR 11-7 compliance",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Global instances (lazy-loaded)
_guard = None
_logger = None
_retriever = None
_chain = None
_registry = None


def get_guard():
    global _guard
    if _guard is None:
        _guard = get_folder_guard()
    return _guard


def get_logger():
    global _logger
    if _logger is None:
        _logger = get_audit_logger()
    return _logger


def get_retriever_instance():
    global _retriever
    if _retriever is None:
        _retriever = get_retriever()
    return _retriever


def get_chain_instance():
    global _chain
    if _chain is None:
        _chain = get_rag_chain()
    return _chain


def get_registry_instance():
    global _registry
    if _registry is None:
        _registry = get_document_registry()
    return _registry


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@app.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        retriever = get_retriever_instance()
        chain = get_chain_instance()
        
        return HealthResponse(
            status="healthy",
            vectorstore_stats=retriever.get_stats(),
            model=chain.model_name
        )
    except Exception as e:
        return HealthResponse(
            status=f"error: {str(e)}",
            vectorstore_stats={},
            model="unknown"
        )


@app.get("/api/stats")
async def get_stats():
    """Get system statistics."""
    try:
        retriever = get_retriever_instance()
        chain = get_chain_instance()
        registry = get_registry_instance()
        
        return {
            "vectorstore": retriever.get_stats(),
            "documents": registry.list_documents(),
            "model": chain.model_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Document Upload & Ingestion Endpoints
# =============================================================================

@app.post("/api/upload", response_model=IngestResponse)
async def upload_files(files: list[UploadFile] = File(...)):
    """
    Upload and ingest documents into the RAG system.
    
    Supports Excel (.xlsx, .xls) and PDF files.
    """
    guard = get_guard()
    logger = get_logger()
    retriever = get_retriever_instance()
    registry = get_registry_instance()
    
    results = {}
    total_chunks = 0
    
    for file in files:
        # Validate file type
        suffix = Path(file.filename).suffix.lower()
        if suffix not in [".xlsx", ".xls", ".pdf"]:
            results[file.filename] = {"error": "Unsupported file type"}
            continue
        
        try:
            # Save file to upload directory
            save_path = guard.upload_dir / file.filename
            content = await file.read()
            guard.safe_write(save_path, content)
            
            # Ingest into document registry (for legacy support)
            entry = registry.ingest_file(save_path)
            
            # Ingest into RAG vector store
            chunk_count = retriever.ingest_document(str(save_path))
            
            results[file.filename] = {
                "doc_id": entry.id,
                "chunks": chunk_count
            }
            total_chunks += chunk_count
            
            logger.log(
                "file_uploaded_rag",
                "api",
                {
                    "filename": file.filename,
                    "chunks": chunk_count
                }
            )
            
        except Exception as e:
            results[file.filename] = {"error": str(e)}
            logger.log(
                "upload_error",
                "api",
                {
                    "filename": file.filename,
                    "error": str(e)
                },
                status="error"
            )
    
    return IngestResponse(
        success=True,
        files_processed=results,
        total_chunks=total_chunks
    )


@app.post("/api/ingest-folder")
async def ingest_folder(folder_path: str = Form(...)):
    """
    Ingest all documents from a folder path.
    
    Copies files to upload directory and ingests into RAG system.
    """
    guard = get_guard()
    logger = get_logger()
    retriever = get_retriever_instance()
    registry = get_registry_instance()
    
    try:
        source_path = Path(folder_path)
        if not source_path.exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {folder_path}")
        
        if not source_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {folder_path}")
        
        # Copy files to upload directory
        supported = [".xlsx", ".xls", ".pdf"]
        results = {}
        total_chunks = 0
        
        for file_path in source_path.rglob("*"):
            if file_path.suffix.lower() in supported:
                try:
                    # Copy to upload dir
                    dest_path = guard.upload_dir / file_path.name
                    shutil.copy2(file_path, dest_path)
                    
                    # Ingest into registry
                    entry = registry.ingest_file(dest_path)
                    
                    # Ingest into RAG
                    chunk_count = retriever.ingest_document(str(dest_path))
                    
                    results[file_path.name] = {
                        "doc_id": entry.id,
                        "chunks": chunk_count
                    }
                    total_chunks += chunk_count
                    
                except Exception as e:
                    results[file_path.name] = {"error": str(e)}
        
        logger.log(
            "folder_ingested_rag",
            "api",
            {
                "folder": folder_path,
                "files": len(results),
                "chunks": total_chunks
            }
        )
        
        return {
            "success": True,
            "files_processed": results,
            "total_chunks": total_chunks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# RAG Chat Endpoints
# =============================================================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    RAG-powered chat endpoint.
    
    Retrieves relevant document context and generates grounded response.
    """
    logger = get_logger()
    
    try:
        chain = get_chain_instance()
        
        # Process through RAG chain
        response = chain.invoke(
            question=request.message,
            k=request.k
        )
        
        return ChatResponse(
            answer=response.answer,
            sources=response.sources,
            query=response.query
        )
        
    except Exception as e:
        logger.log(
            "chat_error",
            "api",
            {"error": str(e)},
            status="error"
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents")
async def list_documents():
    """List all ingested documents."""
    try:
        registry = get_registry_instance()
        return {"documents": registry.list_documents()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/clear")
async def clear_vectorstore():
    """Clear all documents from the vector store."""
    try:
        retriever = get_retriever_instance()
        registry = get_registry_instance()
        
        retriever.clear()
        registry.clear_registry()
        
        return {"success": True, "message": "Vector store cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Legacy Compatibility Endpoints
# =============================================================================

@app.post("/api/analyze")
async def analyze_documents():
    """Trigger document analysis (legacy endpoint)."""
    try:
        chain = get_chain_instance()
        
        # Generate executive summary
        response = chain.invoke(
            question="Provide an executive summary of all the uploaded documents. What are they about and what calculations do they contain?",
            k=10
        )
        
        return {
            "success": True,
            "analysis": response.answer,
            "sources": response.sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
