# Parse Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a centered frontend progress panel while video parsing is running and no parsed content is ready yet.

**Architecture:** Keep `/api/parse` synchronous. Add a small frontend progress helper that models staged parsing percentages, then render a progress panel in `Downloader.jsx` between the input area and the result area while parsing is active.

**Tech Stack:** React, existing Vite frontend, Node built-in test runner.

---

### Task 1: Parse Progress Helper

**Files:**
- Create: `frontend/src/parseProgress.js`
- Create: `frontend/src/parseProgress.test.js`

- [ ] **Step 1: Write failing helper tests**

Create `frontend/src/parseProgress.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  PARSE_PROGRESS_STEPS,
  getParseProgressStep,
  nextParseProgressPercent,
} from './parseProgress.js'

test('parse progress exposes the expected staged labels', () => {
  assert.deepEqual(PARSE_PROGRESS_STEPS.map((step) => step.label), [
    '校验链接',
    '连接解析服务',
    '识别平台并获取视频信息',
    '整理清晰度 / 字幕 / 封面',
    '生成结果卡片',
  ])
})

test('getParseProgressStep maps percent to the current stage', () => {
  assert.equal(getParseProgressStep(0).key, 'validate')
  assert.equal(getParseProgressStep(50).key, 'fetch')
  assert.equal(getParseProgressStep(80).key, 'organize')
  assert.equal(getParseProgressStep(100).key, 'render')
})

test('nextParseProgressPercent advances but caps while request is pending', () => {
  assert.equal(nextParseProgressPercent(0), 10)
  assert.ok(nextParseProgressPercent(50) > 50)
  assert.equal(nextParseProgressPercent(99), 92)
})
```

- [ ] **Step 2: Verify red**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/parseProgress.test.js
```

Expected: `ERR_MODULE_NOT_FOUND`.

- [ ] **Step 3: Implement helper**

Create `frontend/src/parseProgress.js` with the exported stage list, `getParseProgressStep(percent)`, and `nextParseProgressPercent(percent)`.

- [ ] **Step 4: Verify green**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/parseProgress.test.js
```

Expected: all tests pass.

### Task 2: Downloader Progress Panel

**Files:**
- Modify: `frontend/src/components/Downloader.jsx`

- [ ] **Step 1: Add parse progress state**

Use `useEffect` and `useState` to advance a `parseProgress` object while `loading` is true. Reset it when parsing finishes.

- [ ] **Step 2: Render centered progress panel**

Add `ParseProgressPanel` inside `Downloader.jsx`. It should render between the input area and result list, centered with a progress bar and the active stage labels.

- [ ] **Step 3: Support batch context**

Show batch metadata such as `2/5` and the current URL when batch parsing is active.

- [ ] **Step 4: Verify frontend**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/parseProgress.test.js
npm run build
```

Expected: tests and build pass.
