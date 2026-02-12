"""
Insurance Document Intelligence Assistant
LLM Module - Groq Client

Provides integration with Groq API for fast LLM inference.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from groq import Groq

from ..security import get_audit_logger, get_pii_masker


class LLMClient:
    """
    Groq API client for Insurance Document Intelligence.
    
    Features:
    - Fast inference with Llama 3
    - Token usage tracking
    - Error handling and retry
    - Context management
    """
    
    def __init__(self):
        load_dotenv()
        
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        # Initialize Groq client without proxy settings
        try:
            import httpx
            # Create a custom httpx client without proxy
            http_client = httpx.Client(timeout=60.0)
            self.client = Groq(api_key=self.api_key, http_client=http_client)
        except Exception:
            # Fallback to default initialization
            self.client = Groq(api_key=self.api_key)
        
        self.logger = get_audit_logger()
        self.pii_masker = get_pii_masker()
        
        # Token tracking
        self.total_tokens_used = 0
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        mask_pii: bool = True
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            temperature: Creativity (0.0-1.0)
            max_tokens: Maximum response tokens
            mask_pii: Whether to mask PII before sending
            
        Returns:
            Generated response text
        """
        # Mask PII if enabled
        if mask_pii:
            masked_prompt, mask_report = self.pii_masker.mask(prompt)
            if mask_report:
                self.logger.log(
                    "pii_masked",
                    "security",
                    {"types_masked": list(mask_report.keys())}
                )
        else:
            masked_prompt = prompt
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": masked_prompt
        })
        
        try:
            return self._make_request_with_retry(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
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
            
            if "503" in error_msg or "over capacity" in error_msg.lower():
                self.logger.log(
                    "service_overloaded",
                    "chat",
                    {"error": error_msg},
                    status="warning"
                )
                return "⚠️ **Service Busy:** The AI model is currently over capacity. Please try again in a few moments."

            self.logger.log(
                "llm_error",
                "chat",
                {"error": error_msg},
                status="error"
            )
            # Return a friendly error instead of crashing
            return f"⚠️ **AI Error:** {error_msg}"
    
    def _make_request_with_retry(self, messages, temperature, max_tokens, retries=3):
        """Make API request with exponential backoff retry."""
        import time
        import random
        
        last_error = None
        
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                # Track tokens
                usage = response.usage
                if usage:
                    self.total_tokens_used += usage.total_tokens
                
                result = response.choices[0].message.content
                
                self.logger.log_response(
                    "llm_generation",
                    len(result),
                    []
                )
                
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Only retry on rate limits or service overload
                if "429" in error_msg or "503" in error_msg or "rate limit" in error_msg or "capacity" in error_msg:
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(sleep_time)
                    continue
                else:
                    raise e
        
        raise last_error
    
    def chat(
        self,
        messages: list[dict],
        system_prompt: str = None,
        temperature: float = 0.3,
        max_tokens: int = 4096
    ) -> str:
        """
        Multi-turn chat conversation.
        
        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
            system_prompt: System instructions
            temperature: Creativity
            max_tokens: Maximum response tokens
            
        Returns:
            Assistant response
        """
        all_messages = []
        
        if system_prompt:
            all_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Mask PII in all messages
        for msg in messages:
            masked_content, _ = self.pii_masker.mask(msg["content"])
            all_messages.append({
                "role": msg["role"],
                "content": masked_content
            })
        
        try:
            return self._make_request_with_retry(
                messages=all_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
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

            if "503" in error_msg or "over capacity" in error_msg.lower():
                self.logger.log(
                    "service_overloaded",
                    "chat",
                    {"error": error_msg},
                    status="warning"
                )
                return "⚠️ **Service Busy:** The AI model is currently over capacity. Please try again in a few moments."

            self.logger.log(
                "llm_chat_error",
                "chat",
                {"error": error_msg},
                status="error"
            )
            return f"⚠️ **AI Error:** {error_msg}"
    
    def get_token_usage(self) -> int:
        """Get total tokens used in this session."""
        return self.total_tokens_used


# Global instance
_client = None

def get_llm_client() -> LLMClient:
    """Get the global LLMClient instance."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
