import { useState } from 'react'
import { Icon } from './icons'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('player')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await onLogin({ username: username.trim(), password })
    } catch (err) {
      setError(err.message || '登录失败，请稍后再试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-gradient-to-br from-[#eef5ff] via-white to-[#f8fbff] px-5 py-10 text-[#202226]">
      <div className="absolute left-[-12rem] top-[-10rem] h-[34rem] w-[34rem] rounded-full bg-brand-100/70 blur-3xl" />
      <div className="absolute bottom-[-14rem] right-[-10rem] h-[38rem] w-[38rem] rounded-full bg-blue-100/80 blur-3xl" />

      <section className="relative mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <div className="mb-8 inline-flex items-center gap-3 rounded-full border border-slate-200 bg-white/80 px-5 py-2 text-sm font-extrabold text-slate-500 shadow-card backdrop-blur">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            私有访问模式已开启
          </div>

          <h1 className="text-5xl font-black leading-tight tracking-[-0.055em] sm:text-6xl">
            登录后使用
            <span className="block text-brand-500">万能视频下载器</span>
          </h1>

          <p className="mt-7 max-w-2xl text-xl font-medium leading-10 text-slate-500">
            当前站点已开启单账号保护。登录后可以继续使用视频解析、下载、字幕导出和 AI 视频总结功能。
          </p>

          <div className="mt-10 grid max-w-2xl gap-4 sm:grid-cols-3">
            {['视频下载', '字幕导出', 'AI 总结'].map((item) => (
              <div key={item} className="rounded-2xl border border-white bg-white/80 p-5 text-left shadow-[0_16px_36px_-24px_rgba(15,23,42,0.42)]">
                <Icon.Check className="mb-4 h-6 w-6 text-brand-500" />
                <p className="text-base font-black text-slate-700">{item}</p>
              </div>
            ))}
          </div>
        </div>

        <form onSubmit={handleSubmit} className="rounded-[2rem] border border-white bg-white/90 p-8 text-left shadow-card backdrop-blur sm:p-10">
          <div className="mb-8">
            <div className="mb-5 grid h-16 w-16 place-items-center rounded-2xl bg-brand-500 text-white shadow-glow">
              <Icon.Shield className="h-8 w-8" />
            </div>
            <h2 className="text-3xl font-black tracking-[-0.04em] text-slate-900">账号登录</h2>
            <p className="mt-3 text-base font-medium text-slate-500">请输入管理员分配的账号密码。</p>
          </div>

          <label className="block">
            <span className="text-sm font-extrabold text-slate-500">账号</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-lg font-bold outline-none transition focus:border-brand-300 focus:bg-white focus:ring-4 focus:ring-brand-100"
              placeholder="player"
            />
          </label>

          <label className="mt-5 block">
            <span className="text-sm font-extrabold text-slate-500">密码</span>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete="current-password"
              className="mt-2 w-full rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-lg font-bold outline-none transition focus:border-brand-300 focus:bg-white focus:ring-4 focus:ring-brand-100"
              placeholder="请输入密码"
            />
          </label>

          {error && (
            <div className="mt-5 rounded-2xl border border-red-100 bg-red-50 px-5 py-4 text-sm font-bold text-red-500">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-7 inline-flex w-full items-center justify-center gap-3 rounded-2xl bg-brand-500 px-7 py-4 text-lg font-black text-white shadow-glow transition hover:bg-brand-600 disabled:opacity-60"
          >
            {loading ? <Icon.Spinner className="h-6 w-6 animate-spin" /> : <Icon.Shield className="h-6 w-6" />}
            {loading ? '登录中...' : '进入系统'}
          </button>
        </form>
      </section>
    </main>
  )
}
