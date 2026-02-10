# AGENTS.md

Purpose: quick guide for agents working in this repo.

Project layout:
- desktop/
  - main.js (Electron main process)
  - preload.js (context bridge)
  - renderer/
    - index.html (console UI)
    - lawyer.html (lawyer UI)
    - styles.css (shared styles)
    - renderer.js (front-end logic)
- src/
  - fyp_vtrack.py (CLI entry point)
  - vtrack/ (FastAPI + merge/suggest/apply logic)
- tests/ (unit/integration tests)
- test_docs/ (sample contracts)
- scripts/ (local helper scripts)
- data/ (local data files)

Run basics:
- FastAPI: `VTRACK_DEVICE_MAP=auto VTRACK_MAX_NEW_TOKENS=128 python -m uvicorn vtrack.api:app`
- Desktop: `cd desktop` then `npm install` and `npm start`

Notes:
- Lawyer view: `npm run start:lawyer` or `electron . --view=lawyer`
- Default API base: `http://127.0.0.1:8000`
