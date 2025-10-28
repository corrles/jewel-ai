# Design Guidelines for Jewel (starter brief for Jane)

Thanks for taking this on, Jane — below is a compact brief that you can use as the starting point for a visual redesign and handoff.

Principles
- Calm, friendly, and trustworthy. Jewel should feel human but not anthropomorphic.
- Local-first and private: visual cues should reinforce privacy (subtle shields, offline indicators).
- Compact on mobile; spacious on desktop.

Color & Typography
- Primary: #667eea (purple) — used for primary actions and highlights.
- Secondary: #764ba2 — accents.
- Backgrounds: light neutral gradients for card surfaces.
- Type: system stack (system-ui, -apple-system, Roboto); large UI text at 14–16px, headings 18–22px.

Spacing & Components
- Cards: 12–18px padding, 12px border-radius, soft elevation shadow.
- Buttons: clear primary/secondary, pill-style for small actions, accessible >= 44px touch target on mobile.
- Inputs: light backgrounds, 8–10px padding, 6px border-radius.

Key areas to tackle first
1. Header & controls: simplify, add clear affordances for team controls and status.
2. Chat bubbles: improve contrast, micro-typography, and spacing for long messages.
3. Mobile responsiveness: stack controls and collapse less-used actions.
4. Style guide file: supply a single MD with color tokens, spacing scale, and component examples.

Deliverables
- A small style guide `DESIGN_GUIDELINES.md` (this file). Add a `style_demo.html` if helpful.
- A small CSS file `run/static/team_theme.css` (already present) for previewing.
- A short PR changing `run/static/chat_enhanced.html` to import the team theme and small HTML/CSS tweaks.

Hand-off suggestions
- Use `run/static/progress.html` to preview and share progress with Coco (and Jane).
- When ready, create a branch and submit a PR with visual changes; keep changes small and reversible.

If you want, I can:
- Create a small `style_demo.html` showing common components (buttons, inputs, chat bubbles) rendered in the new theme.
- Scaffold a `style_tokens.json` file for designers.

Tell me which of the above you'd like automated next (style demo, tokens, PR scaffolding), or I can start by creating a small style demo page for Jane to iterate on.
