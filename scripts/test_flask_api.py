import requests
import time
import sys

def test_health():
    url = "http://localhost:5000/api/health"
    print(f"Testing {url}...")
    
    for i in range(10):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("Health check passed!")
                print(response.json())
                return True
        except requests.exceptions.ConnectionError:
            print(f"Attempt {i+1}: Server not ready...")
            time.sleep(2)
            
    print("Health check failed after 10 attempts.")
    return False

if __name__ == "__main__":
    success = test_health()
    sys.exit(0 if success else 1)
