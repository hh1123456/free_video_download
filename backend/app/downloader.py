"""yt-dlp 薄封装层。

设计原则：不修改 yt-dlp 源码，只把它当库调用（封装）。这里提供：
- parse_video: 仅解析视频信息（不下载），返回标题/封面/时长/清晰度列表/字幕语言
- DownloadManager: 后台线程下载 + 进度回调 + 音频提取 + 字幕下载
"""
from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yt_dlp

from .config import DOWNLOAD_DIR, TASK_TTL_SECONDS, get_cookies_file, get_ffmpeg_dir

FFMPEG_DIR = get_ffmpeg_dir()

def _format_for(max_h: Optional[int]) -> str:
    """生成 yt-dlp format 选择表达式。

    兼容性优先：优先选择 H.264(avc) 视频 + AAC(mp4a) 音频，这是几乎所有播放器
    和手机都能直接播放的"万能编码"；只有当平台没有 H.264 时，才回退到其它编码
    （如 AV1/VP9）。避免出现"只有声音没画面"（播放器不支持 AV1）的问题。
    """
    h = f"[height<={max_h}]" if max_h else ""
    fallback = "" if not max_h else (
        "worstvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/"
        "worstvideo[ext=mp4]+bestaudio[ext=m4a]/"
        "worstvideo+bestaudio/"
    )
    return (
        f"bestvideo{h}[vcodec^=avc]+bestaudio[acodec^=mp4a]/"  # 最佳 H.264 + AAC
        f"bestvideo{h}[ext=mp4]+bestaudio[ext=m4a]/"            # 退而求其次：mp4 容器
        f"bestvideo{h}+bestaudio/"                              # 再退：任意编码合并
        f"{fallback}"                                            # 若没有低于目标清晰度的流，选最低可用流
        f"best{h}/best"                                          # 最后：单一最佳流
    )


# 提供给用户的清晰度预设 -> yt-dlp format 选择表达式
QUALITY_FORMATS: Dict[str, str] = {
    "best": _format_for(None),
    "1080p": _format_for(1080),
    "720p": _format_for(720),
    "480p": _format_for(480),
    "360p": _format_for(360),
}


# 模拟真实浏览器请求头，绕过 B站等平台的风控（如 HTTP 412 Precondition Failed）
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _is_bilibili_url(url: Optional[str]) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return "bilibili.com" in host or "b23.tv" in host


def _base_opts(url: Optional[str] = None) -> Dict[str, Any]:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if _is_bilibili_url(url):
        headers.update(
            {
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
            }
        )
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        # 网络健壮性：自动重试，缓解 SSL EOF / 连接中断 / 限流等瞬时错误
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 5,
        "file_access_retries": 5,
        "socket_timeout": 30,
        "concurrent_fragment_downloads": 1,
        "http_headers": {
            "User-Agent": _USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.bilibili.com/",
            # B站风控需要 Origin 头，否则接口返回 HTTP 412 Precondition Failed
            "Origin": "https://www.bilibili.com",
        },
    }
    if FFMPEG_DIR:
        opts["ffmpeg_location"] = FFMPEG_DIR
    opts["http_headers"] = headers
    cookies = get_cookies_file()
    if cookies:
        opts["cookiefile"] = cookies
    return opts


def friendly_error(exc: Exception) -> str:
    """把底层报错翻译成更友好的中文提示。"""
    msg = str(exc)
    low = msg.lower()
    if "winerror 10013" in low:
        return (
            "网络连接被系统拦截（WinError 10013），当前这台机器上的 Python/命令行程序无法正常建立外部连接。"
            "这通常是防火墙、安全软件、代理/VPN 或系统网络策略导致的。"
            "请先检查系统网络权限后再重试。原始错误码：10013。"
        )
    if "unexpected_eof" in low or "ssl" in low or "eof occurred" in low:
        return "网络连接被中断（SSL EOF）。多为网络不稳定/代理波动/平台限流导致，请稍后重试或更换网络；若使用代理请确认其稳定。"
    if "412" in msg and "precondition" in low:
        return "平台风控拦截（HTTP 412）。请稍后重试；如为 B站高清/会员内容，需提供登录 Cookie。"
    if "timed out" in low or "timeout" in low:
        return "连接超时，请检查网络后重试。"
    if "http error 403" in low or "forbidden" in low:
        return "访问被拒绝（403）。该内容可能需要登录 Cookie 或存在地区限制。"
    if "http error 404" in low or "not found" in low:
        return "找不到该视频（404），链接可能已失效或被删除。"
    if "private" in low or "login" in low or "sign in" in low:
        return "该视频需要登录/为私密内容，请提供登录 Cookie 后重试。"
    if "unsupported url" in low or "no video" in low:
        return "暂不支持该链接，请确认是有效的视频页面地址。"
    return msg


def _human_size(num: Optional[float]) -> Optional[str]:
    if not num:
        return None
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    for unit in units:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}PB"


