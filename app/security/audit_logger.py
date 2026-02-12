"""
Insurance Document Intelligence Assistant
Security Module - Audit Logger

Provides comprehensive logging with timestamps for SR 11-7 compliance.
All user actions, document access, queries, and responses are logged.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from functools import wraps

from .folder_guard import get_folder_guard


class AuditLogger:
    """
    SR 11-7 compliant audit logging system.
    
    Features:
    - Timestamps on all actions
    - JSON-structured logs for auditability
    - Separate log files by date
    - User action tracking
    - Document access logging
    - Query and response logging
    """
    
    def __init__(self):
        self.guard = get_folder_guard()
        self.logs_dir = self.guard.logs_dir
        
        # Set up Python logger
        self.logger = logging.getLogger("insurance_ai_audit")
        self.logger.setLevel(logging.DEBUG)
        
        # Daily rotating file handler
        self._setup_handler()
    
    def _setup_handler(self):
        """Set up file handler for current date."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"audit_{today}.log"
        
        # Remove old handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add file handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        
        # JSON formatter
        formatter = logging.Formatter("%(message)s")
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        
        # Also add console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            "[%(levelname)s] %(message)s"
        ))
        self.logger.addHandler(console_handler)
    
    def _create_log_entry(
        self,
        action: str,
        category: str,
        details: dict = None,
        user_input: str = None,
        status: str = "success"
    ) -> dict:
        """Create a structured log entry."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "category": category,
            "status": status,
        }
        
        if user_input:
            entry["user_input"] = user_input[:500]  # Truncate long inputs
        
        if details:
            entry["details"] = details
        
        return entry
    
    @staticmethod
    def _json_serializer(obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def log(
        self,
        action: str,
        category: str,
        details: dict = None,
        user_input: str = None,
        status: str = "success"
    ):
        """
        Log an action with full audit trail.
        
        Args:
            action: The action being performed (e.g., "document_upload", "query")
            category: Category of action (e.g., "security", "ingestion", "chat")
            details: Additional details as a dictionary
            user_input: User input that triggered the action
            status: Status of the action ("success", "error", "warning")
        """
        entry = self._create_log_entry(action, category, details, user_input, status)
        
        try:
            log_line = json.dumps(entry, ensure_ascii=False, default=self._json_serializer)
            
            if status == "error":
                self.logger.error(log_line)
            elif status == "warning":
                self.logger.warning(log_line)
            else:
                self.logger.info(log_line)
        except Exception as e:
            # Fallback logging if serialization fails
            self.logger.error(f"Failed to log entry: {str(e)}")
    
    def log_document_access(
        self,
        document_path: str,
        access_type: str,
        user_input: str = None
    ):
        """Log document access for audit trail."""
        self.log(
            action="document_access",
            category="ingestion",
            details={
                "document": str(document_path),
                "access_type": access_type
            },
            user_input=user_input
        )
    
    def log_query(
        self,
        query: str,
        query_type: str,
        document_context: list = None
    ):
        """Log a user query."""
        self.log(
            action="user_query",
            category="chat",
            details={
                "query_type": query_type,
                "documents_referenced": document_context or []
            },
            user_input=query
        )
    
    def log_response(
        self,
        response_type: str,
        response_length: int,
        documents_used: list = None
    ):
        """Log an LLM response."""
        self.log(
            action="llm_response",
            category="chat",
            details={
                "response_type": response_type,
                "response_length": response_length,
                "documents_used": documents_used or []
            }
        )
    
    def log_security_event(
        self,
        event_type: str,
        description: str,
        severity: str = "warning"
    ):
        """Log a security-related event."""
        self.log(
            action="security_event",
            category="security",
            details={
                "event_type": event_type,
                "description": description,
                "severity": severity
            },
            status="warning" if severity != "critical" else "error"
        )
    
    def log_ingestion(
        self,
        document_name: str,
        document_type: str,
        success: bool,
        metadata: dict = None
    ):
        """Log document ingestion."""
        self.log(
            action="document_ingestion",
            category="ingestion",
            details={
                "document_name": document_name,
                "document_type": document_type,
                "metadata": metadata or {}
            },
            status="success" if success else "error"
        )
    
    def get_recent_logs(self, count: int = 50) -> list[dict]:
        """
        Get recent log entries for display.
        
        Args:
            count: Number of recent entries to return
            
        Returns:
            List of log entry dictionaries
        """
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = self.logs_dir / f"audit_{today}.log"
        
        if not log_file.exists():
            return []
        
        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
        
        return entries[-count:]


# Decorator for auditing function calls
def audit_action(action: str, category: str):
    """Decorator to automatically audit function calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_audit_logger()
            
            try:
                result = func(*args, **kwargs)
                logger.log(
                    action=action,
                    category=category,
                    details={"function": func.__name__},
                    status="success"
                )
                return result
            except Exception as e:
                logger.log(
                    action=action,
                    category=category,
                    details={"function": func.__name__, "error": str(e)},
                    status="error"
                )
                raise
        
        return wrapper
    return decorator


# Global instance
_logger = None

def get_audit_logger() -> AuditLogger:
    """Get the global AuditLogger instance."""
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger
