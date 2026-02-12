"""
Insurance Document Intelligence Assistant
Main Flask Application
"""

import os
from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from .api import api
from .security import get_folder_guard


def create_app():
    """Create and configure the Flask application."""
    
    # Load environment variables
    load_dotenv()
    
    # Create Flask app
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="static"
    )
    
    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_SIZE_MB", 50)) * 1024 * 1024
    
    # Enable CORS
    CORS(app)
    
    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
    
    # Register blueprints
    app.register_blueprint(api, url_prefix="/api")
    
    # Main route
    @app.route("/")
    def index():
        return render_template("index.html")
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return {"error": "Not found"}, 404
    
    @app.errorhandler(500)
    def server_error(e):
        return {"error": "Internal server error"}, 500
    
    @app.errorhandler(413)
    def file_too_large(e):
        return {"error": "File too large"}, 413
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    print("\n\n" + "="*60)
    print("!!! LOADED FIXED VERSION - CITATION FORMATTING ENABLED !!!")
    
    # Auto-ingest existing files to ensure registry is in sync
    from .ingestion import get_document_registry
    from .security import get_folder_guard
    
    print("Syncing document registry with uploads folder...")
    try:
        registry = get_document_registry()
        guard = get_folder_guard()
        registry.ingest_folder(guard.upload_dir)
        print("Registry sync complete.")
    except Exception as e:
        print(f"ERROR during registry sync: {e}")
        print("Continuing application startup despite ingestion error...")
    
    print("="*60 + "\n\n")
    # Run on 0.0.0.0:5000 (Standard Flask Port, All Interfaces)
    # Disabled debug reloader to prevent mid-request restarts during heavy ML tasks
    app.run(
        host="0.0.0.0", 
        port=5000,
        debug=True,
        threaded=True
    )
