Smoke tests for local/staging Jewel

This folder contains a quick PowerShell smoke test you can run on Windows to validate a running local or staging server.

Run (from project root):

```powershell
# Ensure server is running
.
# Run the smoke test
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\deploy\smoke_tests\smoke_test.ps1
```

What it does
Smoke tests for local/staging Jewel

This folder contains a quick PowerShell smoke test you can run on Windows to validate a running local or staging server.

Run (from project root):

```powershell
# Ensure server is running
.
# Run the smoke test
powershell -NoProfile -ExecutionPolicy Bypass -File .\packaging\deploy\smoke_tests\smoke_test.ps1
```

What it does
- GET /health
- POST /video_summary with quick=true (cheap; max_frames=1)

Notes
- The smoke test intentionally uses a very small workload to avoid heavy OpenAI usage. If your OpenAI key is missing or out of quota, the server should still return partial results (transcript, visual_summary, fallback_summary).


Local reflections (developer privacy helper)
------------------------------------------
Jewel supports storing short "private reflections" locally on the machine (used by the agent for internal reasoning). Access to these reflections is gated by a local secret to prevent accidental exposure.

To enable and inspect reflections from the UI:

1. Set the `JEWEL_LOCAL_SECRET` environment variable when launching the server. On Windows PowerShell you can do this for the current process like:

```powershell
$env:JEWEL_LOCAL_SECRET = 'your-strong-local-secret'
& .\.venv\Scripts\Activate.ps1; python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

1. Open the chat UI in your browser (e.g. `http://127.0.0.1:8000/ui/chat_enhanced.html`).

1. Open Customize (⚙️) and paste the same secret into the "Local secret" field in the Persona section. Click "Show Reflections" to fetch them or "Reset Reflections" to delete them. The secret is stored only in your browser's `localStorage` for convenience — clear it if you prefer not to keep it there.

Security note: The reflections data is stored locally in the server's SQLite store and is intended for developer/local use only. Do not expose the machine or the local secret to untrusted networks.