def parse_video(url: str) -> Dict[str, Any]:
    """仅解析视频信息，不下载。"""
    opts = _base_opts(url)
    opts["skip_download"] = True
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # 部分链接是播放列表，这里取第一个条目兜底
    if info.get("_type") == "playlist" and info.get("entries"):
        entries = [e for e in info["entries"] if e]
        info = entries[0] if entries else info

    # 整理可下载的视频清晰度（仅保留有画面或合并后的格式，去重展示）
    seen_heights = set()
    qualities: List[Dict[str, Any]] = []
    for f in info.get("formats", []) or []:
        height = f.get("height")
        vcodec = f.get("vcodec")
        if not height or vcodec in (None, "none"):
            continue
        if height in seen_heights:
            continue
        seen_heights.add(height)
        qualities.append(
            {
                "height": height,
                "label": f"{height}p",
                "ext": f.get("ext"),
                "filesize": _human_size(f.get("filesize") or f.get("filesize_approx")),
            }
        )
    qualities.sort(key=lambda x: x["height"], reverse=True)

    subtitles = sorted(
        set(list((info.get("subtitles") or {}).keys()) + list((info.get("automatic_captions") or {}).keys()))
    )

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "duration_string": info.get("duration_string"),
        "uploader": info.get("uploader") or info.get("channel"),
        "extractor": info.get("extractor_key") or info.get("extractor"),
        "webpage_url": info.get("webpage_url") or url,
        "view_count": info.get("view_count"),
        "qualities": qualities,
        "subtitles": subtitles,
    }


class DownloadManager:
    """管理后台下载任务（内存态，无数据库）。"""

    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _set(self, task_id: str, **kwargs: Any) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def create_task(
        self,
        url: str,
        quality: str = "best",
        audio_only: bool = False,
        subtitle_lang: Optional[str] = None,
    ) -> str:
        task_id = uuid.uuid4().hex
        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "url": url,
                "status": "queued",
                "percent": 0.0,
                "speed": None,
                "eta": None,
                "title": None,
                "filename": None,
                "error": None,
                "created_at": time.time(),
            }
        thread = threading.Thread(
            target=self._run,
            args=(task_id, url, quality, audio_only, subtitle_lang),
            daemon=True,
        )
        thread.start()
        return task_id

    def _progress_hook(self, task_id: str):
        def hook(d: Dict[str, Any]) -> None:
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes") or 0
                percent = (downloaded / total * 100) if total else 0.0
                self._set(
                    task_id,
                    status="downloading",
                    percent=round(percent, 1),
                    speed=_human_size(d.get("speed")),
                    eta=d.get("eta"),
                )
            elif status == "finished":
                # 下载完成，可能进入后处理（合并/转码）
                self._set(task_id, status="processing", percent=99.0)

        return hook

    def _run(
        self,
        task_id: str,
        url: str,
        quality: str,
        audio_only: bool,
        subtitle_lang: Optional[str],
    ) -> None:
        task_dir = DOWNLOAD_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        opts = _base_opts(url)
        opts["outtmpl"] = str(task_dir / "%(title).80s.%(ext)s")
        opts["progress_hooks"] = [self._progress_hook(task_id)]

        if audio_only:
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            opts["format"] = QUALITY_FORMATS.get(quality, QUALITY_FORMATS["best"])
            # 优先合并为 mp4，方便手机/通用播放
            opts["merge_output_format"] = "mp4"

        if subtitle_lang:
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitleslangs"] = [subtitle_lang]
            opts["subtitlesformat"] = "srt/best"
            opts["postprocessors"] = opts.get("postprocessors", []) + [
                {"key": "FFmpegSubtitlesConvertor", "format": "srt"}
            ]

        try:
            self._set(task_id, status="downloading")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info.get("_type") == "playlist" and info.get("entries"):
                    entries = [e for e in info["entries"] if e]
                    info = entries[0] if entries else info

            # 找到产出的主文件（排除字幕）
            files = sorted(
                [p for p in task_dir.iterdir() if p.is_file()],
                key=lambda p: p.stat().st_size,
                reverse=True,
            )
            main_file = files[0] if files else None
            self._set(
                task_id,
                status="completed",
                percent=100.0,
                title=info.get("title"),
                filename=main_file.name if main_file else None,
            )
        except Exception as exc:  # noqa: BLE001
            self._set(task_id, status="error", error=friendly_error(exc))

    def cleanup_expired(self) -> None:
        """清理过期任务及其文件。"""
        now = time.time()
        expired: List[str] = []
        with self._lock:
            for tid, task in self._tasks.items():
                if now - task["created_at"] > TASK_TTL_SECONDS:
                    expired.append(tid)
        for tid in expired:
            task_dir = DOWNLOAD_DIR / tid
            try:
                if task_dir.exists():
                    for p in task_dir.iterdir():
                        p.unlink(missing_ok=True)
                    task_dir.rmdir()
            except Exception:
                pass
            with self._lock:
                self._tasks.pop(tid, None)


manager = DownloadManager()
