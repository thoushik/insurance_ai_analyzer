import requests
import json
import time

print("Sending POST request to http://localhost:5000/api/eval/evaluate")
print("Waiting for response (this may take 10-20 seconds for RAGAS)...")

start = time.time()
try:
    response = requests.post(
        "http://localhost:5000/api/eval/evaluate",
        json={"question": "What is the loss ratio?"},
        timeout=60  # generous 60s timeout
    )
    elapsed = time.time() - start
    print(f"\nTime: {elapsed:.2f}s")
    print(f"Status Code: {response.status_code}")
    
    try:
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print("Response was not JSON:")
        print(response.text)
        
except Exception as e:
    elapsed = time.time() - start
    print(f"\nCRASH after {elapsed:.2f}s: {e}")
