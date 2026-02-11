"""
Insurance Document Intelligence Assistant
API Routes

Flask API endpoints for document analysis and chat.
"""

import os
from pathlib import Path
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from ..security import get_folder_guard, get_audit_logger, SecurityViolationError
from ..ingestion import get_document_registry
from ..llm import get_response_handler
from ..rag.retriever import get_retriever  # Added for RAG


api = Blueprint("api", __name__)

guard = get_folder_guard()
logger = get_audit_logger()


# Allowed file extensions
ALLOWED_EXTENSIONS = {"xlsx", "xls", "pdf"}


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@api.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Insurance Document Intelligence Assistant"
    })


@api.route("/upload", methods=["POST"])
def upload_file():
    """
    Upload a document for analysis.
    
    Accepts: Excel (.xlsx, .xls) and PDF files
    Returns: Document info after ingestion
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            "error": f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    try:
        # Secure filename and save to uploads
        filename = secure_filename(file.filename)
        upload_path = guard.upload_dir / filename
        
        file.save(str(upload_path))
        
        logger.log(
            "file_uploaded",
            "ingestion",
            {"filename": filename}
        )
        
        # Ingest the file to registry (meta)
        registry = get_document_registry()
        entry = registry.ingest_file(upload_path)
        
        # Ingest the file to vector store (RAG)
        retriever = get_retriever()
        retriever.ingest_document(str(upload_path))
        
        return jsonify({
            "success": True,
            "document": {
                "id": entry.id,
                "filename": entry.filename,
                "type": entry.doc_type,
                "ingested_at": entry.ingested_at
            }
        })
        
    except SecurityViolationError as e:
        logger.log_security_event("upload_violation", str(e))
        return jsonify({"error": "Security violation"}), 403
    
    except Exception as e:
        logger.log(
            "upload_error",
            "ingestion",
            {"error": str(e)},
            status="error"
        )
        return jsonify({"error": str(e)}), 500


@api.route("/ingest-folder", methods=["POST"])
def ingest_folder():
    """
    Ingest all documents from a folder.
    
    Expects JSON: {"folder_path": "path/to/folder"}
    Returns: List of ingested documents
    """
    data = request.get_json() or {}
    folder_path = data.get("folder_path")
    
    if not folder_path:
        # Default to uploads folder
        folder_path = str(guard.upload_dir)
    
    try:
        # Validate path is safe
        safe_path = guard.validate_path(folder_path)
        
        # Ingest folder to registry
        registry = get_document_registry()
        entries = registry.ingest_folder(safe_path)
        
        # Ingest folder to vector store (RAG)
        retriever = get_retriever()
        retriever.ingest_folder(str(safe_path))
        
        # Get ingestion confirmation message
        handler = get_response_handler()
        confirmation = handler.handle_ingestion()
        
        return jsonify({
            "success": True,
            "documents_ingested": len(entries),
            "documents": [
                {
                    "id": e.id,
                    "filename": e.filename,
                    "type": e.doc_type
                }
                for e in entries
            ],
            "message": confirmation
        })
        
    except SecurityViolationError as e:
        return jsonify({"error": "Security violation: Path outside allowed folder"}), 403
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/refresh-uploads", methods=["POST"])
def refresh_uploads():
    """
    Refresh and ingest all documents from the uploads folder.
    
    Returns the file list immediately and processes everything
    in a background thread to avoid request timeout.
    """
    import threading
    
    try:
        guard = get_folder_guard()
        
        # Quickly scan for files (no parsing)
        valid_extensions = {'.xlsx', '.xls', '.pdf'}
        files_found = []
        upload_path = guard.upload_dir
        
        if upload_path.exists():
            for f in upload_path.iterdir():
                if f.is_file() and f.suffix.lower() in valid_extensions:
                    file_type = "excel" if f.suffix.lower() in {'.xlsx', '.xls'} else "pdf"
                    files_found.append({
                        "name": f.name,
                        "type": file_type
                    })
        
        if not files_found:
            return jsonify({"error": "No documents found in uploads folder"}), 400
        
        # Run ALL ingestion in background thread
        def background_ingest():
            try:
                registry = get_document_registry()
                registry.ingest_folder(upload_path)
                
                retriever = get_retriever()
                retriever.ingest_folder(str(upload_path))
                print(f"[BACKGROUND] Successfully ingested {len(files_found)} documents")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[BACKGROUND] Ingestion error: {e}")
        
        thread = threading.Thread(target=background_ingest, daemon=True)
        thread.start()
        
        # Build file list for response
        file_list = "\n".join([f"- {f['name']} ({f['type']})" for f in files_found])
        message = f"The insurance data folder has been successfully ingested.\n**Documents found:**\n{file_list}\n\n_Documents are being processed in the background. You can start asking questions shortly._"
        
        return jsonify({
            "success": True,
            "documents_ingested": len(files_found),
            "documents": files_found,
            "message": message
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@api.route("/load-folder-path", methods=["POST"])
def load_folder_path():
    """
    Load documents from an external folder path.
    
    This endpoint copies files from an external folder into the uploads directory,
    then ingests them. This allows loading from any folder on the system.
    
    Expects JSON: {"folder_path": "C:\\path\\to\\folder"}
    Returns: List of ingested documents
    """
    import shutil
    
    data = request.get_json() or {}
    folder_path = data.get("folder_path", "").strip()
    
    if not folder_path:
        return jsonify({"error": "No folder path provided"}), 400
    
    try:
        source_path = Path(folder_path)
        
        if not source_path.exists():
            return jsonify({"error": f"Folder not found: {folder_path}"}), 404
        
        if not source_path.is_dir():
            return jsonify({"error": f"Path is not a folder: {folder_path}"}), 400
        
        # Find all valid files in the source folder (recursive)
        valid_extensions = {".xlsx", ".xls", ".pdf"}
        files_copied = []
        files_skipped = []
        
        for file in source_path.rglob("*"):
            if file.is_file() and file.suffix.lower() in valid_extensions:
                try:
                    # Use secure filename and copy to uploads
                    safe_name = secure_filename(file.name)
                    dest_path = guard.upload_dir / safe_name
                    
                    # Skip if file already exists (no duplicates)
                    if dest_path.exists():
                        files_skipped.append({"file": file.name, "reason": "already_exists"})
                        continue
                    
                    shutil.copy2(str(file), str(dest_path))
                    files_copied.append(dest_path.name)
                    
                    logger.log(
                        "file_copied",
                        "ingestion",
                        {"source": str(file), "destination": str(dest_path)}
                    )
                    
                except Exception as e:
                    files_skipped.append({"file": file.name, "error": str(e)})
        
        # Now ingest from uploads folder (includes existing + newly copied)
        registry = get_document_registry()
        entries = registry.ingest_folder(guard.upload_dir)
        
        # If nothing was ingested and nothing was copied, show error
        if not files_copied and not entries:
            return jsonify({
                "error": f"No valid files found. Supported: {', '.join(valid_extensions)}"
            }), 400
        
        # Ingest to vector store (RAG) in background thread
        import threading
        upload_dir = str(guard.upload_dir)
        def background_ingest():
            try:
                retriever = get_retriever()
                retriever.ingest_folder(upload_dir)
            except Exception as e:
                print(f"[BACKGROUND] Embedding error: {e}")
        
        thread = threading.Thread(target=background_ingest, daemon=True)
        thread.start()
        
        # Get ingestion confirmation message
        handler = get_response_handler()
        confirmation = handler.handle_ingestion()
        
        return jsonify({
            "success": True,
            "files_copied": len(files_copied),
            "files_skipped": len(files_skipped),
            "documents_ingested": len(entries),
            "message": confirmation + "\n\n_Vector embeddings are being generated in the background. Please wait a moment before asking questions._"
        })
        
    except Exception as e:
        logger.log(
            "load_folder_error",
            "ingestion",
            {"folder_path": folder_path, "error": str(e)},
            status="error"
        )
        return jsonify({"error": str(e)}), 500


@api.route("/documents", methods=["GET"])
def list_documents():
    """List all ingested documents."""
    registry = get_document_registry()
    documents = registry.list_documents()
    
    return jsonify({
        "documents": documents,
        "count": len(documents)
    })


@api.route("/documents/<doc_id>", methods=["GET"])
def get_document(doc_id: str):
    """Get details for a specific document."""
    registry = get_document_registry()
    summary = registry.get_document_summary(doc_id)
    
    if "error" in summary:
        return jsonify(summary), 404
    
    return jsonify(summary)


@api.route("/chat", methods=["POST"])
def chat():
    """
    Process a chat message.
    
    Expects JSON: {"message": "user message"}
    Returns: Assistant response
    """
    data = request.get_json() or {}
    message = data.get("message", "").strip()
    
    if not message:
        return jsonify({"error": "No message provided"}), 400
    
    try:
        handler = get_response_handler()
        response = handler.process_message(message)
        
        return jsonify({
            "response": response,
            "documents_loaded": len(get_document_registry().list_documents())
        })
        
    except Exception as e:
        logger.log(
            "chat_error",
            "chat",
            {"error": str(e)},
            status="error"
        )
        return jsonify({"error": str(e)}), 500


@api.route("/chat/clear", methods=["POST"])
def clear_chat():
    """Clear chat history."""
    handler = get_response_handler()
    handler.clear_history()
    
    return jsonify({"success": True, "message": "Chat history cleared"})


@api.route("/analyze/executive-summary", methods=["GET"])
def executive_summary():
    """Get executive summary of all documents."""
    try:
        handler = get_response_handler()
        summary = handler.handle_executive_summary()
        
        return jsonify({"summary": summary})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/analyze/document/<doc_id>", methods=["GET"])
def analyze_document(doc_id: str):
    """Analyze a specific document."""
    try:
        handler = get_response_handler()
        analysis = handler.handle_document_analysis(doc_id)
        
        return jsonify({"analysis": analysis})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/analyze/sheet/<doc_id>/<sheet_name>", methods=["GET"])
def analyze_sheet(doc_id: str, sheet_name: str):
    """Analyze a specific Excel sheet."""
    try:
        handler = get_response_handler()
        analysis = handler.handle_sheet_analysis(doc_id, sheet_name)
        
        return jsonify({"analysis": analysis})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/analyze/formulas/<doc_id>/<sheet_name>", methods=["GET"])
def analyze_formulas(doc_id: str, sheet_name: str):
    """Analyze formulas in a specific sheet."""
    try:
        handler = get_response_handler()
        analysis = handler.handle_formula_analysis(doc_id, sheet_name)
        
        return jsonify({"analysis": analysis})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api.route("/analyze/calculation-type", methods=["GET"])
def identify_calculation_type():
    """Identify calculation types in documents."""
    doc_id = request.args.get("doc_id")
    
    try:
        handler = get_response_handler()
        analysis = handler.handle_calculation_type(doc_id)
        
        return jsonify({"analysis": analysis})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
