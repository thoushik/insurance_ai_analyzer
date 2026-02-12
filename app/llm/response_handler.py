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
        
        import re
        # Try to find a specific cell reference in the message (e.g. F24, AA12)
        # Look for pattern: word boundary, 1-2 letters, 1-3 digits, word boundary
        target_cell = None
        
        # We need the message to extract the cell. 
        # Since handle_formula_analysis doesn't take message, we'll try to find it 
        # in self.messages[-1] if it exists and is from user.
        last_message = ""
        if self.messages and self.messages[-1]["role"] == "user":
            last_message = self.messages[-1]["content"]
            
        cell_match = re.search(r'\b([A-Z]{1,2}[0-9]{1,3})\b', last_message.upper())
        if cell_match:
            target_cell = cell_match.group(1)
        
        # If we have a target cell, filter formulas to ONLY include that one + dependencies
        # This prevents the LLM from seeing other formulas and getting confused
        if target_cell:
            # Check if we have the specific formula
            specific_formula = next((f for f in formulas if f['cell'] == target_cell), None)
            
            if specific_formula:
                # Found it! Show full rich metadata
                formula_text = f"""CONFIRMED METADATA FOUND:
- Cell: {specific_formula['cell']}
- Formula: {specific_formula['formula']}
- Value: {specific_formula.get('value', 'N/A')}
- Data Type: {specific_formula.get('data_type', 'unknown')}
- Number Format: {specific_formula.get('number_format', 'General')}"""
            else:
                # Not found in metadata. 
                # We still pass the target_cell to the prompt so the LLM knows what to look for
                # and can fail properly.
                formula_text = f"CRITICAL: The specific formula for {target_cell} was NOT found in the sheet metadata. The user is asking about {target_cell}, but it is not in the index. You must state that the cell was not found."
        else:
            # Fallback to showing all samples if no specific cell asked
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
            sheet_context=sheet_context,
            target_cell=target_cell
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
            # RAG chain returns a RAGResponse object
            if hasattr(response, 'answer'):
                return response.answer
            # Fallback for dict (if changed later)
            if isinstance(response, dict) and 'answer' in response:
                return response['answer']
            return str(response)
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                self.logger.log(
                    "rate_limit_exceeded",
                    "chat",
                    {"error": error_msg},
                    status="warning"
                )
                return "⚠️ **Rate Limit Exceeded:** The AI service is currently busy. Please wait a few minutes and try again."
            
            self.logger.log(
                "rag_error",
                "chat",
                {"error": error_msg},
                status="error"
            )
            return f"I encountered an error while processing your request: {error_msg}"
    
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
        
        # Smart Routing for Excel: Check if message mentions a specific sheet
        # This bypasses RAG for specific formula/sheet questions to ensure 100% retrieval reliability
        for doc_id, entry in self.registry.documents.items():
            if entry.doc_type == "excel":
                for sheet in entry.metadata.get("sheets", []):
                    sheet_name = sheet["name"]
                    # distinct check: ensure sheet name is actually in the message
                    if sheet_name.lower() in message_lower:
                        self.logger.log(
                            "smart_routing_triggered",
                            "chat",
                            {"sheet": sheet_name, "doc": entry.filename}
                        )
                        
                        # Check for formula/cell specific intent
                        if any(kw in message_lower for kw in ["formula", "calc", "value", "cell", "row", "col", "f24"]):
                            return self.handle_formula_analysis(doc_id, sheet_name)
                        else:
                            return self.handle_sheet_analysis(doc_id, sheet_name)

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
