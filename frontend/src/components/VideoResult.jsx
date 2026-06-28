import { useEffect, useRef, useState } from 'react'
import { startDownload, getProgress, fileUrl } from '../api'
import { Icon } from './icons'

const PRESETS = [
  { key: 'best', label: '最佳画质', height: 99999 },
  { key: '1080p', label: '1080P', height: 1080 },
  { key: '720p', label: '720P', height: 720 },
  { key: '480p', label: '480P', height: 480 },
  { key: '360p', label: '360P', height: 360 },
]

function fmtDuration(sec) {
  if (!sec) return null
  const s = Math.floor(sec % 60)
  const m = Math.floor((sec / 60) % 60)
  const h = Math.floor(sec / 3600)
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

export default function VideoResult({ info, url }) {
  const [quality, setQuality] = useState('best')
  const [audioOnly, setAudioOnly] = useState(false)
  const [subtitle, setSubtitle] = useState('')
  const [task, setTask] = useState(null)
  const pollRef = useRef(null)
  const triggeredRef = useRef(false)

  const maxHeight = info.qualities?.[0]?.height || 99999
  const presets = PRESETS.filter((p) => p.key === 'best' || p.height <= maxHeight)
  const busy = task && ['queued', 'downloading', 'processing'].includes(task.status)

  useEffect(() => () => clearInterval(pollRef.current), [])

  async function handleDownload() {
    triggeredRef.current = false
    setTask({ status: 'queued', percent: 0 })
    try {
      const { task_id } = await startDownload({
        url,
        quality,
        audioOnly,
        subtitleLang: subtitle || null,
      })
      clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const t = await getProgress(task_id)
          setTask({ ...t, taskId: task_id })
          if (t.status === 'completed') {
            clearInterval(pollRef.current)
            if (!triggeredRef.current) {
              triggeredRef.current = true
              const a = document.createElement('a')
              a.href = fileUrl(task_id)
              a.download = t.filename || ''
              document.body.appendChild(a)
              a.click()
              a.remove()
            }
          } else if (t.status === 'error') {
            clearInterval(pollRef.current)
          }
        } catch (e) {
          clearInterval(pollRef.current)
          setTask({ status: 'error', error: e.message })
        }
      }, 1000)
    } catch (e) {
      setTask({ status: 'error', error: e.message })
    }
  }

  return (
    <div className="overflow-hidden rounded-3xl bg-white shadow-card border border-slate-100">
      <div className="border-b border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-bold text-ink">
          <span className="grid place-items-center h-7 w-7 rounded-lg bg-brand-50 text-brand-600">
            <Icon.Download className="h-4 w-4" />
          </span>
          视频信息与下载
        </div>
      </div>

      <div className="p-4">
        <div className="relative aspect-video w-full overflow-hidden rounded-2xl bg-slate-100">
          {info.thumbnail ? (
            <img src={info.thumbnail} alt="" className="h-full w-full object-cover" referrerPolicy="no-referrer" />
          ) : (
            <div className="grid h-full w-full place-items-center text-slate-300">
              <Icon.Download className="h-10 w-10" />
            </div>
          )}
          {fmtDuration(info.duration) && (
            <span className="absolute bottom-2 right-2 rounded bg-black/70 px-2 py-1 text-xs font-semibold text-white">
              {fmtDuration(info.duration)}
            </span>
          )}
        </div>

        <h3 className="mt-4 line-clamp-3 text-left text-lg font-extrabold leading-snug text-ink">{info.title}</h3>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          {info.uploader && <span className="max-w-full truncate">作者 {info.uploader}</span>}
          {info.extractor && <span className="rounded-full bg-brand-50 px-2 py-0.5 font-semibold text-brand-600">{info.extractor}</span>}
          {info.qualities?.length > 0 && <span>最高 {info.qualities[0].label}</span>}
        </div>

        <div className="mt-5">
          <div className="mb-2 text-left text-xs font-semibold text-slate-400">选择清晰度</div>
          <div className="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
            {presets.map((p) => (
              <button
                key={p.key}
                disabled={audioOnly || busy}
                onClick={() => setQuality(p.key)}
                className={`rounded-xl border px-3 py-2 text-sm font-semibold transition disabled:opacity-40 ${
                  quality === p.key && !audioOnly
                    ? 'border-brand-500 bg-brand-500 text-white shadow-glow'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-brand-300'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            disabled={busy}
            onClick={() => setAudioOnly((v) => !v)}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm font-semibold transition ${
              audioOnly ? 'border-violet bg-violet text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-violet/50'
            }`}
          >
            <Icon.Music className="h-4 w-4" /> 仅音频 MP3
          </button>

          {info.subtitles?.length > 0 && (
            <div className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600">
              <Icon.Caption className="h-4 w-4 text-slate-400" />
              <select
                disabled={busy}
                value={subtitle}
                onChange={(e) => setSubtitle(e.target.value)}
                className="max-w-[160px] bg-transparent text-sm font-medium outline-none"
              >
                <option value="">不要字幕</option>
                {info.subtitles.map((s) => (
                  <option key={s} value={s}>字幕 {s}</option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="mt-5">
          {!busy && (!task || task.status === 'error') && (
            <button
              onClick={handleDownload}
              className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-brand-500 to-violet px-6 py-3 font-bold text-white shadow-glow transition hover:opacity-95 active:scale-[0.99]"
            >
              <Icon.Download className="h-5 w-5" /> 开始下载
            </button>
          )}

          {task?.status === 'error' && (
            <p className="mt-3 text-left text-sm text-red-500">下载失败：{task.error}</p>
          )}

          {busy && (
            <div>
              <div className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-500">
                <span className="flex items-center gap-1.5 text-brand-600">
                  <Icon.Spinner className="h-4 w-4 animate-spin" />
                  {task.status === 'processing' ? '正在合并/转码...' : task.status === 'queued' ? '排队中...' : '高速下载中'}
                </span>
                <span>{task.percent || 0}% {task.speed ? `· ${task.speed}/s` : ''}</span>
              </div>
              <div className="relative h-2.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  className="bar-shimmer relative h-full rounded-full bg-gradient-to-r from-brand-500 to-violet transition-all duration-300"
                  style={{ width: `${Math.max(task.percent || 0, 3)}%` }}
                />
              </div>
            </div>
          )}

          {task?.status === 'completed' && (
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-1.5 font-bold text-emerald-600">
                <span className="grid h-6 w-6 place-items-center rounded-full bg-emerald-100"><Icon.Check className="h-4 w-4" /></span>
                下载完成
              </span>
              <a
                href={fileUrl(task.taskId)}
                className="inline-flex items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                <Icon.Download className="h-4 w-4" /> 重新保存到本地
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
