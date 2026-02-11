"""
Insurance Document Intelligence Assistant
Run Script

Use this script to start the application.
"""

import os
import sys

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from app.main import app

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Insurance Document Intelligence Assistant")
    print("  SR 11-7 Compliant Document Analysis")
    print("=" * 60)
    print("\n  Starting server at: http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,  # Disable reloader to prevent mid-request restarts
        threaded=True # Handle multiple request threads
    )
