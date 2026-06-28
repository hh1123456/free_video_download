"""全局配置：路径、ffmpeg 定位、AI(DeepSeek) 配置等。"""
from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（backend 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_dotenv() -> None:
    """轻量加载 backend/.env（不引入额外依赖）。

    仅做最朴素的 KEY=VALUE 解析：忽略空行与 # 注释，支持去除两端引号。
    已存在于环境变量中的键不会被覆盖。
    """
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_load_dotenv()

# 下载文件临时存放目录
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 前端构建产物目录（生产环境由 FastAPI 托管）
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

# 下载任务的最大保留时间（秒），超过后清理
TASK_TTL_SECONDS = int(os.getenv("TASK_TTL_SECONDS", "3600"))

# 可选的 Cookie 文件（Netscape 格式）。某些平台（如 B站 720p/1080p、会员视频、
# 受限内容）需要登录态才能获取更高清晰度。把浏览器导出的 cookies.txt 放到
# backend/cookies.txt，或用环境变量 COOKIES_FILE 指定路径即可自动启用。
def get_cookies_file() -> str | None:
    env_path = os.getenv("COOKIES_FILE")
    if env_path and Path(env_path).exists():
        return env_path
    default = BASE_DIR / "backend" / "cookies.txt"
    return str(default) if default.exists() else None


# ---- AI（DeepSeek，OpenAI 兼容协议）配置 ----
# Key 用环境变量管理（勿硬编码）：可写到 backend/.env 的 DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

# AI 总结任务的内存保留时间（秒）
AI_TASK_TTL_SECONDS = int(os.getenv("AI_TASK_TTL_SECONDS", "7200"))

# ---- 语音转写 ASR（faster-whisper）配置 ----
# 当视频没有可用字幕时，自动下载音频并用本地 Whisper 转写为文本再总结。
# 关闭：设 ENABLE_ASR=0
ENABLE_ASR = os.getenv("ENABLE_ASR", "1").strip().lower() not in ("0", "false", "no")
# 模型大小：tiny / base / small / medium / large-v3（越大越准越慢；默认 small 均衡）
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small").strip()
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu").strip()  # cpu / cuda
# CPU 推荐 int8（省内存更快）；GPU 可用 float16
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip()
# HuggingFace 模型下载源：国内访问官方站常被墙，默认走镜像 hf-mirror.com。
# 如需用官方源或自建镜像，设环境变量 HF_ENDPOINT 覆盖即可。
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 字幕语言优先级：抓取字幕时按此顺序挑选第一个可用的语言
# （中文优先，其次英文；其余按平台返回的第一个兜底）
SUBTITLE_LANG_PRIORITY = [
    "zh-Hans", "zh-CN", "zh", "zh-Hant", "zh-TW", "zh-HK",
    "en", "en-US", "en-GB",
]


# 内置 ffmpeg 二进制存放目录
BIN_DIR = BASE_DIR / "backend" / "bin"


def get_ffmpeg_dir() -> str | None:
    """返回一个包含标准命名 ffmpeg 可执行文件的目录，供 yt-dlp 使用。

    优先使用系统已安装的 ffmpeg；若没有，则回退到 imageio-ffmpeg 自带的二进制，
    实现"免安装、开箱即用"。由于 imageio-ffmpeg 的二进制文件名不标准
    （形如 ffmpeg-win64-vX.X.X.exe），yt-dlp 无法自动识别，因此这里把它
    复制为标准的 ffmpeg(.exe) 放到 BIN_DIR，保证 yt-dlp 能稳定找到。
    """
    # 1) 系统 PATH 中是否已有 ffmpeg
    from shutil import which

    system_ffmpeg = which("ffmpeg")
    if system_ffmpeg:
        return str(Path(system_ffmpeg).parent)

    # 2) 回退到 imageio-ffmpeg 自带二进制，并复制为标准命名
    try:
        import shutil

        import imageio_ffmpeg

        src = Path(imageio_ffmpeg.get_ffmpeg_exe())
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        target_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
        target = BIN_DIR / target_name
        if not target.exists() or target.stat().st_size != src.stat().st_size:
            shutil.copy2(src, target)
            if os.name != "nt":
                target.chmod(0o755)
        return str(BIN_DIR)
    except Exception:
        return None
