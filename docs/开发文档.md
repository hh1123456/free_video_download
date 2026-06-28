# 万能视频下载器 · 开发文档

> 本文记录项目的设计思路、技术决策、核心实现、踩坑记录与拓展指南，便于后续持续开发。
> 配套文档：根目录 `README.md`（面向使用者的快速上手）。

---

## 一、项目背景与目标

很多视频平台不支持下载，或下载不便（无批量、限清晰度、限速等）。本项目做一个**万能视频下载网站**：

- 粘贴链接即可从 **1000+ 平台**下载视频（YouTube / Bilibili / 抖音 / TikTok / X / Vimeo……）
- 高清原画、批量下载、音频提取(MP3)、字幕下载
- 电脑/手机通用，纯网页无需安装
- 预留 AI 能力（视频总结、字幕翻译）

### 核心设计原则
1. **站在巨人肩膀上**：下载这种高风险、高复杂度的核心能力，直接用十几万 Star 的开源项目 [yt-dlp](https://github.com/yt-dlp/yt-dlp)，且**只封装、不改源码**，最大化降低风险与维护成本。
2. **轻量优先**：后端无数据库，纯内存任务态；ffmpeg 免安装。
3. **独特且有价值感的 UI**：参考 [ai.codefather.cn](https://ai.codefather.cn/painting) 的浅色+蓝紫渐变风格。

---

## 二、技术选型与决策

| 维度 | 选型 | 决策理由 |
|---|---|---|
| 下载引擎 | yt-dlp（作为 Python 库 `import yt_dlp`） | 主流、能力强、覆盖平台多；封装调用而非改源码，便于随时升级 |
| 后端框架 | FastAPI + Uvicorn | 轻量、异步、自带文档；适合做解析/下载/进度的薄 API 层 |
| 媒体处理 | ffmpeg（`imageio-ffmpeg` 自带二进制） | 免系统安装、开箱即用；合并音视频、转 MP3、转字幕都依赖它 |
| 数据存储 | 内存字典 + 本地临时目录 | 一期不需要持久化，保持轻量 |
| 前端 | React + Vite + Tailwind(CDN) | 组件化、热更新快；Tailwind 便于 1:1 还原参考站风格 |
| 依赖隔离 | Python venv | 避免污染全局环境、版本冲突 |

> **为什么不直接 fork 现成 Web 项目（如 MeTube）？** 它们的前端是固定框架，要 1:1 改成参考站独特风格反而改动更大。「FastAPI 薄封装 + 自写前端」才是"独特 UI + 改动最少"的最优解。

---

## 三、架构总览

```
浏览器(React)
   │  ① POST /api/parse        → 解析视频信息（不下载）
   │  ② POST /api/download     → 创建后台下载任务，返回 task_id
   │  ③ GET  /api/progress/{id}→ 轮询进度（每 1s）
   │  ④ GET  /api/file/{id}    → 下载完成的文件
   ▼
FastAPI (main.py)
   ▼
DownloadManager (downloader.py)  ── 后台线程 + yt-dlp + 进度回调
   ▼
yt-dlp  ── ffmpeg(内置) 合并/转码  ── downloads/{task_id}/ 临时文件
```

**下载流程的关键点**：下载是异步的——`/api/download` 立即返回 `task_id`，真正的下载在后台线程跑，前端通过轮询 `/api/progress` 获取百分比/速度/状态。这样长耗时下载不会阻塞 HTTP 请求。

---

## 四、目录结构

```
free_viedo_dowload/
├─ backend/
│  ├─ app/
│  │  ├─ main.py          # FastAPI 入口：路由 + 托管前端 + AI 总结接口
│  │  ├─ downloader.py    # 【核心】yt-dlp 封装：解析/下载/进度/音频/字幕/错误翻译
│  │  ├─ ai.py            # 【AI】字幕抓取解析 + DeepSeek 总结/大纲/导图/对话/翻译
│  │  └─ config.py        # 路径、ffmpeg 定位、cookie 文件定位、DeepSeek 配置、.env 加载
│  ├─ bin/                # 自动生成：内置 ffmpeg.exe（gitignore）
│  ├─ .venv/              # 虚拟环境（gitignore）
│  └─ requirements.txt
├─ frontend/
│  ├─ index.html          # Tailwind CDN + 主题色配置
│  ├─ src/
│  │  ├─ App.jsx          # 页面骨架：Hero/平台/能力/CTA/Footer
│  │  ├─ api.js           # 后端接口封装
│  │  └─ components/
│  │     ├─ Navbar.jsx
│  │     ├─ Downloader.jsx   # 单个/批量输入 + 结果列表编排
│  │     ├─ VideoResult.jsx  # 单视频卡片：清晰度/音频/字幕/进度/下载
│  │     └─ icons.jsx        # 内联 SVG 图标
│  └─ dist/               # 构建产物（gitignore），由后端托管
├─ downloads/             # 下载临时目录（gitignore，自动清理）
├─ docs/开发文档.md        # 本文件
├─ README.md
└─ start.ps1              # 一键启动脚本
```

---

## 五、核心模块详解

### 5.1 `downloader.py`（最重要）

- `_base_opts()`：所有 yt-dlp 调用的公共配置。集中了**请求头、重试、ffmpeg、cookie**等关键设置。**新增全局行为优先改这里**。
- `_format_for(max_h)`：生成清晰度的 format 表达式，**兼容性优先**（H.264 > mp4 > 任意）。
- `QUALITY_FORMATS`：清晰度预设映射（best/1080p/720p/480p/360p）。
- `parse_video(url)`：仅解析，返回标题/封面/时长/清晰度列表/字幕语言。
- `friendly_error(exc)`：把底层报错翻译成友好中文提示。
- `DownloadManager`：内存任务管理器。
  - `create_task()`：建任务并起后台线程。
  - `_run()`：实际下载逻辑（音频/字幕/合并分支都在此）。
  - `_progress_hook()`：yt-dlp 进度回调 → 更新任务状态。
  - `cleanup_expired()`：清理过期任务和文件。

### 5.2 `main.py`（API 层）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/parse` | 解析视频 |
| POST | `/api/download` | 创建下载任务 → `{task_id}` |
| GET | `/api/progress/{task_id}` | 查询进度/状态 |
| GET | `/api/file/{task_id}` | 取已完成文件 |
| POST | `/api/ai/summary` | 创建 AI 总结任务（异步）→ `{task_id}` |
| GET | `/api/ai/summary/{task_id}` | 轮询总结进度/结果 |
| POST | `/api/ai/chat` | 基于视频字幕的多轮问答 `{content_key, question, history}` |
| POST | `/api/ai/translate` | 翻译总结结果 `{content_key, target}` |
| GET | `/` | 生产环境托管前端 `dist/`；无 dist 时返回开发提示 |

### 5.4 `ai.py`（AI 视频总结）

- **文本来源**：仅用字幕（人工字幕优先，其次平台自动字幕）。无任何字幕的视频不支持总结。
- `fetch_transcript(url)`：复用 `downloader._base_opts()` 抓字幕(vtt)，`_parse_vtt` 解析为带时间戳片段并去除自动字幕的滚动重复行。
- `summarize()`：调 DeepSeek（JSON 模式）产出 `{overview, key_points, outline[带时间戳], mindmap_markdown}`。
- `chat_over_transcript()` / `translate_summary()`：基于缓存字幕做问答 / 翻译。
- `AISummaryManager`：与 `DownloadManager` 同款"后台线程 + 内存态 + 轮询"模式；内存缓存 `content_key(=task_id) → 字幕片段`，供问答/翻译复用，省钱省时；`get()` 不对外暴露原始字幕。
- **配置**：`DEEPSEEK_API_KEY` 等走环境变量 / `backend/.env`（见 `backend/.env.example`）。

前端 `AiSummary.jsx`：视频卡片下方内联面板，Tab=总结/大纲/思维导图(markmap)/AI问答，支持翻译下拉 + 导出 Markdown + 打印 PDF；大纲时间戳可点击跳转原视频对应位置。

### 5.3 前端

- 状态机：`idle → parsing → parsed → downloading/processing → completed/error`。
- `VideoResult.jsx` 下载完成后自动用 `<a download>` 触发浏览器保存（手机也适用）。
- 进度通过 `setInterval` 每秒轮询，完成/出错即停止。

---

## 六、踩坑记录（重点，拓展前必读）

> 这些是开发中真实遇到并已解决的问题，**改代码前先看这里，避免重复踩坑**。

### 1. ffmpeg 免安装
- **问题**：本机无 ffmpeg，且 `imageio-ffmpeg` 的二进制文件名不标准（`ffmpeg-win64-vX.exe`），yt-dlp 认不出。
- **解决**：`config.get_ffmpeg_dir()` 把它复制为标准 `ffmpeg.exe` 放到 `backend/bin/`，再把目录传给 yt-dlp 的 `ffmpeg_location`。

### 2. yt-dlp 必须保持新版本
- **问题**：各平台风控/接口频繁变动，旧版 yt-dlp 会出现"Requested format is not available""无法解析"等。
- **解决**：定期 `pip install -U yt-dlp`。`requirements.txt` 用 `>=` 不锁死。

### 3. Bilibili HTTP 412 Precondition Failed
- **问题**：B站风控拦截"不像浏览器"的请求。
- **解决**：在 `_base_opts` 的 `http_headers` 加 **`Origin: https://www.bilibili.com`**（关键）+ `Referer` + `User-Agent`。

### 4. B站/会员只能下到 480p
- **原因**：未登录时平台只开放低清晰度。
- **解决**：支持可选 **Cookie 文件**——把浏览器导出的 `cookies.txt` 放 `backend/cookies.txt`（或设环境变量 `COOKIES_FILE`），`config.get_cookies_file()` 自动加载。注意：`cookiesfrombrowser` 直读浏览器在新版 Chrome/Edge 上有 DPAPI 解密失败的坑（yt-dlp#10927），所以用导出文件方式更稳。

### 5. SSL UNEXPECTED_EOF / 连接中断
- **原因**：网络不稳定/代理抖动/平台限流，TLS 连接被掐断。
- **解决**：`_base_opts` 加重试与超时（`retries`、`fragment_retries`、`extractor_retries`、`socket_timeout`）。

### 6. 下载视频"只有声音没画面"
- **原因**：平台优先给 **AV1** 编码，很多播放器/手机不支持 AV1 解码（只解出音频）。
- **解决**：`_format_for()` **优先选 H.264(avc) + AAC**，仅在无 H.264 时才回退到 AV1/VP9。

### 7. Windows 端口占用 / 进程残留
- **现象**：用 PowerShell 起的 uvicorn，杀掉外层进程后，真正监听 8000 的 python 子进程仍存活，导致重启时报 `bind 10048`。
- **解决**：重启前用 `Get-NetTCPConnection -LocalPort 8000` 找到并 `Stop-Process` 真正占用端口的进程。

### 8. 全局环境被污染
- **坑**：一开始把依赖装进了全局 conda 环境，降级了其它项目用到的 fastapi/starlette。
- **解决**：一律用 `backend/.venv` 虚拟环境隔离。

### 9. PowerShell 把 uvicorn 日志当错误
- **现象**：uvicorn 把 INFO 日志写到 stderr，PowerShell 包装成 `NativeCommandError`，看起来像报错，其实服务正常。判断服务是否真起来，看是否有 `Application startup complete`。

---

## 七、拓展开发指南

### 7.1 新增/适配更多平台
基本**无需改代码**——yt-dlp 自带上千平台支持。若某平台失败：
1. 先 `pip install -U yt-dlp`；
2. 若是风控（403/412），参考踩坑 #3/#4，在 `_base_opts` 针对性加请求头或 Cookie。

### 7.2 AI 视频总结（已实现）
实现位于 `backend/app/ai.py` + 前端 `AiSummary.jsx`。能力：结构化总结、带时间戳大纲、思维导图、AI 问答、翻译、导出 MD/PDF。
- **配置密钥**：复制 `backend/.env.example` 为 `backend/.env`，填入 `DEEPSEEK_API_KEY` 后重启后端。
- **当前限制（仅字幕）**：无任何字幕（含平台自动字幕）的视频会提示"暂不支持总结"。
- **后续可拓展无字幕视频**：在 `fetch_transcript` 无字幕分支接 ASR（本地 faster-whisper，或云端 whisper API）得到文本再走同样的总结链路即可。
- **换模型**：DeepSeek 走 OpenAI 兼容协议，改 `.env` 的 `DEEPSEEK_BASE_URL`/`DEEPSEEK_MODEL` 即可指向其它兼容服务。

### 7.3 增加下载历史 / 用户系统（需要持久化）
当前是内存态，重启即丢。若要历史记录：
1. 引入 SQLite（最轻量）或其它数据库；
2. 把 `DownloadManager` 的任务表落库；
3. 加 `/api/history` 接口与前端页面。

### 7.4 部署上线
1. 前端 `npm run build` 生成 `dist/`，由 FastAPI 统一托管（只暴露一个端口）；
2. 用 `uvicorn`/`gunicorn` 起服务，前面挂 Nginx 反代；
3. 注意：服务器需能访问目标平台（境外平台可能需代理，配 yt-dlp 的 `proxy` 选项）；
4. 定时清理 `downloads/`（`cleanup_expired` 已有逻辑，可加定时任务）；
5. 合规：保留免责声明，避免商用受版权内容。

### 7.5 常见小改动速查
| 需求 | 改哪里 |
|---|---|
| 改下载清晰度策略/编码偏好 | `downloader.py` 的 `_format_for()` |
| 改全局请求头/重试/代理 | `downloader.py` 的 `_base_opts()` |
| 加新接口 | `main.py` |
| 改 UI 配色/文案 | `frontend/index.html`(主题色) + `App.jsx`/各组件 |
| 改清晰度按钮选项 | `frontend/src/components/VideoResult.jsx` 的 `PRESETS` |
| 改任务保留时间 | 环境变量 `TASK_TTL_SECONDS`（下载）/ `AI_TASK_TTL_SECONDS`（AI 总结） |
| 配 AI 密钥/换模型 | `backend/.env`（`DEEPSEEK_API_KEY`/`DEEPSEEK_BASE_URL`/`DEEPSEEK_MODEL`） |
| 改总结输出结构/提示词 | `ai.py` 的 `_SUMMARY_SYSTEM` 与 `summarize()` |
| 改字幕语言优先级 | `config.py` 的 `SUBTITLE_LANG_PRIORITY` |
| 改 AI 面板/Tab/导出 | `frontend/src/components/AiSummary.jsx` |

---

## 八、本地开发与测试

### 启动
见 `README.md`（`start.ps1` 一键启动，或前后端分别启动）。

### 快速自测（PowerShell）
```powershell
# 解析
$b=@{url='https://vimeo.com/76979871'}|ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/parse -Method Post -Body $b -ContentType application/json

# 下载并轮询
$b=@{url='https://vimeo.com/76979871';quality='360p'}|ConvertTo-Json
$d=Invoke-RestMethod -Uri http://127.0.0.1:8000/api/download -Method Post -Body $b -ContentType application/json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/progress/$($d.task_id)"
```

### 验证下载文件的编码（排查"没画面"）
```powershell
backend\bin\ffmpeg.exe -i "目标文件.mp4"   # 看 Stream #0:0 是否为 h264
```

---

## 九、版本与依赖

- Python 3.13、Node 22
- 关键依赖：`fastapi`、`uvicorn`、`yt-dlp`(保持最新)、`imageio-ffmpeg`、`openai`(接 DeepSeek)、`react`、`vite`、`markmap`(CDN)
- 内置 ffmpeg：4.2.2（由 imageio-ffmpeg 提供）

---

## 十、变更记录（开发里程碑）

1. 搭建骨架：FastAPI 后端 + React/Vite 前端 + venv 隔离。
2. 后端封装 yt-dlp：解析/下载/进度/音频MP3/字幕；集成内置 ffmpeg。
3. 前端还原参考站 UI：Hero + 胶囊搜索框 + 结果卡片 + 进度 + 批量 + 平台/能力展示。
4. 全流程自测通过（Vimeo 解析→下载→合并→音频→UI 链路）。
5. 修复 Bilibili 412（加 Origin 头）+ 支持 Cookie 文件取高清。
6. 增强网络健壮性（重试/超时）+ 友好错误提示。
7. 修复"只有声音没画面"（编码兼容性优先 H.264）。
8. **AI 视频总结上线**：字幕抓取解析 + DeepSeek 结构化总结/带时间戳大纲/思维导图/AI 问答/翻译；前端视频卡片内联面板，支持导出 Markdown / 打印 PDF。当前为"仅字幕"方案，无字幕视频暂不支持。
## 2026-06-21 Troubleshooting And Implementation Update

### 1. Bilibili Subtitle And Download Handling

- `backend/cookies.txt` uses Netscape-format cookies exported from a logged-in browser session. Keep Bilibili-related cookies only when possible.
- AI summary now follows a subtitle-first strategy:
  - Try yt-dlp subtitles and automatic captions.
  - For Bilibili, fall back to the player subtitle API:
    - `x/web-interface/view?bvid=...` to get `aid` and `cid`.
    - `x/player/wbi/v2?aid=...&cid=...` to get subtitle metadata.
    - Download `subtitle_url` JSON and convert Bilibili subtitle bodies into internal transcript segments.
- Download quality selection now has a fallback for cases where a requested quality has no matching stream. Example: if `480p` has no `height<=480` stream, the format selector can fall back to the lowest available video stream instead of failing with `Requested format is not available`.

### 2. Whisper ASR Fallback

- Summary uses subtitles first. Whisper is only needed when no usable subtitles are found and `ENABLE_ASR=1`.
- `faster-whisper` loads the configured model from `WHISPER_MODEL` (`small` by default).
- Hugging Face official access can time out in this environment. `config.py` defaults `HF_ENDPOINT` to `https://hf-mirror.com`, which has been verified reachable.
- The `small` Whisper model has been loaded once successfully, which caches it locally for later ASR use.
- Operational switch:
  - `ENABLE_ASR=1`: no-subtitle videos can fall back to local Whisper transcription.
  - `ENABLE_ASR=0`: no-subtitle videos fail fast with a clear no-subtitle message.

### 3. Douyin Short-Link Parsing

- Douyin share short links such as `https://v.douyin.com/xujb7b1B7IQ` are valid inputs.
- The short link redirects to a real video URL such as `https://www.douyin.com/video/7653463628881346661?...`.
- The failure `Fresh cookies (not necessarily logged in) are needed` was not caused by missing Douyin login cookies in the verified case.
- Root cause: `_base_opts()` previously sent Bilibili-only headers (`Referer` and `Origin`) to every platform. Douyin parsing can fail when it receives those Bilibili headers.
- Fix: `_base_opts(url)` is now URL-aware:
  - Bilibili URLs keep `Referer: https://www.bilibili.com/` and `Origin: https://www.bilibili.com`.
  - Douyin and other platforms use generic browser headers only.
- All call sites that create yt-dlp options should pass the current URL into `_base_opts(url)`, including parse, download, subtitle fetching, and ASR audio download paths.
- Verified real parse result for `https://v.douyin.com/xujb7b1B7IQ`:
  - `extractor`: `Douyin`
  - `id`: `7653463628881346661`
  - `duration`: `1:53`
  - `/api/parse`: HTTP 200

### 4. Verification Commands

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest tests.test_downloader_errors tests.test_downloader_formats tests.test_ai_summary
```

Real-network spot checks used during debugging:

```powershell
curl.exe -I --connect-timeout 10 https://huggingface.co
curl.exe -I --connect-timeout 10 https://hf-mirror.com
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('ok')"
```

## 2026-06-21 AI Reading And Export Improvements

### 1. Markdown Reading

- The AI summary panel now has a `Markdown` tab.
- Frontend file: `frontend/src/components/AiSummary.jsx`.
- Styling uses Tailwind Typography via CDN (`https://cdn.tailwindcss.com?plugins=typography`) plus local `.summary-prose` tweaks in `frontend/src/index.css`.
- The Markdown tab is built from the existing structured summary fields, so it does not change the backend LLM response schema.

### 2. Mind Map Fullscreen And PNG Export

- The mind map tab now has:
  - `Fullscreen`: uses the browser Fullscreen API and calls `markmap.fit()` after layout changes.
  - `Download image`: serializes the rendered SVG, draws it to a 2x canvas, and downloads a PNG.
- No new frontend dependency is required.
- Main implementation: `frontend/src/components/AiSummary.jsx`.

### 3. Transcript / Subtitle SRT Download

- The AI summary toolbar now has a `字幕` download button.
- Because transcript segments are intentionally hidden from the polling response, SRT download is implemented by the backend:
  - `GET /api/ai/transcript/{task_id}.srt`
  - Returns the completed task transcript as an SRT attachment.
- Backend helper:
  - `segments_to_srt(segments)` in `backend/app/ai.py`.
  - `AISummaryManager.get_transcript_download(task_id)` reads completed cached segments only.
- Frontend helper:
  - `transcriptDownloadUrl(taskId)` in `frontend/src/api.js`.

### 4. Verification

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest tests.test_downloader_errors tests.test_downloader_formats tests.test_ai_summary

cd ..\frontend
npm run build
```
