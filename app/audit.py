"""
Security & compliance: audit log with timestamp and user input.
PII masking if detected; all actions logged; no data leaves local environment.
SR 11-7 model risk expectations.
"""
import re
import logging
from datetime import datetime
from pathlib import Path

try:
    from app.config import get_logs_dir
except ImportError:
    try:
        from config import get_logs_dir
    except ImportError:
        get_logs_dir = lambda: Path(__file__).resolve().parent.parent / "logs"

# Simple PII patterns (mask in logs)
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

def mask_pii(text: str) -> str:
    if not text:
        return text
    t = SSN_PATTERN.sub("[SSN_REDACTED]", text)
    t = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", t)
    return t

def _ensure_log_dir():
    d = get_logs_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d

def setup_audit_logger():
    log_dir = _ensure_log_dir()
    log_file = log_dir / "audit.log"
    logger = logging.getLogger("insurance_ai_audit")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
        logger.addHandler(fh)
    return logger

_audit_logger = None

def get_audit_logger():
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = setup_audit_logger()
    return _audit_logger

def log_action(action: str, user_input: str = "", extra: str = ""):
    logger = get_audit_logger()
    safe_input = mask_pii(user_input)
    msg = f"action={action} | user_input={safe_input}"
    if extra:
        msg += f" | {extra}"
    logger.info(msg)
