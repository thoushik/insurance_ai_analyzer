# Insurance Document Intelligence Assistant

A secure, local-only Insurance Document Intelligence Assistant designed for actuarial, regulatory, and risk analysis of Excel and PDF files. Built with SR 11-7 compliance in mind.

## Features

- **🔒 Secure by Design**: All operations stay within the project folder
- **📊 Excel Analysis**: Extract formulas, understand sheet relationships, identify calculation types
- **📄 PDF Extraction**: Parse text, tables, and sections with page references
- **🤖 AI-Powered**: Uses Groq's fast LLM inference for intelligent document analysis
- **📋 SR 11-7 Compliant**: Audit logging, traceability, no hallucination
- **🎨 Modern UI**: Premium dark theme with glassmorphism design

## Quick Start

### 1. Create Virtual Environment

```bash
cd c:\Users\aksal\Documents\project\insurance_ai_analyzer
python -m venv venv
.\venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Key

The `.env` file is already configured with your Groq API key. If you need to change it:

```env
GROQ_API_KEY=your_api_key_here
LLM_MODEL=llama-3.3-70b-versatile
```

### 4. Run the Application

```bash
python -m app.main
```

Or use the run script:

```bash
python run.py
```

### 5. Open in Browser

Navigate to: **http://localhost:5000**

## Usage

1. **Upload Documents**: Drag & drop Excel (.xlsx) or PDF files onto the upload zone
2. **Automatic Ingestion**: Documents are parsed and indexed automatically
3. **Get Summary**: Click "Yes" to get an executive summary of all documents
4. **Deep Dive**: Ask about specific documents, sheets, or formulas
5. **Interactive Follow-up**: Use the numbered options to navigate through analysis levels

## Analysis Levels

| Level | Description |
|-------|-------------|
| **Executive Summary** | 2-paragraph overview of all documents |
| **Document Level** | Purpose and type of individual documents |
| **Sheet Level** | Input/calculation/output classification |
| **Formula Level** | Cell-by-cell formula explanation |
| **Calculation Type** | Automatic identification (IBNR, scenario testing, etc.) |

## Security Features

- ✅ Folder-safe: Never accesses files outside project folder
- ✅ Read-only mode for uploaded documents
- ✅ PII masking before LLM processing
- ✅ Comprehensive audit logging
- ✅ SR 11-7 compliance

## Project Structure

```
insurance_ai_analyzer/
├── app/
│   ├── security/      # Folder guard, PII masking, audit logging
│   ├── ingestion/     # Excel and PDF parsers
│   ├── llm/           # Groq client and prompts
│   ├── api/           # Flask routes
│   └── static/        # CSS and JavaScript
├── templates/         # HTML templates
├── data/uploads/      # Uploaded documents
├── logs/              # Audit logs
└── cache/             # Document cache
```

## License

Private - Internal use only
