"""
Insurance Document Intelligence Assistant
Security Module

Provides folder-safety, audit logging, and PII masking.
"""

from .folder_guard import FolderGuard, SecurityViolationError, get_folder_guard, require_safe_path
from .audit_logger import AuditLogger, get_audit_logger, audit_action
from .pii_masker import PIIMasker, get_pii_masker

__all__ = [
    "FolderGuard",
    "SecurityViolationError", 
    "get_folder_guard",
    "require_safe_path",
    "AuditLogger",
    "get_audit_logger",
    "audit_action",
    "PIIMasker",
    "get_pii_masker",
]
