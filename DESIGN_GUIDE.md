Jewel — Design Handoff & Guide for Jane
======================================

Thanks for helping with the UI redesign! This document gives a quick onboarding, prioritized tasks you can pick up, and where the code lives.

Quick setup
-----------

1. Create and activate a Python virtual environment and install requirements:

   - On PowerShell:
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     pip install -r requirements.txt

2. Start the dev server from the repository root:

   python -m uvicorn server.app:app --reload

Where to edit
-------------

- UI files are under `run/static/` — the main chat page is `chat_enhanced.html`.
- Styles are inline in the HTML for now; you can extract them into a new `run/static/css/` stylesheet.
- Generated assets and outputs are served from `/data` (folder: `data/`).

Design goals & constraints
-------------------------

- Keep the interface simple and friendly. Primary actions: send text, voice, image, generate, video.
- Maintain accessibility: clear contrast, keyboard-friendly, proper button sizes.
- Work within the existing FastAPI static mount: files under `run/static` are served at `/ui/`.

Suggested small tasks (pick 1–3 to start)
---------------------------------------

1. Theme polish (quick win)
   - Extract inline CSS into `run/static/css/theme.css`.
   - Implement 3 theme presets (purple/default, ocean, dark) and add a live preview selector.

2. Header redesign
   - Simplify header (move secondary controls into dropdown), increase contrast, and add responsive layout.
   - Replace text buttons with icon + label and hover tooltips.

3. Message card cleanup
   - Improve spacing, add subtle avatars (Jewel/You), and update font stack.
   - Ensure message bubbles wrap properly and are readable on mobile.

4. Create small assets
   - Add a small SVG logo `run/static/logo.svg` and favicon.

5. Accessibility pass
   - Audit for color contrast (WCAG AA), keyboard navigation, and ARIA attributes.

How to preview changes
----------------------

1. Edit `run/static/chat_enhanced.html` or add new CSS under `run/static/css/`.
2. Restart the dev server (or rely on `--reload`).
3. Open `http://127.0.0.1:8000/ui/chat_enhanced.html` and `http://127.0.0.1:8000/ui/progress.html`.

Reporting progress back
-----------------------

- Use the `progress.html` page (linked from the header) to see quick status and steps for Jane.
- When you complete a task, create a small Git branch and open a PR or leave a note in this repo (commit message + short description).

Contact & context
-----------------

If you need design assets or to discuss UX tradeoffs, leave a note in the codebase or message the team. The priority list is:
1) Theme polish
2) Header redesign
3) Message card cleanup

Thanks — feel free to start with any item above and I will wire up the server or add endpoints to support what you need.
