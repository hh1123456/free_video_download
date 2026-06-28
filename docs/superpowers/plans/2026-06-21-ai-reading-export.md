# AI Reading Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add polished Markdown reading, mind map fullscreen/PNG export, and SRT transcript download to the AI summary panel.

**Architecture:** Keep the frontend mostly self-contained in `AiSummary.jsx` and `index.css`, with one backend endpoint for SRT because transcript segments are intentionally hidden from polling responses. Avoid new dependencies because the project uses Tailwind CDN rather than a Tailwind build pipeline.

**Tech Stack:** React 18, Vite, browser Fullscreen API, SVG-to-Canvas PNG export, FastAPI, Python unittest.

---

## Files

- Modify `backend/app/ai.py`: add SRT formatting helper and transcript download accessor.
- Modify `backend/app/main.py`: add `GET /api/ai/transcript/{task_id}.srt`.
- Modify `backend/tests/test_ai_summary.py`: add tests for SRT formatting and manager download data.
- Modify `frontend/src/api.js`: add transcript download URL helper.
- Modify `frontend/src/components/AiSummary.jsx`: add Markdown tab, transcript download button, mind map fullscreen, PNG export.
- Modify `frontend/src/components/icons.jsx`: add fullscreen/image icons if needed.
- Modify `frontend/src/index.css`: add `.summary-prose` Markdown styles and fullscreen mind map styles.

## Tasks

- [ ] Write failing backend tests for SRT conversion and completed-task transcript download.
- [ ] Implement minimal backend SRT helper, manager accessor, and FastAPI file endpoint.
- [ ] Run backend tests and confirm they pass.
- [ ] Add frontend API helper and UI controls.
- [ ] Add local Markdown renderer and prose styles.
- [ ] Add mind map fullscreen and PNG export handlers.
- [ ] Run frontend production build.
- [ ] Run full backend regression test command.
- [ ] Update project docs with the new user-facing behavior.
