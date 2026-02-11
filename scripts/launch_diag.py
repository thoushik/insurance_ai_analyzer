import sys
import traceback
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def start_app():
    print("=== INSURANCE AI DIAGNOSTIC LAUNCHER ===")
    print(f"CWD: {os.getcwd()}")
    print(f"Python: {sys.version}")

    try:
        print("\n[1] Importing Application...")
        from app.main import app
        print("Import successful.")

        print("\n[2] initializing Server on Port 5001...")
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        print(f"Local Access: http://127.0.0.1:5001")
        print(f"\n" + "="*50)
        print(f"LAN ACCESS URL: http://{local_ip}:5001")
        print(f"="*50 + "\n")
        print(f"Please use the LAN ACCESS URL above!")
        
        # Run without reloader to keep it simple and catch errors in this process
        app.run(host="0.0.0.0", port=5001, debug=True, use_reloader=False)

    except Exception:
        print("\n[CRITICAL ERROR] Application crashed during startup!")
        traceback.print_exc()
        
        # Write to file
        with open("crash_report.txt", "w") as f:
            f.write("=== CRASH REPORT ===\n")
            traceback.print_exc(file=f)
            
        print("\n>> crash_report.txt has been generated. <<")
        sys.exit(1)

if __name__ == "__main__":
    start_app()
