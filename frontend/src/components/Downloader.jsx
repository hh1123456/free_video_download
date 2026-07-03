import { useEffect, useState } from 'react'
import { parseVideo } from '../api'
import { Icon } from './icons'
import AiSummary from './AiSummary'
import VideoResult from './VideoResult'
import { PARSE_PROGRESS_STEPS, getParseProgressStep, nextParseProgressPercent } from '../parseProgress'

const EXAMPLES = ['YouTube', 'Bilibili', 'Twitter/X']

export default function Downloader() {
  const [mode, setMode] = useState('single')
  const [url, setUrl] = useState('')
  const [batchText, setBatchText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState([])
  const [parseProgress, setParseProgress] = useState(null)

  const hasSingleResult = mode === 'single' && results.length === 1 && results[0].info
  const compact = hasSingleResult

  useEffect(() => {
    if (!loading || !parseProgress) return undefined
    const timer = setInterval(() => {
      setParseProgress((current) => (
        current ? { ...current, percent: nextParseProgressPercent(current.percent) } : current
      ))
    }, 450)
    return () => clearInterval(timer)
  }, [loading, parseProgress?.runId])

  async function handleSingle() {
    const u = url.trim()
    if (!u) return setError('请输入视频链接')
    setError('')
    setResults([])
    setParseProgress({
      runId: Date.now(),
      kind: 'single',
      percent: 10,
      currentUrl: u,
    })
    setLoading(true)
    try {
      const info = await parseVideo(u)
      setParseProgress((current) => current ? { ...current, percent: 100 } : current)
      setResults([{ url: u, info }])
    } catch (e) {
      setError(e.message)
      setResults([])
    } finally {
      setLoading(false)
      setParseProgress(null)
    }
  }

  async function handleBatch() {
    const urls = [...new Set(batchText.split(/\s+/).map((s) => s.trim()).filter(Boolean))]
    if (urls.length === 0) return setError('请输入至少一个视频链接')
    setError('')
    setLoading(true)
    setResults([])
    setParseProgress({
      runId: Date.now(),
      kind: 'batch',
      percent: 10,
      current: 1,
      total: urls.length,
      currentUrl: urls[0],
    })
    const acc = []
    for (const [index, u] of urls.entries()) {
      setParseProgress({
        runId: `${Date.now()}-${index}`,
        kind: 'batch',
        percent: 10,
        current: index + 1,
        total: urls.length,
        currentUrl: u,
      })
      try {
        const info = await parseVideo(u)
        setParseProgress((current) => current ? { ...current, percent: 100 } : current)
        acc.push({ url: u, info })
      } catch (e) {
        acc.push({ url: u, error: e.message })
      }
      setResults([...acc])
    }
    setLoading(false)
    setParseProgress(null)
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !loading) handleSingle()
  }

  function switchMode(nextMode) {
    setMode(nextMode)
    setError('')
    setResults([])
  }

  return (
    <div id="download" className={`w-full mx-auto ${compact ? 'max-w-[1760px]' : 'max-w-5xl'}`}>
      {!compact && (
        <div className="mb-5 flex justify-center gap-2 text-sm font-bold text-slate-400">
          <button
            onClick={() => switchMode('single')}
            className={mode === 'single' ? 'text-brand-500' : 'hover:text-slate-600'}
          >
            单个下载
          </button>
          <span>/</span>
          <button
            onClick={() => switchMode('batch')}
            className={mode === 'batch' ? 'text-brand-500' : 'hover:text-slate-600'}
          >
            批量下载
          </button>
        </div>
      )}

      <div className={compact ? 'rounded-[2rem] border border-white/70 bg-white/75 p-3 shadow-card backdrop-blur lg:p-4' : ''}>
        {mode === 'single' ? (
          <div
            className={`flex flex-col items-stretch overflow-hidden border border-slate-200 bg-white shadow-[0_12px_32px_-18px_rgba(15,23,42,0.42)] sm:flex-row ${
              compact ? 'rounded-2xl' : 'rounded-[2rem]'
            }`}
          >
            <div className="flex flex-1 items-center gap-4 px-7">
              <Icon.Link className="h-7 w-7 shrink-0 text-slate-400" />
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="https://www.youtube.com/watch?v=... 粘贴视频链接"
                className="w-full bg-transparent py-6 text-xl font-medium outline-none placeholder:text-slate-400"
              />
            </div>
            <button
              onClick={handleSingle}
              disabled={loading}
              className="inline-flex items-center justify-center gap-3 bg-brand-500 px-12 py-6 text-xl font-extrabold text-white transition hover:bg-brand-600 disabled:opacity-60 sm:min-w-[240px]"
            >
              {loading ? <Icon.Spinner className="h-7 w-7 animate-spin" /> : <span className="text-3xl leading-none">⌕</span>}
              {loading ? '解析中' : compact ? '重新解析' : '解析视频'}
            </button>
          </div>
        ) : (
          <div className="rounded-[2rem] border border-slate-200 bg-white p-4 shadow-[0_12px_32px_-18px_rgba(15,23,42,0.42)]">
            <textarea
              value={batchText}
              onChange={(e) => setBatchText(e.target.value)}
              rows={4}
              placeholder={'每行粘贴一个视频链接，支持多平台混合：\nhttps://youtube.com/watch?v=...\nhttps://www.bilibili.com/video/...'}
              className="w-full resize-y rounded-2xl bg-slate-50 p-4 text-base outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-brand-200"
            />
            <div className="mt-3 flex justify-end">
              <button
                onClick={handleBatch}
                disabled={loading}
                className="inline-flex items-center gap-2 rounded-full bg-brand-500 px-7 py-3 text-base font-extrabold text-white shadow-glow transition hover:bg-brand-600 disabled:opacity-60"
              >
                {loading ? <Icon.Spinner className="h-5 w-5 animate-spin" /> : <Icon.Layers className="h-5 w-5" />}
                {loading ? '批量解析中' : '批量解析'}
              </button>
            </div>
          </div>
        )}

        {error && <p className="mt-3 text-center text-sm text-red-500">解析失败：{error}</p>}
      </div>

      {loading && parseProgress && (
        <ParseProgressPanel progress={parseProgress} />
      )}

      {!compact && mode === 'single' && (
        <div className="mt-7 flex flex-wrap items-center justify-center gap-4 text-base text-slate-400">
          <span>试试：</span>
          {EXAMPLES.map((item) => (
            <span key={item} className="rounded-full border border-slate-200 bg-white px-7 py-2 font-semibold">
              {item}
            </span>
          ))}
        </div>
      )}

      {hasSingleResult && (
        <section className="video-workspace mt-5 grid gap-4 text-left lg:grid-cols-[minmax(240px,300px)_minmax(0,1fr)] xl:grid-cols-[minmax(260px,320px)_minmax(0,1fr)]">
          <aside className="lg:sticky lg:top-24 lg:self-start">
            <VideoResult info={results[0].info} url={results[0].url} />
          </aside>
          <div className="min-w-0">
            <AiSummary url={results[0].url} autoStart />
          </div>
        </section>
      )}

      {mode === 'batch' && results.length > 0 && (
        <div className="mt-6 grid gap-4 text-left lg:grid-cols-2">
          {results.map((r, i) =>
            r.info ? (
              <VideoResult key={r.url + i} info={r.info} url={r.url} />
            ) : (
              <div key={r.url + i} className="rounded-2xl border border-red-100 bg-red-50 p-4 text-sm">
                <p className="break-all font-semibold text-red-600">解析失败：{r.url}</p>
                <p className="mt-1 text-red-400">{r.error}</p>
              </div>
            )
          )}
        </div>
      )}
    </div>
  )
}

