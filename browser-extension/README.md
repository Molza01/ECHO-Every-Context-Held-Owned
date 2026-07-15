# ContextOS Browser Extension

Minimal Chromium (MV3) extension that makes the browser a first-class ContextOS memory source.

## What it does
- On navigation, sends **page title + URL + domain** to the local backend
  (`POST http://127.0.0.1:8765/api/ingest`, `source_type: "browser"`).
- **Explicit** "Remember this page" / "Remember this selection" context-menu actions.
- **Ambient side panel** that shows memories related to the current page, with confidence and
  "why this appeared" — the browser-side equivalent of the app's ambient panel.
- Popup with a live Supermemory status dot and an auto-capture on/off toggle.

## What it never does
No page-content scraping, no form/field reading, no keystroke capture, no silent selection
capture. Selected text is only sent through the explicit right-click action.

## Load it
Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → select this folder.

No build step — plain MV3 + vanilla JS so it loads directly.
