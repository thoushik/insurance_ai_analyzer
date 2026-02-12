
import requests
import json
import time
import sys

BASE_URL = "http://127.0.0.1:5000/api"

def test_api_citation_format():
    print(f"Testing API at {BASE_URL}...")
    
    # 1. Health Check
    try:
        resp = requests.get(f"{BASE_URL}/health")
        if resp.status_code != 200:
            print(f"[ERROR] API Health check failed: {resp.status_code}")
            return
        print("[OK] API is healthy")
    except Exception as e:
        print(f"[ERROR] Could not connect to API: {e}")
        print("Make sure the server is running (run_app.bat)!")
        return

    # 2. Test PDF Citation (General Query)
    print("\n[TEST] PDF Citation Format...")
    payload = {"message": "What are the key findings of the AI survey?"}
    try:
        start = time.time()
        resp = requests.post(f"{BASE_URL}/chat", json=payload)
        duration = time.time() - start
        
        if resp.status_code == 200:
            answer = resp.json().get("response", "")
            print(f"Response (first 200 chars): {answer[:200]}...")
            
            if "(Source:" in answer and ", Page" in answer:
                print("[SUCCESS] Found exact citation format: (Source: ..., Page ...)")
            elif "[Source" in answer:
                print("[FAILURE] Found old [Source N] format!")
            else:
                print("[WARNING] No citations found.")
        else:
            print(f"[ERROR] Request failed: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Request error: {e}")

    # 3. Test Excel Analysis (Formula Query)
    print("\n[TEST] Excel Analysis Format...")
    payload = {"message": "Analyze the formula in cell G26 of Hindsight IBNR"}
    try:
        start = time.time()
        resp = requests.post(f"{BASE_URL}/chat", json=payload)
        duration = time.time() - start
        
        if resp.status_code == 200:
            answer = resp.json().get("response", "")
            print(f"Response (first 200 chars): {answer[:200]}...")
            
            if "**Formula Breakdown:**" in answer:
                print("[SUCCESS] Found structured Excel analysis header.")
            else:
                print("[FAILURE] Missing '**Formula Breakdown:**' header.")
        else:
            print(f"[ERROR] Request failed: {resp.text}")
    except Exception as e:
        print(f"[ERROR] Request error: {e}")

if __name__ == "__main__":
    test_api_citation_format()
