import { useEffect, useState } from 'react'
import { getCurrentUser, login, logout } from './api'
import Navbar from './components/Navbar'
import Downloader from './components/Downloader'
import LoginPage from './components/LoginPage'
import { Icon } from './components/icons'

const FEATURES = [
  {
    icon: '🌐',
    tint: 'bg-blue-50',
    title: '支持 1800+ 平台',
    desc: 'YouTube、Bilibili、抖音、TikTok、Twitter、Instagram 等全球主流平台',
  },
  {
    icon: '⚡',
    tint: 'bg-amber-50',
    title: '极速解析下载',
    desc: '智能解析视频链接，自动匹配最优下载方式，速度快人一步',
  },
  {
    icon: '📱',
    tint: 'bg-emerald-50',
    title: '手机也能用',
    desc: '完美适配手机浏览器，随时随地想下就下，无需安装任何 App',
  },
  {
    icon: '🎬',
    tint: 'bg-violet/10',
    title: '多种清晰度',
    desc: '支持从 360p 到 4K 多种清晰度选择，满足不同场景需求',
  },
  {
    icon: '🤖',
    tint: 'bg-rose-50',
    title: 'AI 视频总结',
    desc: 'AI 智能分析视频内容，一键生成摘要、思维导图，还能针对视频提问',
  },
]

export default function App() {
  const [user, setUser] = useState(null)
  const [checkingAuth, setCheckingAuth] = useState(true)

  useEffect(() => {
    let alive = true
    getCurrentUser()
      .then((currentUser) => {
        if (alive) setUser(currentUser)
      })
      .catch(() => {
        if (alive) setUser(null)
      })
      .finally(() => {
        if (alive) setCheckingAuth(false)
      })
    return () => {
      alive = false
    }
  }, [])

  async function handleLogin(credentials) {
    const currentUser = await login(credentials)
    setUser(currentUser)
  }

  async function handleLogout() {
    await logout().catch(() => {})
    setUser(null)
  }

  if (checkingAuth) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f7f9fc] text-slate-500">
        <div className="inline-flex items-center gap-3 rounded-2xl bg-white px-6 py-4 text-base font-extrabold shadow-card">
          <Icon.Spinner className="h-6 w-6 animate-spin text-brand-500" />
          正在检查登录状态...
        </div>
      </div>
    )
  }

  if (!user) {
    return <LoginPage onLogin={handleLogin} />
  }

  return (
    <div id="top" className="min-h-screen bg-white text-[#202226]">
      <Navbar user={user} onLogout={handleLogout} />

      <main>
        <section className="relative overflow-hidden bg-gradient-to-b from-[#f4f8ff] via-white to-white px-6 pb-16 pt-14 sm:pt-20 lg:px-12">
          <div className="absolute left-1/2 top-20 h-72 w-[980px] -translate-x-1/2 rounded-full bg-brand-100/45 blur-3xl" />

          <div className="relative mx-auto max-w-[1760px] text-center">
            <div className="mb-11 inline-flex items-center gap-3 rounded-full border border-slate-200 bg-white px-6 py-2 text-lg font-semibold text-slate-500 shadow-card">
              <span className="h-3 w-3 rounded-full bg-emerald-400" />
              支持 1800+ 平台，永久免费使用
            </div>

            <h1 className="text-5xl font-black leading-tight tracking-[-0.05em] text-[#202226] sm:text-6xl lg:text-7xl">
              免费在线视频下载器，
              <span className="text-brand-500">一键保存</span>
            </h1>

            <p className="mx-auto mt-7 max-w-4xl text-xl font-medium leading-10 text-slate-500 sm:text-2xl">
              粘贴视频链接，智能解析下载。支持 YouTube、Bilibili、抖音、TikTok 等 1800+ 平台，
              多种清晰度可选，还能 AI 总结视频内容
            </p>

            <div className="mx-auto mt-12 w-full">
              <Downloader />
            </div>
          </div>
        </section>

        <section id="features" className="bg-[#f7f8fb] px-5 py-12 sm:py-16">
          <div className="mx-auto max-w-[1520px]">
            <div className="mb-16 text-center">
              <h2 className="text-4xl font-black tracking-[-0.04em] text-[#202226] sm:text-5xl">
                为什么选择 <span className="text-brand-500">SaveAny</span> 视频下载器
              </h2>
              <p className="mt-5 text-xl font-medium text-slate-500">
                简单、快速、强大的在线视频下载体验，支持 AI 智能总结
              </p>
            </div>

            <div className="grid gap-7 md:grid-cols-2 xl:grid-cols-5">
              {FEATURES.map((feature) => (
                <article
                  key={feature.title}
                  className="rounded-[1.35rem] border border-slate-100 bg-white p-9 text-left shadow-[0_12px_36px_-20px_rgba(15,23,42,0.22)] transition hover:-translate-y-1 hover:shadow-card"
                >
                  <div className={`mb-8 grid h-[74px] w-[74px] place-items-center rounded-2xl ${feature.tint} text-3xl`}>
                    {feature.icon}
                  </div>
                  <h3 className="text-2xl font-black text-[#202226]">{feature.title}</h3>
                  <p className="mt-5 text-lg font-medium leading-9 text-slate-500">{feature.desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
