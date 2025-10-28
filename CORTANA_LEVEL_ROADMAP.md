CORTANA-LEVEL ROADMAP for Jewel
================================

Goal
----

Bring `Jewel` from a chat-first assistant to a "Cortana-level" personal assistant: proactive, multimodal, deeply integrated with a user's calendar/OS/services, reliable offline fallbacks, always-safe, and highly personalized while preserving privacy and user control.

Success criteria (measurable)
----------------------------

- Responsive voice interaction (wake word → query → answer) with median end-to-end latency < 1s for local actions and < 3s for remote queries (when network available).
- Proactive notifications: schedule and deliver reminders, proactively surface relevant info (e.g., travel delays) with >85% accuracy in relevance judged by a small user panel.
- Multimodal understanding: analyze an image or video clip and produce a concise summary with visual highlights (frames, timestamped captions) for 80% of test clips.
- Robust offline fallback: when cloud LLMs are unavailable, return useful, locally-derived summaries and actions (local NLU + heuristics) instead of failing.
- Safety: maintain content filters, opt-in controls, and an explainable audit trail for any action that affects external systems.

Phased plan (incremental, testable)
----------------------------------

MVP (replaceable within weeks)

- Stable chat + video pipeline (done).
- Local fallback summaries for video and vision (done/in-progress).
- Quick-mode for low-cost testing (done).

Phase 1 — Reliable Assistant Core (1–2 months)

- Voice I/O: integrate a low-latency STT engine (Vosk/whisper local) + TTS with caching.
- Wake-word / push-to-talk UX on desktop and web.
- Identity & personalization: local profile, preferences, persona tuning.
- Acceptance tests + smoke suite (health, quick video summary) — automated.

Phase 2 — Service Integrations & Proactivity (2–3 months)

- Calendar, email, contacts integrations (OAuth flows), with read-only by default and explicit action flows for writes.
- Proactive scheduler: rules engine + short-term notification queue + retry/backoff.
- Short-term memory: local recent context for continuity across sessions.

Phase 3 — Multimodal & Offline Resilience (3–6 months)

- Local vision models for thumbnails/objects (tiny CNNs) so some visual analysis works offline.
- Progressive summarization: short bullets → expanded section on demand; store metadata for fast retrieval.
- Background workers for heavy tasks (ffmpeg/yt-dlp offloaded to queue + status endpoints).

Phase 4 — Platform polish & scaling

- Production deployment patterns (k8s/Cloud Run), logging/metrics, and cost controls.
- Security audit, privacy policy, opt-in telemetry, and tools for data export/deletion.

Technical building blocks
------------------------

- Local components: Vosk/Whisper (STT), Azure/OpenAI TTS, SQLite for memory, background worker (RQ or Celery-lite), ffmpeg, yt-dlp.
- Cloud components (optional): OpenAI LLMs for high-quality summaries, OAuth providers for calendar/email, object storage for thumbnails.
- Orchestration: FastAPI endpoints + uvicorn, nginx reverse proxy, systemd service for production.

Safety, privacy and data governance
----------------------------------

- Default to local-first: sensitive data stored locally unless user opts into cloud sync.
- Provide an audit log (what commands were run, what external actions were taken) accessible to the user.
- Implement rate-limiting and explicit user confirmation for any action that sends money, emails, or posts publicly.

Testing & metrics
-----------------

- Functional tests: /health, /chat, /vision, /video_summary (quick-mode: max_frames=1).
- Integration tests: OAuth calendar read/write dry-runs in a staging environment.
- Performance metrics: P95 latency, average LLM tokens/call, error rates, OpenAI 429 events.

Edge cases & operational concerns
--------------------------------

- OpenAI quota failures: surface fallback + clear messaging and local degrade modes.
- Long-running processing (video): return async job id + polling endpoint; UI shows progress and partial results.
- Windows-specific file locks: use in-memory buffers (BytesIO) and ensure temp dirs use unique names.

Top-priority next steps (concrete, 1–2 week sprint)
--------------------------------------------------

1. Add automated smoke tests and continuous checks (packaging/deploy/smoke_tests added).
2. Implement a simple scheduler/proactive notifier (local SQLite queue + background job that can raise desktop notifications or send TTS reminders via the server).
3. Add OAuth calendar read-only integration and a sample action: "What am I doing tomorrow?" that pulls next-day events and summarizes them.

Deliverables I will start implementing (with your permission)
-----------------------------------------------------------

- Add the scheduler + simple notifier module and endpoints (/schedule, /tasks, /notify).  
- Add the calendar integration scaffold (OAuth config, token store, read-only fetch).  
- Wire basic CI smoke tests and a nightly local runner that checkpoints the health and quota metrics.

If you want me to proceed with the work above, say which two items to prioritize first: (A) scheduler + notifier, (B) calendar integration, (C) CI/smoke test automation, (D) local wake-word + TTS polishing.

Notes
-----

This roadmap aims to be practical and iterative. Building a full Cortana-level assistant is a project of months and requires policy decisions (privacy, integrations, billing). I'll keep changes minimal and reversible and prioritize safety and local-first behavior.
