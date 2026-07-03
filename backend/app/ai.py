"""AI video summary: transcript fetching, summarization, chat, translation."""
from __future__ import annotations

import json
import re
import tempfile
import threading
import time
import urllib.request
import uuid
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, build_opener

import yt_dlp

from . import config
from .config import get_cookies_file
from .downloader import _USER_AGENT, _base_opts, friendly_error

# ---------------------------------------------------------------------------
# 涓€銆佸瓧骞曟姄鍙栦笌瑙ｆ瀽
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")  # 鍘婚櫎 <00:00:00.500><c> 涔嬬被鐨勫唴鑱旀爣绛?
_CUE_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})"
)


def _ts_to_seconds(h: str, m: str, s: str, ms: str = "0") -> int:
    return int(h) * 3600 + int(m) * 60 + int(s)


def _seconds_to_str(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _seconds_to_srt_ts(sec: int) -> str:
    sec = max(0, int(sec or 0))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d},000"


def _safe_download_title(title: Optional[str]) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(title or "video-transcript")).strip()
    return cleaned[:80] or "video-transcript"


def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    """Convert transcript segments to a browser-downloadable SRT document."""
    cues: List[str] = []
    for idx, seg in enumerate(segments or [], start=1):
        text = re.sub(r"\s+", " ", str(seg.get("text") or "")).strip()
        if not text:
            continue
        start = int(seg.get("start") or 0)
        next_seg = segments[idx] if idx < len(segments) else None
        end = int((next_seg or {}).get("start") or start + 3)
        if end <= start:
            end = start + 3
        cues.append(
            f"{len(cues) + 1}\n"
            f"{_seconds_to_srt_ts(start)} --> {_seconds_to_srt_ts(end)}\n"
            f"{text}\n"
        )
    return "\n".join(cues)


def _pick_subtitle_lang(info: Dict[str, Any]) -> Optional[str]:
    """Pick the best subtitle language from yt-dlp metadata."""
    manual = set((info.get("subtitles") or {}).keys())
    auto = set((info.get("automatic_captions") or {}).keys())

    for pref in config.SUBTITLE_LANG_PRIORITY:
        if pref in manual:
            return pref
    for pref in config.SUBTITLE_LANG_PRIORITY:
        if pref in auto:
            return pref
    # 鍏滃簳锛氫汉宸ュ瓧骞曠殑浠绘剰涓€涓紝鍏舵鑷姩瀛楀箷浠绘剰涓€涓?
    if manual:
        return sorted(manual)[0]
    if auto:
        return sorted(auto)[0]
    return None


def _parse_vtt(text: str) -> List[Dict[str, Any]]:
    """Parse VTT/SRT text into timestamped transcript segments."""
    segments: List[Dict[str, Any]] = []
    last_text = ""
    lines = text.replace("\r\n", "\n").split("\n")
    i = 0
    cur_start: Optional[int] = None
    buf: List[str] = []

    def flush() -> None:
        nonlocal buf, cur_start, last_text
        if cur_start is None:
            buf = []
            return
        joined = " ".join(b.strip() for b in buf if b.strip()).strip()
        joined = _TAG_RE.sub("", joined).strip()
        buf = []
        if not joined or joined == last_text:
            return
        # 鍘绘帀涓庝笂涓€鏉￠珮搴﹂噸鍙犵殑婊氬姩瀛楀箷锛堣嚜鍔ㄥ瓧骞曞父瑙侊級
        if last_text and (joined in last_text or last_text in joined):
            # 鐢ㄦ洿闀跨殑涓€鏉¤鐩?
            if len(joined) > len(last_text) and segments:
                segments[-1]["text"] = joined
                last_text = joined
            return
        segments.append({"start": cur_start, "start_str": _seconds_to_str(cur_start), "text": joined})
        last_text = joined

    while i < len(lines):
        line = lines[i]
        m = _CUE_TIME_RE.search(line)
        if m:
            flush()
            cur_start = _ts_to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
            buf = []
        elif line.strip() == "" and buf:
            flush()
            cur_start = None
        elif cur_start is not None and not line.startswith("WEBVTT") and "-->" not in line:
            # 璺宠繃绾暟瀛楃殑 SRT 搴忓彿
            if not line.strip().isdigit():
                buf.append(line)
        i += 1
    flush()
    return segments


