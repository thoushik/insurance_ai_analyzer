"""
Insurance Document Intelligence Assistant
LLM Module - Response Handler

Handles chat logic, context building, and response formatting.
"""

import json
from typing import Optional

from .client import get_llm_client
from .prompts import (
    get_system_prompt,
    get_ingestion_confirmation,
    get_executive_summary_prompt,
    get_document_prompt,
    get_sheet_prompt,
    get_formula_prompt,
    get_calculation_type_prompt,
    NOT_FOUND_RESPONSE,
    INTERACTIVE_FOLLOWUP
)
from ..ingestion import get_document_registry
from ..security import get_audit_logger
from ..rag.chain import get_rag_chain  # Added for RAG


class ResponseHandler:
    """
    Handles chat interactions and response generation.
    
    Features:
    - Context-aware responses
    - Document reference tracking
    - Interactive follow-up management
    - SR 11-7 compliant responses
    """
    
    def __init__(self):
        self.llm = get_llm_client()
        self.registry = get_document_registry()
        self.logger = get_audit_logger()
        self.rag_chain = get_rag_chain()  # Initialize RAG
        
        # Chat history
        self.messages: list[dict] = []
        
        # Current context
        self.current_document = None
        self.current_sheet = None
    
    def handle_ingestion(self) -> str:
        """
        Handle document ingestion and return confirmation.
        
        Returns:
            Formatted ingestion confirmation message
        """
        documents = self.registry.list_documents()
        
        if not documents:
            return "No documents have been uploaded yet. Please upload Excel (.xlsx) or PDF files to begin analysis."
        
        self.logger.log_query(
            "folder_ingestion",
            "ingestion_confirmation",
            [d["filename"] for d in documents]
        )
        
        return get_ingestion_confirmation(documents)
    
    def handle_executive_summary(self) -> str:
        """
        Generate an executive summary of all documents.
        
        Returns:
            2-paragraph executive summary
        """
        context = self.registry.get_all_context()
        
        if not context:
            return NOT_FOUND_RESPONSE
        
        prompt = get_executive_summary_prompt(context)
        
        self.logger.log_query(
            "executive_summary",
            "executive_summary",
            [d["filename"] for d in self.registry.list_documents()]
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=get_system_prompt()
        )
        
        # Ensure follow-up is appended
        if "Would you like to" not in response:
            response += INTERACTIVE_FOLLOWUP
        
        return response
    
    def handle_document_analysis(self, doc_id: str) -> str:
        """
        Analyze a specific document.
        
        Args:
            doc_id: Document ID to analyze
            
        Returns:
            Document analysis response
        """
        entry = self.registry.get_document(doc_id)
        
        if not entry:
            return NOT_FOUND_RESPONSE
        
        self.current_document = doc_id
        
        details = json.dumps(entry.metadata, indent=2, default=str)
        
        prompt = get_document_prompt(
            name=entry.filename,
            doc_type=entry.doc_type,
            details=details
        )
        
        self.logger.log_query(
            f"document_analysis:{entry.filename}",
            "document_analysis",
            [entry.filename]
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=get_system_prompt()
        )
        
        if "Would you like to" not in response:
            response += INTERACTIVE_FOLLOWUP
        
        return response
    
    def handle_sheet_analysis(
        self,
        doc_id: str,
        sheet_name: str
    ) -> str:
        """
        Analyze a specific Excel sheet.
        
        Args:
            doc_id: Document ID
            sheet_name: Sheet name to analyze
            
        Returns:
            Sheet analysis response
        """
        entry = self.registry.get_document(doc_id)
        
        if not entry or entry.doc_type != "excel":
            return NOT_FOUND_RESPONSE
        
        self.current_document = doc_id
        self.current_sheet = sheet_name
        
        # Find sheet in metadata
        sheet_info = None
        for sheet in entry.metadata.get("sheets", []):
            if sheet["name"] == sheet_name:
                sheet_info = sheet
                break
        
        if not sheet_info:
            return f"Sheet '{sheet_name}' was not found in {entry.filename}."
        
        details = json.dumps(sheet_info, indent=2, default=str)
        
        prompt = get_sheet_prompt(
            doc_name=entry.filename,
            sheet_name=sheet_name,
            details=details
        )
        
        self.logger.log_query(
            f"sheet_analysis:{entry.filename}:{sheet_name}",
            "sheet_analysis",
            [entry.filename]
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=get_system_prompt()
        )
        
        if "Would you like to" not in response:
            response += INTERACTIVE_FOLLOWUP
        
        return response
    
    def handle_formula_analysis(
        self,
        doc_id: str,
        sheet_name: str
    ) -> str:
        """
        Analyze formulas in a specific sheet.
        
        Args:
            doc_id: Document ID
            sheet_name: Sheet name
            
        Returns:
            Formula analysis response
        """
        entry = self.registry.get_document(doc_id)
        
        if not entry or entry.doc_type != "excel":
            return NOT_FOUND_RESPONSE
        
        # Find sheet and its formulas
        sheet_info = None
        for sheet in entry.metadata.get("sheets", []):
            if sheet["name"] == sheet_name:
                sheet_info = sheet
                break
        
        if not sheet_info:
            return f"Sheet '{sheet_name}' was not found in {entry.filename}."
        
        formulas = sheet_info.get("sample_formulas", [])
        
        if not formulas:
            return f"No formulas were extracted from sheet '{sheet_name}'. The sheet may contain only values, or formulas may be protected."
        
        formula_text = "\n".join(
            f"- Cell {f['cell']}: {f['formula']}"
            for f in formulas
        )

        # Build sheet context from metadata
        context_parts = []
        if sheet_info.get("purpose"):
            context_parts.append(f"Sheet Purpose: {sheet_info['purpose']}")
        if sheet_info.get("headers"):
            context_parts.append(f"Columns: {', '.join(sheet_info['headers'])}")
        if sheet_info.get("row_count"):
            context_parts.append(f"Rows: {sheet_info['row_count']}")
        
        sheet_context = "\n".join(context_parts)
        
        prompt = get_formula_prompt(
            doc_name=entry.filename,
            sheet_name=sheet_name,
            formulas=formula_text,
            sheet_context=sheet_context
        )
        
        self.logger.log_query(
            f"formula_analysis:{entry.filename}:{sheet_name}",
            "formula_analysis",
            [entry.filename]
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=get_system_prompt()
        )
        
        if "Would you like to" not in response:
            response += INTERACTIVE_FOLLOWUP
        
        return response
    
    def handle_calculation_type(
        self,
        doc_id: str = None
    ) -> str:
        """
        Identify the type of calculation in documents.
        
        Args:
            doc_id: Optional specific document, or all documents
            
        Returns:
            Calculation type analysis
        """
        if doc_id:
            entry = self.registry.get_document(doc_id)
            if not entry:
                return NOT_FOUND_RESPONSE
            context = json.dumps(entry.metadata, indent=2, default=str)
        else:
            context = self.registry.get_all_context()
        
        prompt = get_calculation_type_prompt(context)
        
        self.logger.log_query(
            "calculation_type_identification",
            "calculation_type",
            [d["filename"] for d in self.registry.list_documents()]
        )
        
        response = self.llm.generate(
            prompt=prompt,
            system_prompt=get_system_prompt()
        )
        
        if "Would you like to" not in response:
            response += INTERACTIVE_FOLLOWUP
        
        return response
    
    def handle_general_query(self, query: str) -> str:
        """
        Handle a general user query using RAG.
        
        Args:
            query: User's question
            
        Returns:
            RAG response
        """
        # Use RAG Chain for scalable, grounded answers
        try:
            response = self.rag_chain.invoke(query)
            return response.answer
            
        except Exception as e:
            self.logger.log(
                "rag_error",
                "chat",
                {"error": str(e)},
                status="error"
            )
            return f"I encountered an error while processing your request: {str(e)}"
    
    def process_message(self, message: str) -> str:
        """
        Process a user message and return appropriate response.
        
        Args:
            message: User message
            
        Returns:
            Response string
        """
        message_lower = message.lower().strip()
        
        # Store message in history
        self.messages.append({"role": "user", "content": message})
        
        # Detect intent
        if message_lower in ["yes", "1", "executive summary"]:
            response = self.handle_executive_summary()
        
        elif message_lower in ["2", "deep dive"] or "deep dive" in message_lower:
            # Show document list for selection
            docs = self.registry.list_documents()
            if docs:
                doc_list = "\n".join(
                    f"{i+1}. **{d['filename']}** ({d['type']})"
                    for i, d in enumerate(docs)
                )
                response = f"Select a document to analyze:\n\n{doc_list}\n\nReply with the document number or name."
            else:
                response = "No documents available. Please upload files first."
        
        elif message_lower in ["3", "specific calculation", "calculation"]:
            response = self.handle_calculation_type()
        
        elif message_lower in ["4", "high-level", "summary"]:
            response = self.handle_executive_summary()
        
        elif message_lower.isdigit():
            # User selected a document by number
            docs = self.registry.list_documents()
            idx = int(message_lower) - 1
            if 0 <= idx < len(docs):
                response = self.handle_document_analysis(docs[idx]["id"])
            else:
                response = "Invalid selection. Please try again."
        
        else:
            # General query
            response = self.handle_general_query(message)
        
        # Store response
        self.messages.append({"role": "assistant", "content": response})
        
        return response
    
    def clear_history(self):
        """Clear chat history."""
        self.messages.clear()
        self.current_document = None
        self.current_sheet = None


# Global instance
_handler = None

def get_response_handler() -> ResponseHandler:
    """Get the global ResponseHandler instance."""
    global _handler
    if _handler is None:
        _handler = ResponseHandler()
    return _handler
