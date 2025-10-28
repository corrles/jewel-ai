import requests
r = requests.get("http://localhost:8000/docs")
print(f"Docs status: {r.status_code}")
