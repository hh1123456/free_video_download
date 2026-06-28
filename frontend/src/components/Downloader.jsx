import { useState } from 'react'
import { parseVideo } from '../api'
import { Icon } from './icons'
import AiSummary from './AiSummary'
import VideoResult from './VideoResult'

const EXAMPLES = ['YouTube', 'Bilibili', 'Twitter/X']

export default function Downloader() {
  const [mode, setMode] = useState('single')
  const [url, setUrl] = useState('')
  const [batchText, setBatchText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState([])

  const hasSingleResult = mode === 'single' && results.length === 1 && results[0].info
  const compact = hasSingleResult

  async function handleSingle() {
    const u = url.trim()
    if (!u) return setError('请输入视频链接')
    setError('')
    setLoading(true)
    try {
      const info = await parseVideo(u)
      setResults([{ url: u, info }])
    } catch (e) {
      setError(e.message)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  async function handleBatch() {
    const urls = [...new Set(batchText.split(/\s+/).map((s) => s.trim()).filter(Boolean))]
    if (urls.length === 0) return setError('请输入至少一个视频链接')
    setError('')
    setLoading(true)
    setResults([])
    const acc = []
    for (const u of urls) {
      try {
        const info = await parseVideo(u)
        acc.push({ url: u, info })
      } catch (e) {
        acc.push({ url: u, error: e.message })
      }
      setResults([...acc])
    }
    setLoading(false)
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
