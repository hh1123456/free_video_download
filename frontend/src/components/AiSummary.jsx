import { useEffect, useRef, useState } from 'react'
import { startAiSummary, getAiSummary, aiChat, aiTranslate, transcriptDownloadUrl } from '../api'
import { Icon } from './icons'
import { escapeHtml, inlineMarkdown } from '../inlineMarkdown'
import { summaryAnimationKey } from '../summaryAnimation'

const TABS = [
  { key: 'markdown', label: '总结摘要', icon: '📝' },
  { key: 'outline', label: '字幕文本', icon: '📄' },
  { key: 'mindmap', label: '思维导图', icon: '🧠' },
  { key: 'chat', label: 'AI 问答', icon: '💬' },
]

const LANGS = [
  { code: '', label: '原文' },
  { code: 'en', label: 'English' },
  { code: 'ja', label: '日本語' },
  { code: 'ko', label: '한국어' },
  { code: 'fr', label: 'Francais' },
  { code: 'es', label: 'Espanol' },
]

function jumpUrl(webUrl, seconds) {
  if (!webUrl || !seconds) return webUrl
  try {
    const u = new URL(webUrl)
    u.searchParams.set('t', u.hostname.includes('youtube') || u.hostname.includes('youtu.be') ? `${seconds}s` : String(seconds))
    return u.toString()
  } catch {
    return webUrl
  }
}

