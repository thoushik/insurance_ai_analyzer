"""
Insurance Document Intelligence Assistant
Streamlit Frontend

A beautiful, interactive chat interface with document upload.
"""

import os
import sys
from pathlib import Path

import streamlit as st
import requests

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment
from dotenv import load_dotenv
load_dotenv()

# API endpoint
API_URL = os.getenv("API_URL", "http://localhost:8000")

# =============================================================================
# Page Configuration
# =============================================================================

st.set_page_config(
    page_title="InsuranceAI - Document Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# Custom CSS
# =============================================================================

st.markdown("""
<style>
    /* Main container */
    .main {
        background: linear-gradient(135deg, #0f0f23 0%, #1a1a3e 100%);
    }
    
    /* Header */
    .header-title {
        color: #00d4ff;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    .header-subtitle {
        color: #8892b0;
        font-size: 1.1rem;
    }
    
    /* Chat messages */
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    .assistant-message {
        background: #1e1e3f;
        border: 1px solid #3d3d6b;
        color: #e6e6e6;
    }
    
    /* Source citations */
    .source-citation {
        background: #2a2a4a;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-size: 0.85rem;
        color: #a0a0c0;
        margin-top: 0.5rem;
    }
    
    /* Compliance badge */
    .compliance-badge {
        background: linear-gradient(135deg, #00b4db 0%, #0083b0 100%);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    /* Document card */
    .doc-card {
        background: #1e1e3f;
        border: 1px solid #3d3d6b;
        border-radius: 8px;
        padding: 0.8rem;
        margin-bottom: 0.5rem;
    }
    
    /* Status indicator */
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 5px;
    }
    
    .status-ready {
        background: #00ff88;
    }
    
    .status-loading {
        background: #ffaa00;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# Session State
# =============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "documents" not in st.session_state:
    st.session_state.documents = []

if "api_healthy" not in st.session_state:
    st.session_state.api_healthy = False

# =============================================================================
# Helper Functions
# =============================================================================

def check_api_health():
    """Check if the API is healthy."""
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code == 200:
            st.session_state.api_healthy = True
            return response.json()
        return None
    except:
        st.session_state.api_healthy = False
        return None


def upload_files(files):
    """Upload files to the API."""
    try:
        files_data = [
            ("files", (f.name, f.getvalue(), "application/octet-stream"))
            for f in files
        ]
        response = requests.post(f"{API_URL}/api/upload", files=files_data, timeout=60)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def ingest_folder(folder_path):
    """Ingest a folder via the API."""
    try:
        response = requests.post(
            f"{API_URL}/api/ingest-folder",
            data={"folder_path": folder_path},
            timeout=120
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def chat_with_rag(message, k=5):
    """Send a chat message to the RAG API."""
    try:
        response = requests.post(
            f"{API_URL}/api/chat",
            json={"message": message, "k": k},
            timeout=60
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def get_documents():
    """Get list of documents from API."""
    try:
        response = requests.get(f"{API_URL}/api/documents", timeout=10)
        return response.json().get("documents", [])
    except:
        return []


def clear_vectorstore():
    """Clear the vector store."""
    try:
        response = requests.delete(f"{API_URL}/api/clear", timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


# =============================================================================
# Sidebar
# =============================================================================

with st.sidebar:
    st.markdown("### 📊 InsuranceAI")
    st.markdown('<span class="compliance-badge">SR 11-7 Compliant</span>', unsafe_allow_html=True)
    st.markdown("---")
    
    # Health check
    health = check_api_health()
    if health:
        st.success("🟢 API Connected")
        st.caption(f"Model: {health.get('model', 'Unknown')}")
        stats = health.get('vectorstore_stats', {})
        st.caption(f"Chunks in store: {stats.get('total_chunks', 0)}")
    else:
        st.error("🔴 API Not Connected")
        st.caption("Start API with: `python run_api.py`")
    
    st.markdown("---")
    
    # File upload
    st.markdown("### 📁 Upload Documents")
    uploaded_files = st.file_uploader(
        "Drop files here",
        type=["xlsx", "xls", "pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        if st.button("📤 Upload & Ingest", use_container_width=True):
            with st.spinner("Uploading and processing..."):
                result = upload_files(uploaded_files)
                if "error" in result:
                    st.error(f"Error: {result['error']}")
                else:
                    st.success(f"✅ {result.get('total_chunks', 0)} chunks created")
                    st.session_state.documents = get_documents()
    
    # Folder path input
    st.markdown("### 📂 Or Load Folder")
    folder_path = st.text_input("Folder path", placeholder="C:\\path\\to\\documents")
    
    if folder_path:
        if st.button("📥 Load Folder", use_container_width=True):
            with st.spinner("Loading folder..."):
                result = ingest_folder(folder_path)
                if "error" in result:
                    st.error(f"Error: {result['error']}")
                else:
                    st.success(f"✅ {result.get('total_chunks', 0)} chunks created")
                    st.session_state.documents = get_documents()
    
    st.markdown("---")
    
    # Documents list
    st.markdown("### 📄 Documents")
    docs = get_documents()
    st.session_state.documents = docs
    
    if docs:
        for doc in docs[:10]:  # Limit display
            doc_type = "📊" if doc.get("type") == "excel" else "📄"
            st.markdown(f"{doc_type} {doc.get('filename', 'Unknown')[:25]}")
    else:
        st.caption("No documents uploaded yet")
    
    st.markdown("---")
    
    # Actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.session_state.documents = get_documents()
            st.rerun()
    
    with col2:
        if st.button("🗑️ Clear", use_container_width=True):
            clear_vectorstore()
            st.session_state.messages = []
            st.session_state.documents = []
            st.rerun()

# =============================================================================
# Main Content
# =============================================================================

# Header
st.markdown('<h1 class="header-title">Insurance Document Intelligence</h1>', unsafe_allow_html=True)
st.markdown('<p class="header-subtitle">RAG-powered analysis with full traceability</p>', unsafe_allow_html=True)

# Retrieval settings
with st.expander("⚙️ Settings", expanded=False):
    k_value = st.slider("Number of chunks to retrieve", 1, 15, 5)

# Chat interface
st.markdown("---")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Show sources for assistant messages
        if message["role"] == "assistant" and "sources" in message:
            sources = message["sources"]
            if sources:
                with st.expander(f"📚 Sources ({len(sources)})"):
                    for src in sources:
                        st.markdown(f"**[{src['index']}]** {src['source']} - {src['chunk_type']} (relevance: {src['relevance']})")

# Chat input
if prompt := st.chat_input("Ask about your insurance documents..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = chat_with_rag(prompt, k=k_value)
            
            if "error" in response:
                answer = f"❌ Error: {response['error']}"
                sources = []
            else:
                answer = response.get("answer", "No response received")
                sources = response.get("sources", [])
            
            st.markdown(answer)
            
            # Show sources
            if sources:
                with st.expander(f"📚 Sources ({len(sources)})"):
                    for src in sources:
                        st.markdown(f"**[{src['index']}]** {src['source']} - {src['chunk_type']} (relevance: {src['relevance']})")
            
            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": sources
            })

# Quick actions
if not st.session_state.messages:
    st.markdown("### 💡 Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📋 Executive Summary", use_container_width=True):
            st.session_state.messages.append({
                "role": "user",
                "content": "Provide an executive summary of all uploaded documents"
            })
            st.rerun()
    
    with col2:
        if st.button("🔬 Analyze Formulas", use_container_width=True):
            st.session_state.messages.append({
                "role": "user",
                "content": "Explain the key formulas and calculations in the uploaded Excel files"
            })
            st.rerun()
    
    with col3:
        if st.button("📊 Document Overview", use_container_width=True):
            st.session_state.messages.append({
                "role": "user",
                "content": "List all documents and describe what each one contains"
            })
            st.rerun()
