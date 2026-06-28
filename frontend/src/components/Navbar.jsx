export default function Navbar({ user, onLogout }) {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-100 bg-white/95 backdrop-blur">
      <nav className="mx-auto flex h-[88px] max-w-[1760px] items-center justify-between px-6 lg:px-12">
        <a href="#top" className="flex items-center gap-4">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-500 text-white shadow-glow">
            <span className="grid h-7 w-7 place-items-center rounded-full border-2 border-white">
              <span className="ml-0.5 h-0 w-0 border-y-[6px] border-l-[9px] border-y-transparent border-l-white" />
            </span>
          </span>
          <span className="text-3xl font-black tracking-tight text-[#222]">SaveAny</span>
          <span className="hidden rounded-full bg-brand-50 px-4 py-1.5 text-sm font-bold text-slate-400 sm:inline-flex">
            万能视频下载
          </span>
        </a>

        <div className="hidden items-center gap-10 text-lg font-bold text-slate-500 lg:flex">
          <a href="#features" className="transition hover:text-brand-500">功能特性</a>
          <a href="#how-to" className="transition hover:text-brand-500">使用教程</a>
          <a href="#compare" className="transition hover:text-brand-500">工具对比</a>
          <a href="#pricing" className="transition hover:text-brand-500">套餐价格</a>
        </div>

        <div className="flex items-center gap-5">
          <button
            onClick={onLogout}
            className="hidden text-lg font-bold text-slate-500 transition hover:text-ink sm:inline-flex"
          >
            退出登录
          </button>
          <a
            href="#download"
            className="rounded-full bg-brand-500 px-7 py-3 text-lg font-extrabold text-white shadow-glow transition hover:bg-brand-600"
          >
            {user?.username || 'player'}
          </a>
        </div>
      </nav>
    </header>
  )
}