function safeFileName(name, fallback = 'video-summary') {
  return String(name || fallback).replace(/[\\/:*?"<>|]+/g, '_').trim().slice(0, 80) || fallback
}

export default function AiSummary({ url, autoStart = false }) {
  const [open, setOpen] = useState(false)
  const [task, setTask] = useState(null)
  const [tab, setTab] = useState('markdown')
  const [lang, setLang] = useState('')
  const [translating, setTranslating] = useState(false)
  const [view, setView] = useState(null)
  const [origin, setOrigin] = useState(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [typedView, setTypedView] = useState(null)

  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [chatting, setChatting] = useState(false)

  const pollRef = useRef(null)
  const mapPanelRef = useRef(null)
  const mapRef = useRef(null)
  const mmRef = useRef(null)
  const animatedTaskRef = useRef('')

  useEffect(() => () => clearInterval(pollRef.current), [])

  useEffect(() => {
    if (!autoStart || open || task) return
    handleStart()
  }, [autoStart, open, task])

  useEffect(() => {
    const onFullscreenChange = () => {
      const active = document.fullscreenElement === mapPanelRef.current
      setIsFullscreen(active)
      setTimeout(() => mmRef.current?.fit?.(), 180)
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange)
  }, [])

  const loading = task && ['queued', 'fetching', 'summarizing'].includes(task.status)
  const enriching = task?.status === 'enriching'
  const markdown = view ? buildMarkdown(view, task?.title) : ''
  const currentSummaryAnimationKey = view ? summaryAnimationKey({ task, view, url }) : ''

  async function handleStart() {
    setOpen(true)
    if (task?.status === 'completed' || loading) return
    setTask({ status: 'queued', stage: '排队中...' })
    try {
      const { task_id } = await startAiSummary(url)
      animatedTaskRef.current = ''
      clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const t = await getAiSummary(task_id)
          setTask(t)
          if (t.status === 'enriching' && t.result) {
            setOrigin(t.result)
            setView(t.result)
          } else if (t.status === 'completed') {
            clearInterval(pollRef.current)
            setOrigin(t.result)
            setView(t.result)
          } else if (t.status === 'error') {
            clearInterval(pollRef.current)
          }
        } catch (e) {
          clearInterval(pollRef.current)
          setTask({ status: 'error', error: e.message })
        }
      }, 500)
    } catch (e) {
      setTask({ status: 'error', error: e.message })
    }
  }

  useEffect(() => {
    if (tab !== 'mindmap' || !view?.mindmap_markdown || !mapRef.current) return
    const mk = window.markmap
    if (!mk?.Transformer || !mk?.Markmap) return
    try {
      const height = isFullscreen ? 'calc(100vh - 110px)' : '560px'
      mapRef.current.innerHTML = `<svg style="width:100%;height:${height}"></svg>`
      const svg = mapRef.current.querySelector('svg')
      const transformer = new mk.Transformer()
      const { root } = transformer.transform(view.mindmap_markdown)
      mmRef.current = mk.Markmap.create(svg, { autoFit: true, duration: 300 }, root)
      setTimeout(() => mmRef.current?.fit?.(), 120)
    } catch {
      // Fallback text is rendered below when markmap cannot draw.
    }
  }, [tab, view, isFullscreen])

  useEffect(() => {
    if (!view) {
      setTypedView(null)
      return
    }
    if (tab !== 'markdown') {
      setTypedView(view)
      return
    }

    const outline = normalizeReadableOutline(view)
    const animationKey = currentSummaryAnimationKey
    if (animatedTaskRef.current === animationKey) {
      setTypedView(view)
      return
    }

    const nextView = {
      ...view,
      overview: '',
      outline: outline.map((item) => ({ ...item, points: [] })),
    }
    setTypedView(nextView)

    const units = [
      ...String(view.overview || '').split('').map((char) => ({ type: 'overview', char })),
      ...outline.flatMap((item, outlineIndex) => [
        { type: 'outline-title', outlineIndex, title: item.title },
        ...item.points.flatMap((point, pointIndex) => [
          { type: 'point-start', outlineIndex, pointIndex },
          ...String(point || '').split('').map((char) => ({ type: 'point-char', outlineIndex, pointIndex, char })),
        ]),
      ]),
    ]
    let cursor = 0
    const timer = setInterval(() => {
      cursor += 2
      const slice = units.slice(0, cursor)
      const overview = slice.filter((u) => u.type === 'overview').map((u) => u.char).join('')
      const nextOutline = outline
        .map((item, outlineIndex) => {
          const titleVisible = slice.some((u) => u.type === 'outline-title' && u.outlineIndex === outlineIndex)
          const points = item.points
            .map((_, pointIndex) =>
              slice
                .filter((u) => u.type === 'point-char' && u.outlineIndex === outlineIndex && u.pointIndex === pointIndex)
                .map((u) => u.char)
                .join('')
            )
            .filter(Boolean)
          return titleVisible ? { ...item, points } : null
        })
        .filter(Boolean)
      setTypedView({ ...view, overview, outline: nextOutline })
      if (cursor >= units.length) {
        clearInterval(timer)
        animatedTaskRef.current = animationKey
        setTypedView(view)
      }
    }, 45)
    return () => clearInterval(timer)
  }, [currentSummaryAnimationKey, tab])

  async function handleTranslate(code) {
    setLang(code)
    if (!code) {
      setView(origin)
      return
    }
    if (!task?.id) return
    setTranslating(true)
    try {
      const { result } = await aiTranslate({ contentKey: task.id, target: code })
      setView(result)
    } catch (e) {
      setView(origin)
      setLang('')
      alert(e.message)
    } finally {
      setTranslating(false)
    }
  }

  async function handleAsk() {
    const q = question.trim()
    if (!q || chatting || !task?.id) return
    setQuestion('')
    const next = [...messages, { role: 'user', content: q }]
    setMessages(next)
    setChatting(true)
    try {
      const { answer } = await aiChat({ contentKey: task.id, question: q, history: messages })
      setMessages([...next, { role: 'assistant', content: answer }])
    } catch (e) {
      setMessages([...next, { role: 'assistant', content: `(鍑洪敊浜嗭細${e.message})` }])
    } finally {
      setChatting(false)
    }
  }

  function exportMarkdown() {
    if (!view) return
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    downloadBlob(blob, `${safeFileName(task?.title)}.md`)
  }

  async function downloadTranscript() {
    if (!task?.id) return
    if (task.segments?.length) {
      const blob = new Blob([segmentsToSrt(task.segments)], { type: 'text/plain;charset=utf-8' })
      downloadBlob(blob, `${safeFileName(task?.title, 'video-transcript')}.srt`)
      return
    }
    try {
      const res = await fetch(transcriptDownloadUrl(task.id))
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        const detail = data.detail || `字幕下载失败 (${res.status})`
        throw new Error(`${detail}。如果刚刚重启过后端，请重新生成一次 AI 总结。`)
      }
      const blob = await res.blob()
      downloadBlob(blob, `${safeFileName(task?.title, 'video-transcript')}.srt`)
    } catch (e) {
      alert(e.message || '字幕下载失败，请确认总结任务尚未过期')
    }
  }

  async function toggleFullscreen() {
    const el = mapPanelRef.current
    if (!el) return
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else if (el.requestFullscreen) {
      await el.requestFullscreen()
    }
    setTimeout(() => mmRef.current?.fit?.(), 180)
  }

  function getMindmapSvgBlob() {
    const svg = mapRef.current?.querySelector('svg')
    if (!svg) return null
    const cloned = svg.cloneNode(true)
    const box = svg.getBoundingClientRect()
    const width = Math.max(1200, Math.ceil(box.width || 1200))
    const height = Math.max(800, Math.ceil(box.height || 800))
    cloned.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    cloned.setAttribute('width', String(width))
    cloned.setAttribute('height', String(height))
    cloned.setAttribute('viewBox', svg.getAttribute('viewBox') || `0 0 ${width} ${height}`)
    const svgText = new XMLSerializer().serializeToString(cloned)
    return { blob: new Blob([svgText], { type: 'image/svg+xml;charset=utf-8' }), width, height }
  }

  function downloadMindmapSvg() {
    const svgData = getMindmapSvgBlob()
    if (!svgData) return
    downloadBlob(svgData.blob, `${safeFileName(task?.title, 'mindmap')}-mindmap.svg`)
  }

  async function downloadMindmapPng() {
    const svgData = getMindmapSvgBlob()
    if (!svgData) return
    try {
      const { blob, width, height } = svgData
      const url = URL.createObjectURL(blob)
      const img = new Image()
      img.decoding = 'async'
      img.onload = () => {
        const scale = 2
        const canvas = document.createElement('canvas')
        canvas.width = width * scale
        canvas.height = height * scale
        const ctx = canvas.getContext('2d')
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.setTransform(scale, 0, 0, scale, 0, 0)
        ctx.drawImage(img, 0, 0, width, height)
        canvas.toBlob((blob) => {
          if (blob) downloadBlob(blob, `${safeFileName(task?.title, 'mindmap')}-mindmap.png`)
          setTimeout(() => URL.revokeObjectURL(url), 1000)
        }, 'image/png')
      }
      img.onerror = () => {
        URL.revokeObjectURL(url)
        alert('导出图片失败，请稍后重试')
      }
      img.src = url
    } catch (e) {
      alert(`导出图片失败：${e.message}`)
    }
  }

  function printPdf() {
    if (!view) return
    const w = window.open('', '_blank')
    if (!w) return
    w.document.write(printableHtml(view, task?.title))
    w.document.close()
    w.focus()
    setTimeout(() => w.print(), 300)
  }

  if (!open) {
    return (
      <button
        onClick={handleStart}
        className="inline-flex items-center gap-2 rounded-full border border-violet/30 bg-violet/5 text-violet font-bold px-5 py-2.5 hover:bg-violet/10 transition"
      >
        <Icon.Sparkle className="w-5 h-5" /> AI 总结这个视频
      </button>
    )
  }

  return (
    <div className="h-full overflow-hidden rounded-[1.75rem] border border-violet/20 bg-gradient-to-br from-violet/[0.04] to-brand-50/40 shadow-card">
      <div className="flex flex-col gap-3 border-b border-violet/10 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 font-bold text-ink">
          <span className="grid place-items-center w-7 h-7 rounded-lg bg-gradient-to-br from-violet to-brand-500 text-white">
            <Icon.Sparkle className="w-4 h-4" />
          </span>
          AI 视频总结
        </div>
        {(task?.status === 'completed' || enriching) && (
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-slate-200 bg-white text-xs text-slate-600">
              <Icon.Globe className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={lang}
                disabled={translating}
                onChange={(e) => handleTranslate(e.target.value)}
                className="bg-transparent outline-none font-medium"
              >
                {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
            </div>
            <button onClick={downloadTranscript} className="ai-tool-btn">
              <Icon.Caption className="w-3.5 h-3.5" /> 字幕
            </button>
            <button onClick={exportMarkdown} className="ai-tool-btn">
              <Icon.Doc className="w-3.5 h-3.5" /> MD
            </button>
            <button onClick={printPdf} className="ai-tool-btn">
              <Icon.Print className="w-3.5 h-3.5" /> PDF
            </button>
          </div>
        )}
      </div>

      {loading && (
        <div className="px-4 py-8 flex flex-col items-center gap-2 text-slate-500">
          <Icon.Spinner className="w-7 h-7 animate-spin text-violet" />
          <p className="font-semibold text-violet">{task.stage || '处理中...'}</p>
          <p className="text-xs text-slate-400">长视频字幕较多，可能需要十几秒，请稍等</p>
          {task.partial && (
            <StreamingDigest partial={task.partial} />
          )}
        </div>
      )}

      {task?.status === 'error' && (
        <div className="px-4 py-6 text-center">
          <p className="text-sm text-red-500">{task.error}</p>
          <button onClick={() => { setTask(null); handleStart() }} className="mt-3 text-sm font-semibold text-violet hover:underline">重试</button>
        </div>
      )}

      {(task?.status === 'completed' || enriching) && view && (
        <div>
          <div className="summary-tabs flex items-center gap-4 overflow-x-auto border-b border-slate-100 bg-white px-6">
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`summary-tab inline-flex shrink-0 items-center gap-2 px-1 py-4 text-[15px] font-bold transition
                  ${tab === t.key ? 'is-active text-brand-500' : 'text-slate-500 hover:text-slate-700'}`}
              >
                <span className="text-base leading-none">{t.icon}</span>
                {t.label}
              </button>
            ))}
            {translating && <Icon.Spinner className="w-4 h-4 animate-spin text-violet ml-1" />}
          </div>

          <div className="bg-white p-5 sm:p-8">
            {enriching && (
              <div className="mb-5 inline-flex items-center gap-2 rounded-full bg-brand-50 px-3 py-1 text-xs font-bold text-brand-600">
                <Icon.Spinner className="h-3.5 w-3.5 animate-spin" />
                已生成快速摘要，正在补充详细解释和思维导图
              </div>
            )}
            {tab === 'markdown' && (
              <SummaryDigest view={typedView || view} title={task?.title} />
            )}

            {tab === 'outline' && (
              <ol className="space-y-1.5">
                {view.outline?.map((o, i) => (
                  <li key={i}>
                    <a
                      href={jumpUrl(task.webpage_url, o.seconds)}
                      target="_blank"
                      rel="noreferrer"
                      className="group flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white transition"
                    >
                      <span className="shrink-0 font-mono text-xs font-bold px-2 py-1 rounded bg-brand-50 text-brand-600 group-hover:bg-brand-500 group-hover:text-white transition">{o.time}</span>
                      <span className="text-sm text-slate-700 group-hover:text-ink">{o.title}</span>
                    </a>
                  </li>
                ))}
                {(!view.outline || view.outline.length === 0) && (
                  <p className="text-sm text-slate-400">未生成大纲。</p>
                )}
              </ol>
            )}

            {tab === 'mindmap' && (
              <div ref={mapPanelRef} className="mindmap-panel rounded-2xl bg-white border border-slate-100 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-b border-slate-100">
                  <div className="text-sm font-bold text-slate-700">思维导图预览</div>
                  <div className="flex flex-wrap gap-2">
                    <button onClick={toggleFullscreen} className="ai-tool-btn">
                      <Icon.Fullscreen className="w-3.5 h-3.5" /> {isFullscreen ? '退出全屏' : '全屏'}
                    </button>
                    <button onClick={downloadMindmapPng} className="ai-tool-btn">
                      <Icon.Image className="w-3.5 h-3.5" /> PNG
                    </button>
                    <button onClick={downloadMindmapSvg} className="ai-tool-btn">
                      <Icon.Doc className="w-3.5 h-3.5" /> SVG
                    </button>
                  </div>
                </div>
                <div ref={mapRef} className="w-full min-h-[560px]" />
                {!window.markmap && (
                  <pre className="m-3 text-xs whitespace-pre-wrap text-slate-500">{view.mindmap_markdown}</pre>
                )}
              </div>
            )}

            {tab === 'chat' && (
              <div>
                <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                  {messages.length === 0 && (
                    <p className="text-sm text-slate-400">就这个视频的内容向 AI 提问吧，例如“核心结论是什么？”“第二部分讲了什么？”</p>
                  )}
                  {messages.map((m, i) => (
                    <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap
                        ${m.role === 'user' ? 'bg-brand-500 text-white rounded-br-sm' : 'bg-white border border-slate-100 text-slate-700 rounded-bl-sm'}`}>
                        {m.content}
                      </div>
                    </div>
                  ))}
                  {chatting && (
                    <div className="flex justify-start">
                      <div className="px-3.5 py-2.5 rounded-2xl bg-white border border-slate-100">
                        <Icon.Spinner className="w-4 h-4 animate-spin text-violet" />
                      </div>
                    </div>
                  )}
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
                    placeholder="输入你的问题..."
                    className="flex-1 px-4 py-2.5 rounded-full bg-white border border-slate-200 outline-none text-sm focus:ring-2 focus:ring-violet/30"
                  />
                  <button
                    onClick={handleAsk}
                    disabled={chatting}
                    className="grid place-items-center w-10 h-10 rounded-full bg-gradient-to-br from-violet to-brand-500 text-white shadow-glow disabled:opacity-60"
                  >
                    <Icon.Send className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function downloadBlob(blob, filename) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}

function buildMarkdown(r, title) {
  const lines = [`# ${title || '视频总结'}`, '', '## 视频概述', r.overview || '', '', '## 内容大纲']
  normalizeReadableOutline(r).forEach((item, index) => {
    lines.push('', `${index + 1}. **${item.title}**`)
    item.points.forEach((point) => lines.push(`   - ${point}`))
  })
  return lines.join('\n')
}

function StreamingDigest({ partial }) {
  const [displayed, setDisplayed] = useState('')

  useEffect(() => {
    if (!partial) {
      setDisplayed('')
      return
    }
    let cancelled = false
    const timer = setInterval(() => {
      setDisplayed((current) => {
        if (cancelled) return current
        if (current.length >= partial.length) {
          clearInterval(timer)
          return current
        }
        return partial.slice(0, Math.min(partial.length, current.length + 2))
      })
    }, 45)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [partial])

  return (
    <article className="mt-4 w-full rounded-2xl border border-violet/10 bg-white/90 p-4 text-left shadow-card">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-violet">
        <Icon.Spinner className="w-4 h-4 animate-spin" />
        正在流式生成总结摘要
      </div>
      <div
        className="summary-prose text-sm leading-7 text-slate-700"
        dangerouslySetInnerHTML={{ __html: markdownToHtml(displayed) }}
      />
    </article>
  )
}

function SummaryDigest({ view, title }) {
  const outline = normalizeReadableOutline(view)
  const overview = view.overview || `${title || '该视频'} 的概要内容正在生成中。`
  return (
    <article className="summary-readable w-full">
      <section>
        <h2>视频概述</h2>
        <p><InlineRichText text={overview} /></p>
      </section>

      <section className="mt-8">
        <h2>内容大纲</h2>
        <div className="space-y-6">
          {outline.map((item, index) => (
            <div key={`${item.title}-${index}`} className="summary-outline-item">
              <div className="summary-outline-title">
                <span>{index + 1}.</span>
                <strong><InlineRichText text={item.title} /></strong>
              </div>
              {item.points.length > 0 && (
                <ul>
                  {item.points.map((point, pointIndex) => (
                    <li key={pointIndex}><InlineRichText text={point} /></li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>
    </article>
  )
}

function InlineRichText({ text }) {
  return <span dangerouslySetInnerHTML={{ __html: inlineMarkdown(text) }} />
}

function normalizeReadableOutline(view) {
  const outline = (view.outline || [])
    .map((item) => ({
      title: String(item.title || '').trim(),
      points: (item.points || []).map((point) => String(point || '').trim()).filter(Boolean),
    }))
    .filter((item) => item.title || item.points.length)

  if (outline.length) {
    return outline.map((item) => ({
      title: item.title || '未命名章节',
      points: item.points.length ? item.points : [buildFallbackOutlinePoint(item.title, view)],
    }))
  }

  return (view.key_points || []).map((point) => ({
    title: String(point || '').split(/[。！？.!?]/)[0] || '核心要点',
    points: [String(point || '').trim()].filter(Boolean),
  }))
}

function buildFallbackOutlinePoint(title, view) {
  const source = (view.key_points || []).find(Boolean) || view.overview || '该章节对应视频中的一个关键部分。'
  return `${title || '该章节'}：这里需要结合视频上下文理解其具体含义。${source} 因此它不只是一个目录标题，还说明了本节在主题推进、问题解释或实践应用中的作用。`
}

function srtTimestamp(seconds) {
  const total = Math.max(0, Math.floor(seconds || 0))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},000`
}

function segmentsToSrt(segments) {
  return (segments || [])
    .map((seg, index) => {
      const start = Math.floor(seg.start || 0)
      const next = segments[index + 1]
      const end = Math.max(start + 1, Math.floor(next?.start ?? start + 3))
      const text = String(seg.text || '').replace(/\s+/g, ' ').trim()
      if (!text) return null
      return `${index + 1}\n${srtTimestamp(start)} --> ${srtTimestamp(end)}\n${text}\n`
    })
    .filter(Boolean)
    .join('\n')
}

function markdownToHtml(md) {
  const lines = md.split('\n')
  const html = []
  let listOpen = false
  const closeList = () => {
    if (listOpen) {
      html.push('</ul>')
      listOpen = false
    }
  }

  lines.forEach((line) => {
    if (line.startsWith('# ')) {
      closeList()
      html.push(`<h1>${inlineMarkdown(line.slice(2))}</h1>`)
    } else if (line.startsWith('## ')) {
      closeList()
      html.push(`<h2>${inlineMarkdown(line.slice(3))}</h2>`)
    } else if (line.startsWith('### ')) {
      closeList()
      html.push(`<h3>${inlineMarkdown(line.slice(4))}</h3>`)
    } else if (line.startsWith('- ')) {
      if (!listOpen) {
        html.push('<ul>')
        listOpen = true
      }
      html.push(`<li>${inlineMarkdown(line.slice(2))}</li>`)
    } else if (line.trim()) {
      closeList()
      html.push(`<p>${inlineMarkdown(line)}</p>`)
    } else {
      closeList()
    }
  })
  closeList()
  return html.join('')
}

function printableHtml(r, title) {
  const outline = normalizeReadableOutline(r).map((o, index) => {
    const points = (o.points || []).map((point) => `<li>${escapeHtml(point)}</li>`).join('')
    return `<div class="outline-item"><h3><span>${index + 1}.</span> ${escapeHtml(o.title)}</h3><ul>${points}</ul></div>`
  }).join('')
  return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title || '视频总结')}</title>
  <style>body{font-family:system-ui,'Noto Sans SC',sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#0F172A;line-height:1.7}
  h1{font-size:24px}h2{font-size:20px;margin-top:32px;border-bottom:1px solid #e5e7eb;padding-bottom:10px}
  h3{font-size:16px;margin:18px 0 8px}h3 span{color:#1777ff}li{margin:6px 0;color:#43536a}</style></head><body>
  <h1>${escapeHtml(title || '视频总结')}</h1>
  <h2>视频概述</h2><p>${escapeHtml(r.overview)}</p>
  <h2>内容大纲</h2>${outline}
  </body></html>`
}
