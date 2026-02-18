"""
Insurance Document Intelligence Assistant
Security Module - PII Masker

Detects and masks Personally Identifiable Information (PII)
before sending to LLM for processing.

Supports dual-layer masking:
  Layer 1 - At ingestion (before chunking and embeddings)
  Layer 2 - Before sending context to LLM API

Controlled by ENABLE_PII_MASKING environment variable (default: True).
"""

import os
import re
import logging
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class PIIMasker:
    """
    Detects and masks PII in text using regex-based pattern matching.

    Supports:
    - Email addresses
    - Phone numbers (US and India)
    - SSN (US)
    - Aadhaar numbers (India)
    - PAN numbers (India)
    - Credit/debit card numbers
    - Bank account numbers (with keyword context)
    - Policy numbers
    - Claim numbers
    - Dates of birth
    - Addresses (US-style street/city/state/zip)

    All masking events are logged with counts only (never raw values).
    """

    def __init__(self):
        # Check configuration flag
        self._enabled = os.getenv("ENABLE_PII_MASKING", "True").lower() in ("true", "1", "yes")

        if not self._enabled:
            logger.warning(
                "PII masking is DISABLED via ENABLE_PII_MASKING=False. "
                "Raw PII may be stored in vector DB and sent to LLM."
            )

        # Compile regex patterns for efficiency
        # Order matters: more specific patterns first to avoid partial matches
        self.patterns = self._build_patterns()

        # Track what was masked for audit
        self.last_mask_report = {}

    def _build_patterns(self) -> dict:
        """Build all PII detection regex patterns."""
        return {
            # ── Email ──────────────────────────────────────────────
            "email": (
                re.compile(
                    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
                ),
                "[MASKED_EMAIL]"
            ),

            # ── Credit / Debit Card ────────────────────────────────
            # 13-19 digit card numbers with optional separators
            "credit_card": (
                re.compile(
                    r'\b(?:\d{4}[-\s]?){3}\d{1,4}\b'
                ),
                "[MASKED_ACCOUNT]"
            ),

            # ── SSN (US) ───────────────────────────────────────────
            # Format: XXX-XX-XXXX or XXX XX XXXX
            "ssn": (
                re.compile(
                    r'\b\d{3}[-\s]\d{2}[-\s]\d{4}\b'
                ),
                "[MASKED_SSN]"
            ),

            # ── Aadhaar (India) ────────────────────────────────────
            # Format: XXXX XXXX XXXX or XXXX-XXXX-XXXX
            "aadhaar": (
                re.compile(
                    r'\b\d{4}[-\s]\d{4}[-\s]\d{4}\b'
                ),
                "[MASKED_SSN]"
            ),

            # ── PAN (India) ────────────────────────────────────────
            # Format: ABCDE1234F (5 letters, 4 digits, 1 letter)
            "pan": (
                re.compile(
                    r'\b[A-Z]{5}\d{4}[A-Z]\b'
                ),
                "[MASKED_SSN]"
            ),

            # ── Policy Number ──────────────────────────────────────
            # Patterns: POL-123456, POL/123456, POLICY-123456, etc.
            "policy_number": (
                re.compile(
                    r'\b(?:POL|POLICY)[-/]?\d{6,}\b',
                    re.IGNORECASE
                ),
                "[MASKED_ACCOUNT]"
            ),

            # ── Claim Number ───────────────────────────────────────
            # Patterns: CLM-123456, CLAIM/123456, etc.
            "claim_number": (
                re.compile(
                    r'\b(?:CLM|CLAIM)[-/]?\d{6,}\b',
                    re.IGNORECASE
                ),
                "[MASKED_ACCOUNT]"
            ),

            # ── Phone (US) ────────────────────────────────────────
            # Formats: +1-xxx-xxx-xxxx, (xxx) xxx-xxxx, xxx.xxx.xxxx
            "phone_us": (
                re.compile(
                    r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
                ),
                "[MASKED_PHONE]"
            ),

            # ── Phone (India) ─────────────────────────────────────
            # Formats: +91-XXXXXXXXXX, 91XXXXXXXXXX, 0XXXXXXXXXX
            "phone_in": (
                re.compile(
                    r'\b(?:\+?91[-.\s]?|0)?[6-9]\d{9}\b'
                ),
                "[MASKED_PHONE]"
            ),

            # ── Date of Birth ──────────────────────────────────────
            # Formats: MM/DD/YYYY, MM-DD-YYYY, DD/MM/YYYY
            "dob": (
                re.compile(
                    r'\b(?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2}\b'
                ),
                "[MASKED_DOB]"
            ),

            # ── Bank Account Number ────────────────────────────────
            # Only match long digit sequences preceded by account-related keywords
            "bank_account": (
                re.compile(
                    r'(?:account|acct|a/c|bank\s*(?:account|acct))[\s#:.\-]*(\d{9,18})',
                    re.IGNORECASE
                ),
                "[MASKED_ACCOUNT]"
            ),

            # ── Address (US-style) ─────────────────────────────────
            # Match common street address patterns
            "address": (
                re.compile(
                    r'\b\d{1,6}\s+(?:[A-Z][a-z]+\s*){1,4}'
                    r'(?:Street|St|Avenue|Ave|Boulevard|Blvd|Drive|Dr|Lane|Ln|Road|Rd|Court|Ct|Way|Place|Pl)\b'
                    r'(?:\.?\s*,?\s*(?:Suite|Ste|Apt|Unit|#)\s*\d+)?',
                    re.IGNORECASE
                ),
                "[MASKED_ADDRESS]"
            ),
        }

    def mask(self, text: str) -> Tuple[str, dict]:
        """
        Mask all PII in the given text.

        Args:
            text: The text to mask

        Returns:
            Tuple of (masked_text, mask_report)
            mask_report contains counts of each PII type found
        """
        if not self._enabled:
            return text, {}

        if not text or not isinstance(text, str):
            return text, {}

        masked_text = text
        mask_report = {}

        for pii_type, (pattern, replacement) in self.patterns.items():
            # Bank account uses a capture group — replace only the number part
            if pii_type == "bank_account":
                matches = pattern.findall(masked_text)
                if matches:
                    mask_report[pii_type] = len(matches)
                    # Replace only the captured digit group
                    masked_text = pattern.sub(
                        lambda m: m.group(0).replace(m.group(1), replacement),
                        masked_text
                    )
            else:
                matches = pattern.findall(masked_text)
                if matches:
                    mask_report[pii_type] = len(matches)
                    masked_text = pattern.sub(replacement, masked_text)

        self.last_mask_report = mask_report

        # Log masking events (counts only, never raw values)
        if mask_report:
            logger.info(
                "PII masked: %s",
                {k: v for k, v in mask_report.items()}
            )

        return masked_text, mask_report

    def mask_text(self, text: str) -> str:
        """
        Mask PII and return only the masked text.

        Args:
            text: The text to mask

        Returns:
            Masked text string
        """
        masked, _ = self.mask(text)
        return masked

    def contains_pii(self, text: str) -> bool:
        """
        Check if text contains any PII without masking.

        Args:
            text: The text to check

        Returns:
            True if PII is detected, False otherwise
        """
        if not self._enabled:
            return False

        for pii_type, (pattern, _) in self.patterns.items():
            if pattern.search(text):
                return True
        return False

    def get_pii_locations(self, text: str) -> dict:
        """
        Get the locations of all PII in the text.

        Args:
            text: The text to analyze

        Returns:
            Dictionary mapping PII types to list of (start, end) positions
        """
        locations = {}

        for pii_type, (pattern, _) in self.patterns.items():
            matches = list(pattern.finditer(text))
            if matches:
                locations[pii_type] = [
                    (m.start(), m.end()) for m in matches
                ]

        return locations

    def add_custom_pattern(
        self,
        name: str,
        pattern: str,
        replacement: str
    ):
        """
        Add a custom PII pattern.

        Args:
            name: Name for the pattern
            pattern: Regex pattern string
            replacement: Replacement text when matched
        """
        self.patterns[name] = (re.compile(pattern), replacement)

    def mask_for_logging(self, text: str, max_length: int = 500) -> str:
        """
        Mask PII and truncate for safe logging.

        Args:
            text: The text to process
            max_length: Maximum length of output

        Returns:
            Masked and truncated text safe for logging
        """
        masked, _ = self.mask(text)
        if len(masked) > max_length:
            return masked[:max_length] + "... [TRUNCATED]"
        return masked

    @property
    def is_enabled(self) -> bool:
        """Check whether PII masking is currently enabled."""
        return self._enabled


# Global instance
_masker = None

def get_pii_masker() -> PIIMasker:
    """Get the global PIIMasker instance."""
    global _masker
    if _masker is None:
        _masker = PIIMasker()
    return _masker
