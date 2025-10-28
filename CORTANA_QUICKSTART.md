# Jewel Cortana-Level Quickstart

Get started with wake-word activation, desktop reminders, and voice interaction in under 5 minutes.

## Prerequisites

- Windows 10/11 (for desktop notifications and PyAudio)
- Python 3.9+ with venv
- Microphone for wake-word detection
- OpenAI API key (for LLM chat)
- Picovoice Porcupine access key (free at https://console.picovoice.ai/)

## Quick Setup

1. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Configure environment**
   
   Create or update `.env` in the project root:
   ```env
   OPENAI_API_KEY=sk-...
   PORCUPINE_ACCESS_KEY=...  # Get free key from console.picovoice.ai
   ```

3. **Test wake-word detection**
   ```powershell
   python -m jewel.io.wake_word
   ```
   
   Say "Jarvis" (or your chosen wake word) to trigger detection.
   Press `Ctrl+C` to stop.

4. **Test desktop notifications**
   ```python
   from jewel.tools.desktop_notifier import notify
   notify("Test", "Desktop notification works!")
   ```

5. **Schedule a reminder**
   ```powershell
   # Start server
   uvicorn server.app:app --reload
   ```
   
   In another terminal or browser (POST to http://localhost:8000/schedule):
   ```python
   import requests
   from datetime import datetime, timedelta, timezone
   
   # Schedule reminder for 30 seconds from now
   run_at = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
   r = requests.post("http://localhost:8000/schedule", json={
       "run_at": run_at,
       "text": "Time to test your assistant!"
   })
   print(r.json())  # {"id": 1}
   ```
   
   You'll see a Windows toast notification when the reminder triggers.

## Full Voice Assistant Demo

Run the voice-enabled console app:

```powershell
python run/run_voice.py
```

- Say the wake word ("Jarvis")
- Speak your question
- Jewel will respond with synthesized speech

## Cortana-Level Features Implemented

✅ **Wake-word activation** - Say "Jarvis" to activate  
✅ **Proactive scheduler** - Schedule reminders with desktop notifications  
✅ **Voice I/O** - Speech-to-text (Vosk) + text-to-speech (Azure/OpenAI)  
✅ **Multimodal** - Image and video analysis endpoints  
✅ **Personalization** - Persona and emotion state tracking  
✅ **Safety** - Content filtering and local-first data  

## Next Steps

- **Calendar integration**: Add Google Calendar OAuth (see CORTANA_LEVEL_ROADMAP.md)
- **Custom wake word**: Train a custom `.ppn` file for "Hey Jewel"
- **Local fallback**: Add offline vision summarization when OpenAI quota is exhausted
- **Continuous improvement**: Review `SELF_MODIFICATION.md` for self-learning capabilities

## Troubleshooting

- **PyAudio install fails**: Download precompiled wheels from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
- **Wake word not detected**: Check microphone permissions and try increasing sensitivity in wake_word.py
- **No desktop notifications**: Install plyer: `pip install plyer`
- **OpenAI quota errors**: Video/vision endpoints will return partial results (transcript + heuristics)

## Architecture

```
┌─────────────────┐
│  Wake Word      │  (Porcupine)
│  Detection      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  STT (Vosk)     │  Convert speech to text
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Agent (LLM)    │  Process query + context
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TTS (Azure)    │  Synthesize response
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Speaker Output │
└─────────────────┘

         +
         
┌─────────────────┐
│  Scheduler      │  Background thread
│  (SQLite)       │  Polls for due tasks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Desktop        │  Windows toast
│  Notifier       │  notifications
└─────────────────┘
```

---

**You're ready to build a Cortana-level assistant!** 🎉

For advanced topics (self-modification, multi-modal learning, production deployment), see the full documentation in the repo root.