def fetch_transcript(url: str, on_stage=None) -> Dict[str, Any]:
    """Fetch transcript text, preferring subtitles and falling back to ASR."""
    def stage(msg: str) -> None:
        if on_stage:
            on_stage(msg)

    opts = _base_opts(url)
    opts["skip_download"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        bili_subtitle = _download_bilibili_player_subtitles(url)
        if bili_subtitle:
            bili_lang, segments = bili_subtitle
            if segments:
                return {
                    "source": "subtitle",
                    "lang": bili_lang,
                    "segments": segments,
                    "title": None,
                    "duration": None,
                    "webpage_url": url,
                    "thumbnail": None,
                }
        raise
    if info.get("_type") == "playlist" and info.get("entries"):
        entries = [e for e in info["entries"] if e]
        info = entries[0] if entries else info

    meta = {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url") or url,
        "thumbnail": info.get("thumbnail"),
    }

    lang = _pick_subtitle_lang(info)
    if lang:
        segments = _download_and_parse_subtitle(url, lang)
        if segments:
            return {"source": "subtitle", "lang": lang, "segments": segments, **meta}
        # 瀛楀箷澹版槑浜嗚瑷€浣嗗疄闄呮嬁涓嶅埌 鈫?缁х画璧?ASR 鍏滃簳

    bili_subtitle = _download_bilibili_player_subtitles(url)
    if bili_subtitle:
        bili_lang, segments = bili_subtitle
        if segments:
            return {"source": "subtitle", "lang": bili_lang, "segments": segments, **meta}

    # No usable subtitles: try ASR fallback.
    if config.ENABLE_ASR:
        stage("无字幕，正在下载音频...")
        try:
            segments = _asr_transcribe(url, stage)
        except Exception as exc:  # noqa: BLE001
            raise _friendly_asr_error(exc, info) from exc
        if segments:
            return {"source": "asr", "lang": "asr", "segments": segments, **meta}

    # 璧板埌杩欓噷璇存槑鏃㈡棤瀛楀箷涔熸棤娉?ASR
    extractor = (info.get("extractor_key") or info.get("extractor") or "").lower()
    if not config.ENABLE_ASR:
        if "bili" in extractor and not get_cookies_file():
            raise ValueError(
                "未获取到该 B 站视频的可用字幕。B 站 CC/AI 字幕可能需要登录 Cookie："
                "可把 cookies.txt 放到 backend/cookies.txt；或开启语音转写（ENABLE_ASR=1）后重试。"
            )
        raise ValueError("该视频没有可用字幕。可开启语音转写（ENABLE_ASR=1）后再试。")
    raise ValueError("无法获取该视频的文本（字幕与语音转写均失败），请稍后重试或更换视频。")


def _download_and_parse_subtitle(url: str, lang: str) -> List[Dict[str, Any]]:
    """Download and parse one subtitle language into transcript segments."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        dl_opts = _base_opts(url)
        dl_opts.update(
            {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [lang],
                "subtitlesformat": "vtt",
                "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
            }
        )
        try:
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                ydl.download([url])
        except Exception:
            return []
        vtt_files = sorted(tmp_dir.glob("*.vtt")) or sorted(tmp_dir.glob("*.srt"))
        if not vtt_files:
            return []
        raw = vtt_files[0].read_text(encoding="utf-8", errors="ignore")
    return _parse_vtt(raw)


def _extract_bilibili_bvid(url: str) -> Optional[str]:
    match = re.search(r"/video/(BV[a-zA-Z0-9]+)", url)
    return match.group(1) if match else None


def _parse_bilibili_json_subtitle(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments: List[Dict[str, Any]] = []
    for item in data.get("body", []) or []:
        text = str(item.get("content") or "").strip()
        if not text:
            continue
        start = int(float(item.get("from") or 0))
        segments.append({"start": start, "start_str": _seconds_to_str(start), "text": text})
    return segments


def _bilibili_opener():
    cookies = get_cookies_file()
    if not cookies:
        return urllib.request.build_opener()
    jar = MozillaCookieJar()
    jar.load(cookies, ignore_discard=True, ignore_expires=True)
    return build_opener(HTTPCookieProcessor(jar))


def _bilibili_get_json(url: str, referer: str) -> Dict[str, Any]:
    headers = {
        "User-Agent": _USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": referer,
        "Origin": "https://www.bilibili.com",
    }
    req = urllib.request.Request(url, headers=headers)
    with _bilibili_opener().open(req, timeout=20) as resp:
        return json.load(resp)


def _pick_bilibili_subtitle(subtitles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    available = [s for s in subtitles if s.get("subtitle_url")]
    if not available:
        return None
    priority = config.SUBTITLE_LANG_PRIORITY + ["ai-zh", "ai-zh-Hans", "ai-en"]
    by_lang = {s.get("lan"): s for s in available}
    for lang in priority:
        if lang in by_lang:
            return by_lang[lang]
    return available[0]


def _download_bilibili_player_subtitles(url: str) -> Optional[tuple[str, List[Dict[str, Any]]]]:
    bvid = _extract_bilibili_bvid(url)
    if not bvid:
        return None
    referer = f"https://www.bilibili.com/video/{bvid}"
    try:
        view = _bilibili_get_json(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            referer,
        )
        data = view.get("data") or {}
        aid = data.get("aid")
        cid = data.get("cid")
        if not aid or not cid:
            return None
        player = _bilibili_get_json(
            f"https://api.bilibili.com/x/player/wbi/v2?aid={aid}&cid={cid}",
            referer,
        )
        subtitles = ((player.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        picked = _pick_bilibili_subtitle(subtitles)
        if not picked:
            return None
        sub_url = picked.get("subtitle_url") or ""
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
        elif urlparse(sub_url).scheme == "":
            sub_url = "https://www.bilibili.com" + sub_url
        subtitle_json = _bilibili_get_json(sub_url, referer)
        segments = _parse_bilibili_json_subtitle(subtitle_json)
        return str(picked.get("lan") or "bilibili"), segments
    except Exception:
        return None


# ---- ASR fallback (faster-whisper) ----
_whisper_model = None
_whisper_lock = threading.Lock()


def _get_whisper():
    """Lazy-load and reuse the Whisper model."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    with _whisper_lock:
        if _whisper_model is not None:
            return _whisper_model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # noqa: BLE001
            raise ValueError(
                "未安装语音转写依赖。请在后端虚拟环境执行：pip install faster-whisper"
            ) from exc
        _whisper_model = WhisperModel(
            config.WHISPER_MODEL,
            device=config.WHISPER_DEVICE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
        )
        return _whisper_model


def _download_audio(url: str, tmp_dir: Path) -> Optional[Path]:
    opts = _base_opts(url)
    opts.update({
        "format": "bestaudio/best",
        "outtmpl": str(tmp_dir / "%(id)s.%(ext)s"),
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    files = sorted([p for p in tmp_dir.iterdir() if p.is_file()],
                   key=lambda p: p.stat().st_size, reverse=True)
    return files[0] if files else None


def _asr_transcribe(url: str, stage) -> List[Dict[str, Any]]:
    """Download audio and transcribe it into timestamped segments."""
    model = _get_whisper()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        audio = _download_audio(url, tmp_dir)
        if not audio:
            return []
        stage("正在语音转写（首次可能需要下载模型，请耐心等待）...")
        segments_iter, _info = model.transcribe(
            str(audio), language=None, vad_filter=True, beam_size=1
        )
        segments: List[Dict[str, Any]] = []
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if not text:
                continue
            start = int(seg.start or 0)
            segments.append({"start": start, "start_str": _seconds_to_str(start), "text": text})
    return segments


def _friendly_asr_error(exc: Exception, info: Dict[str, Any]) -> ValueError:
    """Translate ASR dependency/model errors into actionable messages."""
    if isinstance(exc, ValueError):
        return exc

    msg = str(exc)
    low = msg.lower()
    extractor = (info.get("extractor_key") or info.get("extractor") or "").lower()

    if any(token in low for token in ("hugging face", "huggingface", "local cache", "on the hub", "hf_hub")):
        if "bili" in extractor and not get_cookies_file():
            return ValueError(
                "未获取到该 B 站视频的可用字幕；同时语音转写需要先下载 Whisper 模型，"
                "但当前无法从 Hugging Face 拉取模型文件。可先放置 cookies.txt 读取字幕，"
                "或预先缓存 Whisper 模型后再试。"
            )
        return ValueError(
            "语音转写需要先下载 Whisper 模型，但当前无法从 Hugging Face 拉取模型文件。"
            "请检查网络，或预先缓存 Whisper 模型后再试。"
        )

    if "timed out" in low or "timeout" in low:
        return ValueError("语音转写初始化超时，请稍后重试。")
    return ValueError(f"语音转写失败：{msg}")


def _segments_to_text(segments: List[Dict[str, Any]], max_chars: int = 30000) -> str:
    """Join timestamped transcript segments for LLM input."""
    lines = [f"[{s['start_str']}] {s['text']}" for s in segments]
    full = "\n".join(lines)
    if len(full) <= max_chars:
        return full
    # 瓒呴暱锛氭寜姣斾緥鎶芥牱锛屼繚鐣欐椂闂存埑鍒嗗竷
    step = len(lines) / (max_chars / (len(full) / len(lines)))
    step = max(1, int(step))
    sampled = lines[::step]
    return "\n".join(sampled)[:max_chars]


# ---------------------------------------------------------------------------
# 浜屻€丏eepSeek 璋冪敤
# ---------------------------------------------------------------------------

def _client():
    if not config.DEEPSEEK_API_KEY:
        raise ValueError(
            "未配置 AI 密钥。请在 backend/.env 中设置 DEEPSEEK_API_KEY=你的密钥，或设置同名环境变量后重启后端。"
        )
    try:
        from openai import OpenAI
    except ImportError as exc:  # noqa: BLE001
        raise ValueError("缺少 openai 依赖，请在后端虚拟环境执行：pip install openai") from exc
    return OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)


_SUMMARY_SYSTEM = (
    "你是有洞察力的视频内容分析师和学习笔记作者。用户会给你一段带时间戳的视频字幕，格式为 [时间] 文本。"
    "请基于字幕内容，输出一份有深度、有趣、适合复盘的结构化中文解读，帮助用户看懂表层信息背后的观点、隐藏逻辑、适用边界和行动启发。"
    "必须严格返回 JSON 对象，不要输出多余文字。JSON 结构如下：\n"
    "{\n"
    '  "overview": "用 5-7 句话写成一段完整解读，说明视频主题、核心矛盾、关键结论、为什么值得看、适合谁参考；可以有 1-2 处 **重点加粗**",\n'
    '  "key_points": ["💡洞察：用一句话点出核心观点，并补充原因、字幕依据、隐藏逻辑、反直觉启发、适用边界或行动建议；至少包含一处 **重点加粗**"],\n'
    '  "outline": [{"time": "12:34", "title": "🎯章节标题：点出这一段的真正作用", "points": ["🔍证据：用 2-3 句话细致解释，包括发生了什么、为什么重要、字幕依据/例子、影响或可执行建议，并用 **重点加粗** 标出关键判断"]}],\n'
    '  "mindmap_markdown": "# 🧠 视频主题\\n## 💡 核心洞察\\n- 子要点"\n'
    "}\n"
    "要求："
    "1. 内容忠于字幕，不准编造字幕没有的信息；"
    "2. 如果需要推断，只能写“从字幕看...”或“可以理解为...”，不要把推断写成事实；"
    "3. overview 不要太短，避免只写一句泛泛而谈的结论，要有问题意识和阅读价值；"
    "4. key_points 输出 6-10 条，按重要性排序；每条必须以 💡洞察、🎯重点、⚠️边界、✅建议、🔍证据 之一开头，且至少包含一处 **重点加粗**；"
    "5. key_points 不能只是复述字幕，要尽量写出隐藏逻辑、反直觉之处、适用条件、风险、例子或行动建议；"
    "6. outline 输出 4-8 个章节，每个章节必须包含 2-4 条 points，形成适合阅读的层级大纲；章节标题可以少量使用图标，但不要堆砌；"
    "7. 每条 points 都必须是细致解释，不能只写短标题或关键词；应包含“发生了什么 + 为什么重要 + 字幕中的依据/例子/建议”中的至少两类信息；"
    "8. outline.time 必须来自字幕中真实存在的时间点；"
    "9. 语言清晰、有洞察、有一点趣味，但不要油腻、夸张或营销腔。"
)

_FAST_SUMMARY_SYSTEM = (
    "你是视频内容快速解读助手。用户会给你带时间戳的视频字幕。"
    "请优先速度，但不要只做平淡复述；快速抓住主题、核心矛盾和最值得看的点。"
    "请优先速度，严格返回 JSON 对象，不要输出多余文字。JSON 结构如下：\n"
    "{\n"
    '  "overview": "用 2-3 句话快速概括视频主题、核心价值和一个有趣的关键洞察；可以包含一处 **重点加粗**",\n'
    '  "outline": [{"time": "12:34", "title": "🎯章节标题：这一段的主要作用"}]\n'
    "}\n"
    "要求：outline 输出 4-8 个章节标题即可，不要写 points，不要写思维导图；章节标题可以少量使用 💡/🎯/⚠️/✅/🔍 等语义图标，但每个标题最多一个；"
    "outline.time 必须来自字幕中真实存在的时间点；内容忠于字幕，不准编造。"
    "如果需要推断，只能写“从字幕看...”或“可以理解为...”。"
)

_DETAIL_SUMMARY_SYSTEM = (
    "你是有洞察力的视频内容分析师和学习笔记作者。用户会给你视频字幕和第一阶段快速摘要。"
    "请在快速摘要基础上补全有深度、有趣、适合复盘的详细解释和思维导图；重点写出观点背后的隐藏逻辑、反直觉启发、适用边界和行动建议。"
    "严格返回 JSON 对象，不要输出多余文字。JSON 结构如下：\n"
    "{\n"
    '  "overview": "保留快速摘要的主线，并扩写为 5-7 句话的完整解读；说明主题、核心矛盾、关键结论、为什么重要、适合谁参考；可以有 1-2 处 **重点加粗**",\n'
    '  "key_points": ["💡洞察：包含解释、原因、字幕依据、隐藏逻辑、反直觉启发、适用边界或行动建议；至少包含一处 **重点加粗**"],\n'
    '  "outline": [{"time": "12:34", "title": "🎯章节标题：这一段的真正作用", "points": ["🔍证据：用 2-3 句话细致解释该点，写清发生了什么、为什么重要、字幕依据/例子/建议，并用 **重点加粗** 标出关键判断"]}],\n'
    '  "mindmap_markdown": "# 🧠 视频主题\\n## 💡 核心洞察\\n- 子要点"\n'
    "}\n"
    "要求："
    "1. outline 尽量沿用第一阶段的章节；每个章节必须包含 2-4 条 points；"
    "2. 每条 points 都要解释说明，不能只写短标题或关键词；"
    "3. key_points 输出 6-10 条，每条必须以 💡洞察、🎯重点、⚠️边界、✅建议、🔍证据 之一开头，且至少包含一处 **重点加粗**；"
    "4. 图标用于区分语义，不要每句话都加图标；"
    "5. 内容忠于字幕，不准编造字幕没有的信息；"
    "6. 如果需要推断，只能写“从字幕看...”或“可以理解为...”，不要把推断写成事实；"
    "7. 语言要有深度、有趣、清晰，但不要油腻、夸张或营销腔。"
)

def _normalize_summary_json(content: str) -> Dict[str, Any]:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last >= first:
        text = text[first:last + 1]
    return json.loads(text or "{}")


def _summary_partial_text(content: str) -> str:
    """Best-effort readable preview while JSON summary is still streaming."""
    try:
        data = _normalize_summary_json(content)
    except Exception:
        text = content or ""
        lines: List[str] = []
        overview_match = re.search(r'"overview"\s*:\s*"([^"]*)', text, flags=re.S)
        if overview_match and overview_match.group(1).strip():
            lines.extend(["## 概要", overview_match.group(1).strip()])

        points_match = re.search(r'"key_points"\s*:\s*\[(.*)', text, flags=re.S)
        points: List[str] = []
        if points_match:
            points = [p.strip() for p in re.findall(r'"([^"]+)"', points_match.group(1)) if p.strip()]
        if points:
            lines.append("")
            lines.append("## 核心要点")
            lines.extend(f"- {point}" for point in points)

        if lines:
            return "\n".join(lines)[:1200]
        cleaned = re.sub(r'[{},"\[\]]+', " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:1200]

    lines: List[str] = []
    overview = str(data.get("overview") or "").strip()
    if overview:
        lines.extend(["## 概要", overview])

    key_points = [str(x).strip() for x in (data.get("key_points") or []) if str(x).strip()]
    if key_points:
        lines.append("")
        lines.append("## 核心要点")
        lines.extend(f"- {point}" for point in key_points)

    return "\n".join(lines).strip()


def _stream_summary_json(system_prompt: str, user_msg: str, on_delta=None) -> Dict[str, Any]:
    client = _client()
    stream = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        stream=True,
    )
    chunks: List[str] = []
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content or ""
        except Exception:
            delta = ""
        if not delta:
            continue
        chunks.append(delta)
        if on_delta:
            preview = _summary_partial_text("".join(chunks))
            if preview:
                on_delta(preview)
    return _normalize_summary_json("".join(chunks))


def _normalize_outline_items(
    items: List[Dict[str, Any]],
    transcript_text: str,
    overview: Any = "",
    key_points: Optional[List[str]] = None,
    require_points: bool = True,
) -> List[Dict[str, Any]]:
    outline = []
    points_source = key_points or []
    for index, item in enumerate(items or []):
        t = str(item.get("time", "")).strip()
        points = [str(p).strip() for p in (item.get("points") or []) if str(p).strip()]
        section_title = str(item.get("title", "")).strip()
        if require_points and not points:
            points = [_build_outline_explanation(section_title, index, transcript_text, overview, points_source)]
        outline.append({
            "time": t,
            "seconds": _time_str_to_seconds(t),
            "title": section_title,
            "points": points,
        })
    return outline


def summarize_fast(transcript_text: str, title: Optional[str], on_delta=None) -> Dict[str, Any]:
    user_msg = f"视频标题：{title or '未知'}\n\n字幕如下：\n{transcript_text}"
    data = _stream_summary_json(_FAST_SUMMARY_SYSTEM, user_msg, on_delta=on_delta)
    data.setdefault("overview", "")
    data["key_points"] = []
    data["outline"] = _normalize_outline_items(data.get("outline", []) or [], transcript_text, data.get("overview", ""), [], require_points=False)
    data["mindmap_markdown"] = ""
    return data


def enrich_summary(transcript_text: str, title: Optional[str], fast_result: Dict[str, Any], on_delta=None) -> Dict[str, Any]:
    user_msg = (
        f"视频标题：{title or '未知'}\n\n"
        f"第一阶段快速摘要：\n{json.dumps(fast_result, ensure_ascii=False)}\n\n"
        f"字幕如下：\n{transcript_text}"
    )
    data = _stream_summary_json(_DETAIL_SUMMARY_SYSTEM, user_msg, on_delta=on_delta)
    data.setdefault("overview", fast_result.get("overview", ""))
    key_points = [str(x).strip() for x in (data.get("key_points") or []) if str(x).strip()]
    data["key_points"] = key_points
    outline_items = data.get("outline") or fast_result.get("outline") or []
    data["outline"] = _normalize_outline_items(outline_items, transcript_text, data.get("overview", ""), key_points, require_points=True)
    data.setdefault("mindmap_markdown", "")
    return data


def summarize(transcript_text: str, title: Optional[str], on_delta=None) -> Dict[str, Any]:
    user_msg = f"视频标题：{title or '未知'}\n\n字幕如下：\n{transcript_text}"
    data = _stream_summary_json(_SUMMARY_SYSTEM, user_msg, on_delta=on_delta)

    # 瑙勮寖鍖?outline锛氳ˉ seconds 瀛楁锛屼究浜庡墠绔?鐐瑰嚮璺宠浆"
    key_points = [str(x).strip() for x in (data.get("key_points") or []) if str(x).strip()]
    data["outline"] = _normalize_outline_items(data.get("outline", []) or [], transcript_text, data.get("overview", ""), key_points, require_points=True)
    data.setdefault("overview", "")
    data.setdefault("key_points", [])
    data.setdefault("mindmap_markdown", "")
    return data


def _build_outline_explanation(
    title: str,
    index: int,
    transcript_text: str,
    overview: Any,
    key_points: List[str],
) -> str:
    """Guarantee the API returns readable explanation text for every outline item."""
    clean_title = title or "该章节"
    source = key_points[index % len(key_points)] if key_points else str(overview or "").strip()
    if not source:
        source = _transcript_excerpt(transcript_text)
    source = source or "从字幕看，这一段承担了补充背景、推进论证或给出结论的作用。"
    return (
        f"💡洞察：**{clean_title}** 这一段不只是目录里的一个标题，更像是视频论证链条中的一个转折或支点。"
        f"{source} 因此阅读时要抓住它回答了什么问题、为什么值得单独拎出来，以及这个判断在现实场景中可以如何被理解或应用。"
    )


def _transcript_excerpt(transcript_text: str, max_chars: int = 90) -> str:
    text = re.sub(r"\[[^\]]+\]", "", transcript_text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _time_str_to_seconds(t: str) -> int:
    parts = [p for p in re.split(r"[:：]", t.strip()) if p != ""]
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 1:
        return nums[0]
    return 0


def chat_over_transcript(
    transcript_text: str,
    title: Optional[str],
    history: List[Dict[str, str]],
    question: str,
) -> str:
    client = _client()
    system = (
        "你是视频内容问答助手。下面是某个视频的字幕（带时间戳）。"
        "请只依据字幕内容回答用户问题，用中文简洁作答；如果字幕中没有相关信息，请如实说明。\n\n"
        f"视频标题：{title or '未知'}\n字幕：\n{transcript_text}"
    )
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    for h in history[-6:]:
        role = h.get("role")
        content = h.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": question})
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=messages,
        temperature=0.4,
        stream=False,
    )
    return resp.choices[0].message.content or ""


_LANG_NAMES = {
    "zh": "中文", "en": "英语", "ja": "日语", "ko": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "ru": "俄语",
}


def translate_summary(summary: Dict[str, Any], target: str) -> Dict[str, Any]:
    """Translate summary fields to the target language."""
    client = _client()
    target_name = _LANG_NAMES.get(target, target)
    payload = {
        "overview": summary.get("overview", ""),
        "key_points": summary.get("key_points", []),
        "outline": [
            {
                "title": o.get("title", ""),
                "points": o.get("points", []) or [],
            }
            for o in summary.get("outline", [])
        ],
        "mindmap_markdown": summary.get("mindmap_markdown", ""),
    }
    system = (
        f"你是专业翻译。把用户给的 JSON 各字段文本翻译成{target_name}，保持 JSON 结构与数组长度不变，"
        "只翻译文本值，不要翻译 JSON 的键，不要添加解释。直接返回翻译后的 JSON 对象。"
    )
    resp = client.chat.completions.create(
        model=config.DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        stream=False,
    )
    data = json.loads(resp.choices[0].message.content or "{}")
    translated_outline = data.get("outline", []) or []
    new_outline = []
    for idx, o in enumerate(summary.get("outline", [])):
        translated_item = translated_outline[idx] if idx < len(translated_outline) and isinstance(translated_outline[idx], dict) else {}
        new_outline.append({
            "time": o.get("time", ""),
            "seconds": o.get("seconds", 0),
            "title": translated_item.get("title") or o.get("title", ""),
            "points": translated_item.get("points") or o.get("points", []) or [],
        })
    return {
        "overview": data.get("overview", summary.get("overview", "")),
        "key_points": data.get("key_points", summary.get("key_points", [])),
        "outline": new_outline,
        "mindmap_markdown": data.get("mindmap_markdown", summary.get("mindmap_markdown", "")),
    }


# ---------------------------------------------------------------------------
# Async AI summary task manager
# ---------------------------------------------------------------------------
class AISummaryManager:
    def __init__(self) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def _set(self, task_id: str, **kwargs: Any) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return None
            public = {k: v for k, v in t.items() if k not in ("_segments", "_transcript_text")}
            if t.get("_segments"):
                public["segments"] = t.get("_segments")
            return public

    def _get_internal(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            t = self._tasks.get(task_id)
            return dict(t) if t else None

    def create_task(self, url: str) -> str:
        task_id = uuid.uuid4().hex
        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "url": url,
                "status": "queued",  # queued -> fetching -> summarizing -> enriching -> completed/error
                "stage": "排队中...",
                "error": None,
                "title": None,
                "lang": None,
                "source": None,
                "webpage_url": url,
                "result": None,
                "partial": "",
                "created_at": time.time(),
            }
        threading.Thread(target=self._run, args=(task_id, url), daemon=True).start()
        return task_id

    def _run(self, task_id: str, url: str) -> None:
        try:
            self._set(task_id, status="fetching", stage="正在获取字幕...")

            def on_stage(msg: str) -> None:
                self._set(task_id, stage=msg)

            data = fetch_transcript(url, on_stage=on_stage)
            transcript_text = _segments_to_text(data["segments"])
            self._set(
                task_id,
                status="summarizing",
                stage="AI 正在总结...",
                title=data.get("title"),
                lang=data.get("lang"),
                source=data.get("source"),
                webpage_url=data.get("webpage_url"),
                _segments=data["segments"],
                _transcript_text=transcript_text,
            )
            def on_delta(text: str) -> None:
                self._set(task_id, partial=text)

            fast_result = summarize_fast(transcript_text, data.get("title"), on_delta=on_delta)
            self._set(
                task_id,
                status="enriching",
                stage="正在补充详细解释和思维导图...",
                result=fast_result,
                partial="",
            )
            result = enrich_summary(transcript_text, data.get("title"), fast_result, on_delta=on_delta)
            self._set(task_id, status="completed", stage="完成", result=result, partial="")
        except Exception as exc:  # noqa: BLE001
            self._set(task_id, status="error", stage="出错", error=_ai_friendly_error(exc))

    def get_context(self, content_key: str) -> Optional[Dict[str, Any]]:
        """Return context for chat and translation reuse."""
        t = self._get_internal(content_key)
        if not t or t.get("status") != "completed":
            return None
        return {
            "transcript_text": t.get("_transcript_text", ""),
            "title": t.get("title"),
            "result": t.get("result"),
        }

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [tid for tid, t in self._tasks.items()
                       if now - t["created_at"] > config.AI_TASK_TTL_SECONDS]
            for tid in expired:
                self._tasks.pop(tid, None)

    def get_transcript_download(self, task_id: str) -> Optional[Dict[str, str]]:
        """Return sanitized title and SRT content once transcript segments are available."""
        t = self._get_internal(task_id)
        if not t or t.get("status") in ("queued", "fetching", "error"):
            return None
        segments = t.get("_segments") or []
        if not segments:
            return None
        return {
            "title": _safe_download_title(t.get("title")),
            "content": segments_to_srt(segments),
        }


def _ai_friendly_error(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return str(exc)
    msg = str(exc)
    low = msg.lower()
    if "api key" in low or "401" in low or "unauthorized" in low:
        return "AI 密钥无效或未授权，请检查 DEEPSEEK_API_KEY 是否正确。"
    if "rate limit" in low or "429" in low:
        return "AI 接口调用过于频繁（限流），请稍后重试。"
    if "insufficient" in low or "balance" in low or "quota" in low:
        return "AI 账户余额不足，请充值后重试。"
    if "timeout" in low or "timed out" in low:
        return "AI 接口请求超时，请稍后重试。"
    return friendly_error(exc)

ai_manager = AISummaryManager()







