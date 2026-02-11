import socket
import sys
import os
import requests
import platform

def check_port(port):
    print(f"Checking port {port}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('127.0.0.1', port))
        if result == 0:
            print(f"Port {port} is OPEN (Something is listening).")
            return True
        else:
            print(f"Port {port} is CLOSED (Nothing listening).")
            return False

def try_bind(port):
    print(f"Attempting to bind to port {port}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('0.0.0.0', port))
        print(f"Successfully bound to port {port}. Port is FREE.")
        s.close()
        return True
    except OSError as e:
        print(f"Failed to bind to port {port}: {e}")
        return False

def check_flask():
    print("\nChecking Flask installation...")
    try:
        import flask
        print(f"Flask version: {flask.__version__}")
        print(f"Flask path: {flask.__file__}")
    except ImportError as e:
        print(f"Flask NOT found: {e}")

def check_env():
    print("\nEnvironment Info:")
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.platform()}")
    print(f"CWD: {os.getcwd()}")

if __name__ == "__main__":
    print("=== DIAGNOSTIC START ===")
    check_env()
    check_flask()
    
    port_open = check_port(5000)
    
    if port_open:
        print("\nTrying to connect to localhost:5000...")
        try:
            r = requests.get('http://127.0.0.1:5000/api/health', timeout=5)
            print(f"Response: {r.status_code}")
            print(f"Content: {r.text[:100]}")
        except Exception as e:
            print(f"Connection failed: {e}")
            
    else:
        print("\nPort is closed. Checking if we can bind...")
        try_bind(5000)
        
    print("=== DIAGNOSTIC END ===")
