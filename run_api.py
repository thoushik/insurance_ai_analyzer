"""
Insurance Document Intelligence Assistant
FastAPI Server Runner

Run with: python run_api.py
"""

import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("  Insurance Document Intelligence Assistant")
    print("  RAG-Powered API Server")
    print("=" * 50)
    print()
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    port = int(os.getenv("API_PORT", 8000))
    
    print(f"  API Docs: http://localhost:{port}/docs")
    print(f"  Health:   http://localhost:{port}/")
    print()
    print("=" * 50)
    
    uvicorn.run(
        "app.api.fastapi_app:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
