import urllib.request
import json

def test_evaluate():
    print("Testing /api/eval/evaluate...")
    url = "http://localhost:5000/api/eval/evaluate"
    data = json.dumps({"question": "What is the loss ratio?"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(json.dumps(result, indent=2))
    except Exception as e:
        print("Error:", e)

def test_robustness():
    print("\nTesting /api/eval/robustness...")
    url = "http://localhost:5000/api/eval/robustness"
    data = json.dumps({"question": "What is the loss ratio?"}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(json.dumps(result, indent=2))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_evaluate()
    test_robustness()
