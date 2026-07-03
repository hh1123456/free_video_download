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
## 2026-06-21 问题排查与实现更新

### 1. B 站字幕与下载处理

- `backend/cookies.txt` 使用从已登录浏览器导出的 Netscape 格式 Cookie，建议尽量只保留 B 站相关条目。
- AI 总结采用**字幕优先**策略：
  - 先尝试 yt-dlp 字幕与自动字幕。
  - 对 B 站，回退到播放器字幕 API：
    - `x/web-interface/view?bvid=...` 获取 `aid` 与 `cid`。
    - `x/player/wbi/v2?aid=...&cid=...` 获取字幕元数据。
    - 下载 `subtitle_url` 的 JSON，并将 B 站字幕正文转换为内部 transcript 片段。
- 下载清晰度选择增加回退：当请求的清晰度没有匹配流时不再直接失败。例如 `480p` 若无 `height<=480` 的流，格式选择器会回退到当前可用的最低清晰度视频流，而不是报 `Requested format is not available`。

### 2. Whisper ASR 回退

- 总结仍优先使用字幕；仅在没有可用字幕且 `ENABLE_ASR=1` 时才启用 Whisper。
- `faster-whisper` 按 `WHISPER_MODEL` 加载模型（默认 `small`）。
- 本环境访问 Hugging Face 官方源可能超时，`config.py` 默认 `HF_ENDPOINT` 为 `https://hf-mirror.com`，已验证可访问。
- `small` 模型已成功加载过一次，本地已缓存，后续 ASR 可直接复用。
- 运行开关：
  - `ENABLE_ASR=1`：无字幕视频可回退到本地 Whisper 转写。
  - `ENABLE_ASR=0`：无字幕视频快速失败，并给出明确的无字幕提示。

### 3. 抖音短链解析

- 抖音分享短链（如 `https://v.douyin.com/xujb7b1B7IQ`）可作为有效输入。
- 短链会重定向到真实视频地址，如 `https://www.douyin.com/video/7653463628881346661?...`。
- 报错 `Fresh cookies (not necessarily logged in) are needed` 在已验证案例中**并非**因缺少抖音登录 Cookie。
- 根因：`_base_opts()` 此前对所有平台都发送 B 站专用请求头（`Referer` 与 `Origin`），抖音收到 B 站头后会解析失败。
- 修复：`_base_opts(url)` 现按 URL 区分：
  - B 站 URL 保留 `Referer: https://www.bilibili.com/` 与 `Origin: https://www.bilibili.com`。
  - 抖音及其他平台仅使用通用浏览器请求头。
- 所有创建 yt-dlp 选项的调用点都应把当前 URL 传入 `_base_opts(url)`，包括解析、下载、字幕抓取与 ASR 音频下载路径。
- 已验证 `https://v.douyin.com/xujb7b1B7IQ` 的真实解析结果：
  - `extractor`：`Douyin`
  - `id`：`7653463628881346661`
  - `duration`：`1:53`
  - `/api/parse`：HTTP 200

### 4. 验证命令

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest tests.test_downloader_errors tests.test_downloader_formats tests.test_ai_summary
```

调试过程中使用的真实网络抽查：

```powershell
curl.exe -I --connect-timeout 10 https://huggingface.co
curl.exe -I --connect-timeout 10 https://hf-mirror.com
.\.venv\Scripts\python.exe -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('ok')"
```

## 2026-06-21 AI 阅读与导出增强

### 1. Markdown 阅读

- AI 总结面板新增 `Markdown` 标签页。
- 前端文件：`frontend/src/components/AiSummary.jsx`。
- 样式通过 CDN 引入 Tailwind Typography（`https://cdn.tailwindcss.com?plugins=typography`），并在 `frontend/src/index.css` 中用本地 `.summary-prose` 做微调。
- Markdown 内容由现有结构化总结字段拼装，**不改动**后端 LLM 响应结构。

### 2. 思维导图全屏与 PNG 导出

- 思维导图标签页新增：
  - `全屏`：使用浏览器 Fullscreen API，布局变化后调用 `markmap.fit()`。
  - `下载图片`：序列化已渲染的 SVG，绘制到 2 倍 canvas 后导出 PNG。
