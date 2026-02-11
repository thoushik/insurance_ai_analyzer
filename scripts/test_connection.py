import requests
import sys

def test_conn():
    url = "http://127.0.0.1:5000/"
    print(f"Connecting to {url}...")
    try:
        resp = requests.get(url, timeout=5)
        print(f"Status: {resp.status_code}")
        print(f"Headers: {resp.headers}")
        print("Content sample:", resp.text[:100])
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

if __name__ == "__main__":
    success = test_conn()
    sys.exit(0 if success else 1)
