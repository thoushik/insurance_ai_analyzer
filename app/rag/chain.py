"""
Insurance Document Intelligence Assistant
RAG Module - Chain

LangChain-based RAG chain for grounded responses.
"""

import os
from typing import Optional
from dataclasses import dataclass

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from .retriever import get_retriever, DocumentRetriever
from ..security import get_audit_logger, get_pii_masker


# RAG System Prompt - SR 11-7 compliant
RAG_SYSTEM_PROMPT = """You are an Insurance Document Intelligence Assistant designed for actuarial, regulatory, and risk analysis.

You are answering questions using ONLY the retrieved document context provided below.

CRITICAL RULES:
1. Use ONLY information from the provided context
2. Do NOT invent formulas, calculations, or assumptions
3. If information is not in the context, say: "This information was not found in the provided documents."
4. Always cite your sources using [Source N] references
5. Explain insurance concepts clearly for actuaries and regulators

FORMULA FORMATTING:
- Display formulas in code format using backticks: `=FORMULA_HERE`
- Number each formula explanation (1., 2., 3., etc.)
- Bold formula names: **Formula Name:**
- Explain what each formula calculates in plain language

Follow SR 11-7 principles:
- Explainability
- Traceability  
- No hallucination"""


RAG_PROMPT_TEMPLATE = """CONTEXT (Retrieved from uploaded documents):
{context}

---

USER QUESTION:
{question}

Please answer based ONLY on the context above. Cite sources using [Source N] format.

---
**Would you like to:**
1. Deep dive into another document
2. Explore a specific Excel sheet
3. Ask about a specific calculation or formula
4. Return to a high-level summary"""


@dataclass
class RAGResponse:
    """Response from RAG chain."""
    answer: str
    sources: list
    query: str
    
    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "sources": self.sources,
            "query": self.query
        }


class RAGChain:
    """
    LangChain-based RAG chain for grounded responses.
    
    Features:
    - Groq LLM integration via LangChain
    - Automatic context retrieval
    - Source citation tracking
    - PII masking integration
    """
    
    def __init__(self, model_name: str = None):
        self.logger = get_audit_logger()
        self.pii_masker = get_pii_masker()
        self.retriever = get_retriever()
        
        # Get model from env or use default
        self.model_name = model_name or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        
        # Initialize Groq via LangChain
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        
        self.llm = ChatGroq(
            api_key=api_key,
            model_name=self.model_name,
            temperature=0.1,  # Low temperature for factual responses
            max_tokens=2000
        )
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            ("human", RAG_PROMPT_TEMPLATE)
        ])
        
        self.logger.log(
            "rag_chain_initialized",
            "rag",
            {"model": self.model_name}
        )
    
    def invoke(
        self,
        question: str,
        k: int = 5,
        mask_pii: bool = True
    ) -> RAGResponse:
        """
        Process a question through the RAG chain.
        
        Args:
            question: User's question
            k: Number of documents to retrieve
            mask_pii: Whether to mask PII in response
            
        Returns:
            RAGResponse with answer and sources
        """
        # 1. Retrieve relevant context
        retrieval_results = self.retriever.retrieve(question, k=k)
        
        # 2. Build context string with source numbers
        context_parts = []
        sources = []
        
        for i, result in enumerate(retrieval_results, 1):
            context_parts.append(
                f"[Source {i}: {result.source}]\n{result.text}"
            )
            sources.append({
                "index": i,
                "source": result.source,
                "chunk_type": result.chunk_type,
                "relevance": round(result.relevance_score, 3),
                "text": result.text
            })
        
        context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant documents found."
        
        # 3. Format prompt
        messages = self.prompt.format_messages(
            context=context,
            question=question
        )
        
        # 4. Generate response
        try:
            response = self.llm.invoke(messages)
            answer = response.content
        except Exception as e:
            self.logger.log(
                "rag_generation_error",
                "rag",
                {"error": str(e)},
                status="error"
            )
            answer = f"Error generating response: {str(e)}"
        
        # 5. Optionally mask PII
        if mask_pii:
            answer = self.pii_masker.mask_text(answer)
        
        # 6. Log the query
        self.logger.log_query(
            query=question[:100],
            query_type="rag_query",
            document_context=[s["source"] for s in sources]
        )
        
        return RAGResponse(
            answer=answer,
            sources=sources,
            query=question
        )
    
    def chat(
        self,
        message: str,
        k: int = 5
    ) -> str:
        """
        Simple chat interface that returns just the answer.
        
        Args:
            message: User message
            k: Number of documents to retrieve
            
        Returns:
            Answer string
        """
        response = self.invoke(message, k=k)
        return response.answer
    
    def get_stats(self) -> dict:
        """Get chain statistics."""
        return {
            "model": self.model_name,
            "retriever_stats": self.retriever.get_stats()
        }


# Global instance
_chain = None


def get_rag_chain() -> RAGChain:
    """Get the global RAGChain instance."""
    global _chain
    if _chain is None:
        _chain = RAGChain()
    return _chain
