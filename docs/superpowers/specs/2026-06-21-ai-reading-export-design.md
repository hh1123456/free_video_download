# AI Reading And Export Improvements Design

## Goal

Improve the AI summary reading experience and export flow:

- Add a polished Markdown reading tab for the generated summary.
- Make the mind map easier to read with fullscreen mode and high-resolution PNG export.
- Let users download the transcript/subtitle as an SRT file after an AI summary task completes.

## Context

The current frontend does not use `marked.parse()`. `AiSummary.jsx` renders structured fields directly: overview, key points, outline, mind map, and chat. The backend stores transcript segments internally as `_segments` but intentionally hides them from the public summary polling response.

Because the frontend does not receive `segments`, subtitle download cannot be purely frontend-only in the current architecture. The stable design is to expose a small backend SRT download endpoint that reuses the completed AI task cache.

## Chosen Design

### Markdown Reading

Add a `Markdown` tab in `AiSummary.jsx`. It will build a full Markdown document from the existing structured summary and render it as safe HTML using a small local Markdown renderer. Styling will use a local `.summary-prose` class inspired by Tailwind Typography instead of adding a package, because this project currently uses Tailwind CDN and has no Tailwind build pipeline.

### Mind Map Fullscreen And PNG Export

Add controls above the mind map:

- `Fullscreen`: call `requestFullscreen()` on the mind map panel and call `markmap.fit()` after the browser enters fullscreen.
- `Exit fullscreen`: call `document.exitFullscreen()`.
- `Download PNG`: serialize the rendered SVG, draw it to a 2x canvas, and download a PNG Blob.

The feature stays frontend-only and does not add dependencies.

### SRT Download

Add backend helpers:

- `segments_to_srt(segments)` converts cached transcript segments into SRT text.
- `AISummaryManager.get_transcript_download(task_id)` returns title and SRT text for completed tasks.
- `GET /api/ai/transcript/{task_id}.srt` returns the SRT as an attachment.

Add a frontend `downloadTranscriptUrl(taskId)` helper and a `Download subtitles` button in the AI panel toolbar.

## Verification

- Backend unit tests cover SRT formatting and the new download helper.
- Existing backend tests must continue passing.
- Frontend production build must pass.
- Manual smoke path: complete an AI summary, switch to Markdown and Mind Map tabs, use fullscreen, download PNG, download SRT.