function ParseProgressPanel({ progress }) {
  const percent = Math.round(Math.max(0, Math.min(100, progress?.percent || 0)))
  const activeStep = getParseProgressStep(percent)
  const isBatch = progress?.kind === 'batch'

  return (
    <section className="mt-8 grid min-h-[280px] place-items-center rounded-[2rem] border border-brand-100 bg-white/90 px-5 py-8 text-center shadow-card">
      <div className="w-full max-w-2xl">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600">
          <Icon.Spinner className="h-6 w-6 animate-spin" />
        </div>
        <h3 className="mt-4 text-xl font-black text-ink">正在解析视频信息</h3>
        <p className="mt-2 text-sm font-semibold text-brand-600">{activeStep.label}</p>

        {isBatch && (
          <div className="mt-3 rounded-2xl bg-slate-50 px-4 py-3 text-left text-xs text-slate-500">
            <div className="font-bold text-slate-700">
              批量解析 {progress.current || 1}/{progress.total || 1}
            </div>
            <div className="mt-1 truncate" title={progress.currentUrl || ''}>
              {progress.currentUrl || '正在准备下一个链接'}
            </div>
          </div>
        )}

        {!isBatch && progress?.currentUrl && (
          <div className="mx-auto mt-3 max-w-xl truncate rounded-full bg-slate-50 px-4 py-2 text-xs font-medium text-slate-500" title={progress.currentUrl}>
            {progress.currentUrl}
          </div>
        )}

        <div className="mt-6">
          <div className="mb-2 flex items-center justify-between text-xs font-bold text-slate-500">
            <span>解析进度</span>
            <span>{percent}%</span>
          </div>
          <div className="relative h-3 overflow-hidden rounded-full bg-slate-100">
            <div
              className="bar-shimmer relative h-full rounded-full bg-gradient-to-r from-brand-500 to-violet transition-all duration-500"
              style={{ width: `${Math.max(percent, 6)}%` }}
            />
          </div>
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-5">
          {PARSE_PROGRESS_STEPS.map((step) => {
            const done = percent >= step.percent
            const active = activeStep.key === step.key
            return (
              <div
                key={step.key}
                className={`rounded-2xl border px-3 py-2 text-left text-xs transition ${
                  active
                    ? 'border-brand-200 bg-brand-50 text-brand-700'
                    : done
                      ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
                      : 'border-slate-100 bg-slate-50 text-slate-400'
                }`}
              >
                <div className="mb-1 flex items-center gap-1.5 font-black">
                  <span className={`h-2 w-2 rounded-full ${done ? 'bg-brand-500' : 'bg-slate-300'}`} />
                  {step.percent}%
                </div>
                <div className="leading-snug">{step.label}</div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