- 无需新增前端依赖。
- 主要实现：`frontend/src/components/AiSummary.jsx`。

### 3. 字幕 SRT 下载

- AI 总结工具栏新增 `字幕` 下载按钮。
- 因轮询响应刻意不返回原始字幕片段，SRT 下载由后端实现：
  - `GET /api/ai/transcript/{task_id}.srt`
  - 以 SRT 附件形式返回已完成任务的字幕。
- 后端辅助：
  - `backend/app/ai.py` 中的 `segments_to_srt(segments)`。
  - `AISummaryManager.get_transcript_download(task_id)` 仅读取已完成任务的缓存片段。
- 前端辅助：
  - `frontend/src/api.js` 中的 `transcriptDownloadUrl(taskId)`。

### 4. 验证

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest tests.test_downloader_errors tests.test_downloader_formats tests.test_ai_summary

cd ..\frontend
npm run build
```

## 2026-07-04 AI 总结体验与解析结果增强

### 1. AI 总结深度与表达升级

- 后端总结提示词增强，要求模型输出更有洞察的内容：不仅复述视频，还要提炼核心观点、潜在逻辑、情绪走向、反常识信息和可行动启发。
- 输出风格从"规矩摘要"调整为更像内容编辑的分析：保留结构化字段，同时鼓励适度使用重点标记、短句节奏和更有趣的表达。
- 仍沿用原有 JSON 结构，避免破坏前端 `AiSummary.jsx` 的展示、翻译、导出和问答链路。
- 主要文件：`backend/app/ai.py`。

### 2. 重点标记与流式展示修复

- 前端新增安全的行内 Markdown 渲染，只支持有限的 `**重点**` 标记，并先转义 HTML，避免把模型输出直接当作不可信 HTML 注入。
- 修复 AI 总结"文档加载完后瞬间全部出现"的问题：动画 key 从只依赖 `task.id` 改为内容感知，保证同一个任务在获得更丰富总结内容时仍会重新触发逐字/流式展示动画。
- 主要文件：
  - `frontend/src/inlineMarkdown.js`
  - `frontend/src/summaryAnimation.js`
  - `frontend/src/components/AiSummary.jsx`

### 3. 解析视频进度条

- 解析阶段新增前端进度面板，在还没有生成视频内容前显示在内容区域中间，避免用户点击解析后长时间无反馈。
- 由于 `/api/parse` 当前是同步接口，进度条采用前端阶段式模拟：提交链接、连接平台、读取媒体信息、整理清晰度与字幕、生成结果。
- 进度会在请求未完成时缓慢推进并封顶，接口返回后再进入完成态；这样不改后端协议，也能给用户稳定的等待反馈。
- 主要文件：
  - `frontend/src/parseProgress.js`
  - `frontend/src/components/Downloader.jsx`

### 4. 视频信息卡与下载大小展示

- 解析完成后的左侧视频卡片补充更多信息：平台、时长、作者、播放量、视频 ID、字幕语言、清晰度数量等，并用不同颜色标签区分信息类型。
- 清晰度/下载按钮增加文件大小提示：能从解析结果拿到 `filesize` 时展示约 `128 MB` 这类大小；缺失时显示"大小未知"。
- `最佳画质` 会从可用清晰度中选取最高项并展示对应最高分辨率与大小，具体清晰度按钮展示自己的大小。
- 主要文件：
  - `frontend/src/videoInfo.js`
  - `frontend/src/components/VideoResult.jsx`

### 5. 部署更新路径确认

- 当前更新分支为 `codex/deep-ai-summary`，最新功能提交为 `e43707b feat: enrich video info card`。
- 服务器若原来连接码云，可额外添加 GitHub 远端，例如 `github`，再拉取 `github/codex/deep-ai-summary` 分支。
- Docker 部署更新流程已验证：拉取最新代码后执行 `docker compose up -d --build`，再用 `/api/health` 检查服务状态。

### 6. 验证

```powershell
cd frontend
node --test src/videoInfo.test.js src/parseProgress.test.js src/inlineMarkdown.test.js src/summaryAnimation.test.js
npm run build
```

验证结果：

- 前端相关单元测试：11/11 通过。
- Vite 生产构建通过。
