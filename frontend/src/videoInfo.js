const TAG_TONES = ['blue', 'violet', 'emerald', 'amber', 'rose', 'cyan', 'slate']

export const TAG_TONE_CLASS = {
  blue: 'border-blue-100 bg-blue-50 text-blue-700',
  violet: 'border-violet/20 bg-violet/10 text-violet',
  emerald: 'border-emerald-100 bg-emerald-50 text-emerald-700',
  amber: 'border-amber-100 bg-amber-50 text-amber-700',
  rose: 'border-rose-100 bg-rose-50 text-rose-700',
  cyan: 'border-cyan-100 bg-cyan-50 text-cyan-700',
  slate: 'border-slate-200 bg-slate-50 text-slate-600',
}

export function formatDuration(sec) {
  if (!sec) return ''
  const total = Math.max(0, Math.floor(sec))
  const s = total % 60
  const m = Math.floor((total / 60) % 60)
  const h = Math.floor(total / 3600)
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

export function formatCount(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return ''
  if (n >= 100000000) return `${trimDecimal(n / 100000000)}亿`
  if (n >= 10000) return `${trimDecimal(n / 10000)}万`
  return String(Math.round(n))
}

function trimDecimal(value) {
  return value.toFixed(1).replace(/\.0$/, '')
}

function tag(text, toneIndex) {
  return { text, tone: TAG_TONES[toneIndex % TAG_TONES.length] }
}

export function buildVideoInfoTags(info = {}) {
  const tags = []
  if (info.extractor) tags.push(tag(`平台 ${info.extractor}`, tags.length))
  if (info.uploader) tags.push(tag(`作者 ${info.uploader}`, tags.length))
  const duration = info.duration_string || formatDuration(info.duration)
  if (duration) tags.push(tag(`时长 ${duration}`, tags.length))
  if (info.qualities?.length) tags.push(tag(`最高 ${info.qualities[0].label}`, tags.length))
  if (info.subtitles?.length) tags.push(tag(`字幕 ${info.subtitles.length} 种`, tags.length))
  const views = formatCount(info.view_count)
  if (views) tags.push(tag(`播放 ${views}`, tags.length))
  if (info.id) tags.push(tag(`ID ${info.id}`, tags.length))
  return tags
}

export function qualitySizeLabel(quality) {
  return quality?.filesize ? `约 ${quality.filesize}` : '大小未知'
}

export function qualityButtonMeta(preset, qualities = []) {
  if (preset.key === 'best') {
    const best = qualities[0]
    return {
      label: preset.label,
      detail: best?.label ? `最高 ${best.label} · ${qualitySizeLabel(best)}` : qualitySizeLabel(best),
    }
  }

  const matched = qualities.find((quality) => quality.height === preset.height)
  return {
    label: preset.label,
    detail: qualitySizeLabel(matched),
  }
}
