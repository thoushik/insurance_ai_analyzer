# Insurance Document Intelligence - RAG Architecture

This project has been upgraded to a Retrieval-Augmented Generation (RAG) architecture for grounded document analysis.

## Key Features

- **Vector Database**: ChromaDB (local semantic search)
- **Embeddings**: HuggingFace `all-MiniLM-L6-v2` (local inference)
- **LLM Integration**: Groq via LangChain
- **Frontend**: Streamlit (interactive chat & upload)
- **Backend**: FastAPI (RAG endpoints)
- **Security**: SR 11-7 compliant audit logging & PII masking

## Quick Start (Windows)

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application**:
   Double-click `run_app.bat`
   
   OR run manually in two terminals:
   
   **Terminal 1 (Backend):**
   ```bash
   python run_api.py
   ```
   
   **Terminal 2 (Frontend):**
   ```bash
   streamlit run streamlit_app.py
   ```

3. **Access the App**:
   Open browser at `http://localhost:8501`

## API Documentation

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Endpoints

- `POST /api/upload`: Upload Excel/PDF documents
- `POST /api/ingest-folder`: Batch ingest a folder
- `POST /api/chat`: RAG-powered chat
- `GET /api/documents`: List ingested files
- `DELETE /api/clear`: Clear vector store

## System Architecture

### 1. Ingestion Layer
- **Excel Parser**: Extracts cell formulas, values, and metadata.
- **PDF Parser**: Extracts text by page, tables, and sections.
- **Chunking**: Creates structured chunks optimized for insurance queries.

### 2. Retrieval Layer
- **Embeddings**: Text converted to vectors using `all-MiniLM-L6-v2`.
- **Vector Store**: ChromaDB index for similarity search.
- **Retriever**: `DocumentRetriever` fetches relevant chunks based on query.

### 3. Generation Layer
- **LangChain**: Orchestrates the RAG flow.
- **Groq LLM**: Generates answers based *only* on retrieved context.
- **PII Masking**: Redacts sensitive data before returning response.

## Troubleshooting

- **Import Errors**: Ensure all packages in `requirements.txt` are installed.
- **API Connection Error**: Ensure backend is running on port 8000.
- **Groq API Key**: Ensure `GROQ_API_KEY` is set in `.env`.
