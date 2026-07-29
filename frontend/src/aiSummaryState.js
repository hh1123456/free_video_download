const DEFAULT_TTL_MS = 2 * 60 * 60 * 1000
const RUNNING_STATUSES = new Set(['queued', 'fetching', 'summarizing', 'enriching'])

function cacheKey(url) {
  return String(url || '').trim()
}

export function createAiSummaryCache({ now = () => Date.now(), ttlMs = DEFAULT_TTL_MS } = {}) {
  const entries = new Map()
  let nowFn = now

  return {
    setNow(nextNow) {
      nowFn = nextNow
    },
    save(url, snapshot) {
      const key = cacheKey(url)
      if (!key || !snapshot?.task) return
      entries.set(key, { ...snapshot, savedAt: nowFn() })
    },
    restore(url) {
      const key = cacheKey(url)
      const entry = entries.get(key)
      if (!entry) return null
      if (nowFn() - entry.savedAt > ttlMs) {
        entries.delete(key)
        return null
      }
      const { savedAt, ...snapshot } = entry
      return snapshot
    },
    remove(url) {
      entries.delete(cacheKey(url))
    },
  }
}

export function shouldResumeSummaryTask(task) {
  return Boolean(task?.id && RUNNING_STATUSES.has(task.status))
}

export function shouldAnimateSummaryView({ task, tab }) {
  return tab === 'markdown' && task?.status === 'enriching'
}

export const aiSummaryCache = createAiSummaryCache()
