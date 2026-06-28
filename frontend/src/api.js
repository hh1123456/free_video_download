// 与后端交互的薄封装。开发期通过 Vite 代理 /api -> 后端 8000。

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `请求失败 (${res.status})`)
  }
  return data
}

export function login({ username, password }) {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function getCurrentUser() {
  return request('/api/auth/me')
}

export function logout() {
  return request('/api/auth/logout', { method: 'POST' })
}

export function parseVideo(url) {
  return request('/api/parse', { method: 'POST', body: JSON.stringify({ url }) })
}

export function startDownload({ url, quality = 'best', audioOnly = false, subtitleLang = null }) {
  return request('/api/download', {
    method: 'POST',
    body: JSON.stringify({
      url,
      quality,
      audio_only: audioOnly,
      subtitle_lang: subtitleLang,
    }),
  })
}

export function getProgress(taskId) {
  return request(`/api/progress/${taskId}`)
}

export function fileUrl(taskId) {
  return `/api/file/${taskId}`
}

// ---- AI 视频总结 ----
export function startAiSummary(url) {
  return request('/api/ai/summary', { method: 'POST', body: JSON.stringify({ url }) })
}

export function getAiSummary(taskId) {
  return request(`/api/ai/summary/${taskId}`)
}

export function aiChat({ contentKey, question, history = [] }) {
  return request('/api/ai/chat', {
    method: 'POST',
    body: JSON.stringify({ content_key: contentKey, question, history }),
  })
}

export function aiTranslate({ contentKey, target }) {
  return request('/api/ai/translate', {
    method: 'POST',
    body: JSON.stringify({ content_key: contentKey, target }),
  })
}

export function transcriptDownloadUrl(taskId) {
  return `/api/ai/transcript/${taskId}.srt`
}
