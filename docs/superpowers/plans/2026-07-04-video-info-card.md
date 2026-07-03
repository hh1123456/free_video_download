# Video Info Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the parsed video info card richer and show each downloadable quality's approximate size.

**Architecture:** Keep backend parsing unchanged because `parse_video()` already returns `qualities[].filesize`, duration, uploader, extractor, view count, subtitles, and ids. Add a focused frontend helper for tag/quality formatting, then update `VideoResult.jsx` to render richer colorful metadata and quality buttons with size text.

**Tech Stack:** React, Vite, Node built-in test runner.

---

### Task 1: Formatting Helper

**Files:**
- Create: `frontend/src/videoInfo.js`
- Create: `frontend/src/videoInfo.test.js`

- [ ] **Step 1: Write failing tests**

Create tests for `formatCount`, `qualitySizeLabel`, `qualityButtonMeta`, and `buildVideoInfoTags`.

- [ ] **Step 2: Verify red**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/videoInfo.test.js
```

Expected: module not found.

- [ ] **Step 3: Implement helper**

Create `videoInfo.js` with formatting functions and a small color palette for tags.

- [ ] **Step 4: Verify green**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/videoInfo.test.js
```

Expected: all tests pass.

### Task 2: VideoResult UI

**Files:**
- Modify: `frontend/src/components/VideoResult.jsx`

- [ ] **Step 1: Import helper and derive display data**

Use `buildVideoInfoTags(info)` and `qualityButtonMeta(p, info.qualities)`.

- [ ] **Step 2: Render richer metadata tags**

Replace the simple author/platform/highest line with a colorful tag grid.

- [ ] **Step 3: Show quality size on each button**

Render quality label and approximate size in each quality button. For unknown sizes, show `大小未知`.

- [ ] **Step 4: Verify frontend**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/videoInfo.test.js
npm run build
```

Expected: tests and build pass.
