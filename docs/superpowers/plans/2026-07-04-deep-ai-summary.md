# Deep AI Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI video summaries deeper, more interesting, and visually scannable with semantic icons and bold emphasis.

**Architecture:** Keep the existing backend summary JSON schema and update prompt contracts in `backend/app/ai.py`. Add a small safe inline Markdown renderer in `frontend/src/components/AiSummary.jsx` so `**bold**` markers in structured fields render as emphasis in the main summary view.

**Tech Stack:** Python `unittest`, FastAPI backend helpers, React JSX, existing Vite frontend build.

---

### Task 1: Backend Prompt Contract

**Files:**
- Modify: `backend/tests/test_ai_summary.py`
- Modify: `backend/app/ai.py`

- [ ] **Step 1: Write the failing prompt-contract test**

Add a test class near the existing summary tests:

```python
class SummaryPromptContractTests(unittest.TestCase):
    def test_detail_prompt_requests_deep_interesting_emphasized_output(self) -> None:
        prompt = ai._DETAIL_SUMMARY_SYSTEM

        self.assertIn("深度", prompt)
        self.assertIn("有趣", prompt)
        self.assertIn("**", prompt)
        self.assertIn("💡洞察", prompt)
        self.assertIn("🎯重点", prompt)
        self.assertIn("⚠️边界", prompt)
        self.assertIn("不准编造", prompt)
        self.assertIn("从字幕看", prompt)

    def test_single_pass_prompt_matches_deep_summary_contract(self) -> None:
        prompt = ai._SUMMARY_SYSTEM

        self.assertIn("深度", prompt)
        self.assertIn("隐藏逻辑", prompt)
        self.assertIn("反直觉", prompt)
        self.assertIn("**", prompt)
        self.assertIn("mindmap_markdown", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\backend
.\.venv\Scripts\python.exe -m unittest tests.test_ai_summary.SummaryPromptContractTests
```

Expected: `FAIL` because the current prompts do not require the new depth, icons, and bold emphasis.

- [ ] **Step 3: Update prompt constants**

Modify `_SUMMARY_SYSTEM`, `_FAST_SUMMARY_SYSTEM`, and `_DETAIL_SUMMARY_SYSTEM` in `backend/app/ai.py` so the detail and single-pass prompts require:

```text
深度、有趣、洞察、隐藏逻辑、反直觉、适用边界、行动建议、**重点加粗**、💡洞察/🎯重点/⚠️边界/✅建议/🔍证据
```

Keep the JSON keys unchanged.

- [ ] **Step 4: Update fallback explanation tone**

Modify `_build_outline_explanation()` so generated fallback points sound like analytical notes, not generic filler. The fallback should mention section role, why it matters, and how to interpret/apply it.

- [ ] **Step 5: Run backend tests**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\backend
.\.venv\Scripts\python.exe -m unittest tests.test_ai_summary
```

Expected: all tests pass.

### Task 2: Frontend Inline Emphasis Rendering

**Files:**
- Create: `frontend/src/inlineMarkdown.js`
- Create: `frontend/src/inlineMarkdown.test.js`
- Modify: `frontend/src/components/AiSummary.jsx`
- Modify: `frontend/src/index.css` only if visual polish needs a small adjustment

- [ ] **Step 1: Write the failing inline Markdown helper test**

Create `frontend/src/inlineMarkdown.test.js` using Node's built-in test runner:

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { escapeHtml, inlineMarkdown } from './inlineMarkdown.js'

test('inlineMarkdown escapes html before rendering bold markers', () => {
  const html = inlineMarkdown('💡洞察：**重点** <script>alert(1)</script>')

  assert.equal(
    html,
    '💡洞察：<strong>重点</strong> &lt;script&gt;alert(1)&lt;/script&gt;'
  )
})

test('escapeHtml escapes quotes and angle brackets', () => {
  assert.equal(escapeHtml('"x" < y & z'), '&quot;x&quot; &lt; y &amp; z')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/inlineMarkdown.test.js
```

Expected: `ERR_MODULE_NOT_FOUND` because `src/inlineMarkdown.js` does not exist yet.

- [ ] **Step 3: Add safe inline rendering helper**

Create `frontend/src/inlineMarkdown.js`:

```js
export function escapeHtml(s) {
  return String(s || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]))
}

export function inlineMarkdown(s) {
  return escapeHtml(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}
```

Then import `escapeHtml` and `inlineMarkdown` in `AiSummary.jsx`, remove the local duplicate definitions, and add:

```jsx
function InlineRichText({ text }) {
  return <span dangerouslySetInnerHTML={{ __html: inlineMarkdown(text) }} />
}
```

This is safe because `inlineMarkdown()` calls `escapeHtml()` before replacing `**bold**`.

- [ ] **Step 4: Run helper test to verify it passes**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
node --test src/inlineMarkdown.test.js
```

Expected: all tests pass.

- [ ] **Step 5: Render generated summary fields through the helper**

Update `SummaryDigest`:

```jsx
<p><InlineRichText text={view.overview || `${title || '该视频'} 的概要内容正在生成中。`} /></p>
```

For titles and points:

```jsx
<strong><InlineRichText text={item.title} /></strong>
<li key={pointIndex}><InlineRichText text={point} /></li>
```

- [ ] **Step 6: Run frontend build**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\frontend
npm run build
```

Expected: build succeeds without JSX or lint errors.

### Task 3: Final Verification

**Files:**
- Review: `backend/app/ai.py`
- Review: `frontend/src/components/AiSummary.jsx`
- Review: `backend/tests/test_ai_summary.py`

- [ ] **Step 1: Run full relevant backend test set**

Run:

```powershell
cd F:\code\ai_project\free_viedo_dowload\backend
.\.venv\Scripts\python.exe -m unittest tests.test_downloader_errors tests.test_downloader_formats tests.test_ai_summary
```

Expected: all tests pass.

- [ ] **Step 2: Check git diff**

Run:

```powershell
git -C F:\code\ai_project\free_viedo_dowload diff -- backend/app/ai.py backend/tests/test_ai_summary.py frontend/src/components/AiSummary.jsx frontend/src/index.css
```

Expected: changes are limited to prompt contract, fallback wording, inline emphasis rendering, and any minimal CSS polish.
