# Deep AI Summary Design

## Goal

Make generated video summaries deeper, more interesting, and easier to scan:

- Replace plain, conservative summary wording with insight-oriented analysis.
- Keep summaries faithful to subtitles while adding interpretation, implications, limits, and practical takeaways.
- Use a small set of semantic icons and bold emphasis to mark important ideas.
- Preserve the existing backend JSON schema so current API consumers keep working.

## Context

The backend currently builds summaries in `backend/app/ai.py` with three prompt constants:

- `_FAST_SUMMARY_SYSTEM` creates the quick result shown while enrichment continues.
- `_DETAIL_SUMMARY_SYSTEM` enriches the quick result with key points, outline points, and mind map markdown.
- `_SUMMARY_SYSTEM` is the single-pass summary path.

The frontend already has a Markdown tab and custom prose styling in `frontend/src/components/AiSummary.jsx` and `frontend/src/index.css`. It can display emoji icons as text. The rich Markdown renderer supports inline `**bold**`, but the main readable summary view currently renders generated text as plain React text, so bold markers in the structured summary view need a small rendering helper.

## Chosen Design

Update the backend prompts without changing the response schema:

```json
{
  "overview": "...",
  "key_points": ["..."],
  "outline": [{"time": "12:34", "title": "...", "points": ["..."]}],
  "mindmap_markdown": "..."
}
```

The new prompt style will ask the model to act like a thoughtful video analyst and learning-note writer. Output should include:

- `overview`: a narrative, insight-oriented overview with the topic, central tension, core conclusion, and why the content matters.
- `key_points`: 6-10 substantive points. Each point should begin with one semantic marker such as `💡洞察`, `🎯重点`, `⚠️边界`, `✅建议`, or `🔍证据`, then include at least one bolded phrase.
- `outline.points`: section-level explanations that avoid bare keywords. Each point should explain what happened, why it matters, and how to use or interpret it when the subtitles support that.
- `mindmap_markdown`: concise but expressive branch names, using icons sparingly in headings.

The prompts will explicitly prohibit unsupported speculation. If the subtitles do not provide enough evidence, the model should phrase interpretation as "从字幕看..." or "可以理解为..." instead of inventing facts.

Update the frontend summary reading view to render a tiny safe subset of inline Markdown for generated text:

- Escape HTML first.
- Support `**bold**` as `<strong>`.
- Leave emoji as normal text.
- Reuse this helper for overview, outline titles, and outline points.

This keeps the interface simple while making generated emphasis visible in the main reading panel.

## Error Handling

If the model returns plain text without icons or bold, existing normalization still works. If outline points are missing, the current fallback builder will continue to create readable explanations. The fallback text should also be adjusted to match the deeper analytical tone.

## Testing

Backend tests should verify the prompt contract contains the new depth, icon, bold, and no-fabrication requirements.

Frontend verification should run the production build to catch JSX or rendering issues after adding the inline Markdown helper.

## Non-Goals

- Do not add new API fields in this pass.
- Do not introduce a full Markdown dependency.
- Do not redesign the summary panel layout.
