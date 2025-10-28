import requests
try:
    # Just call the basic endpoint
    r = requests.get("http://localhost:8000/")
    print(f"Root status: {r.status_code}")
except Exception as e:
    print(f"Root error: {e}")
