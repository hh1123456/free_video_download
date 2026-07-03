export const PARSE_PROGRESS_STEPS = [
  { key: 'validate', label: '校验链接', percent: 10 },
  { key: 'connect', label: '连接解析服务', percent: 25 },
  { key: 'fetch', label: '识别平台并获取视频信息', percent: 50 },
  { key: 'organize', label: '整理清晰度 / 字幕 / 封面', percent: 75 },
  { key: 'render', label: '生成结果卡片', percent: 95 },
]

function clampPercent(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(100, n))
}

export function getParseProgressStep(percent) {
  const safe = clampPercent(percent)
  let active = PARSE_PROGRESS_STEPS[0]
  for (const step of PARSE_PROGRESS_STEPS) {
    if (safe >= step.percent) active = step
  }
  return active
}

export function nextParseProgressPercent(percent) {
  const safe = clampPercent(percent)
  if (safe >= 92) return 92
  if (safe < 10) return 10
  if (safe < 25) return Math.min(25, safe + 3)
  if (safe < 50) return Math.min(50, safe + 4)
  if (safe < 75) return Math.min(75, safe + 3)
  return Math.min(92, safe + 1.5)
}
