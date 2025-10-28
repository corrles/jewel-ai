# Jewel AI Prototype

This repository contains the Jewel AI multimodal assistant prototype.

## Setup

1. Activate the virtual environment:
	```powershell
	& .\.venv\Scripts\Activate.ps1
	```
2. Install dependencies:
	```powershell
	pip install -r requirements.txt
	```

## Running the Server

Start the FastAPI app locally:
```powershell
python -m uvicorn server.app:app --reload --port 8000
```

The server will be available at http://127.0.0.1:8000.

## Smoke Tests

With the server running (and venv activated), run:
```powershell
python .\run\smoke_test.py
```

Expected output:
```
Running smoke tests...
/health -> 200 {"ok": true}
/chat -> 200 {"reply": "<assistant reply>"}
```
