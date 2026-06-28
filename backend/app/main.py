"""FastAPI 入口：解析 / 下载 / 进度 / 取文件 等接口 + 托管前端。"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import DOWNLOAD_DIR, FRONTEND_DIST
from .downloader import friendly_error, manager, parse_video
from .ai import ai_manager, chat_over_transcript, translate_summary

app = FastAPI(title="万能视频下载器 API", version="1.0.0")

AUTH_USERNAME = os.getenv("AUTH_USERNAME", "player")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "295056")
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "0").strip().lower() in ("1", "true", "yes")
SESSION_COOKIE = "session"
_sessions: set[str] = set()

# 开发期前端跑在 5173，放开跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"
    audio_only: bool = False
    subtitle_lang: Optional[str] = None


class AISummaryRequest(BaseModel):
    url: str


class AIChatRequest(BaseModel):
    content_key: str
    question: str
    history: list[dict] = []


class AITranslateRequest(BaseModel):
    content_key: str
    target: str = "en"


class LoginRequest(BaseModel):
    username: str
    password: str


def _is_public_path(path: str) -> bool:
    return path in {"/api/health", "/api/auth/login"} or not path.startswith("/api/")


def _current_user(request: Request) -> Optional[str]:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id and session_id in _sessions:
        return AUTH_USERNAME
    return None


@app.middleware("http")
async def require_login(request: Request, call_next):
    if not _is_public_path(request.url.path) and not _current_user(request):
        return Response(
            content='{"detail":"请先登录"}',
            status_code=401,
            media_type="application/json; charset=utf-8",
        )
    return await call_next(request)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/login")
def api_login(req: LoginRequest) -> Response:
    if req.username != AUTH_USERNAME or req.password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="账号或密码错误")

    session_id = secrets.token_urlsafe(32)
    _sessions.add(session_id)
    response = Response(
        content='{"username":"player"}',
        media_type="application/json; charset=utf-8",
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@app.get("/api/auth/me")
def api_me(request: Request) -> dict:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return {"username": user}


@app.post("/api/auth/logout")
def api_logout(request: Request) -> Response:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id:
        _sessions.discard(session_id)
    response = Response(content='{"ok":true}', media_type="application/json; charset=utf-8")
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.post("/api/parse")
def api_parse(req: ParseRequest) -> dict:
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    try:
        return parse_video(url)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"解析失败：{friendly_error(exc)}")


@app.post("/api/download")
def api_download(req: DownloadRequest) -> dict:
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    manager.cleanup_expired()
    task_id = manager.create_task(
        url=url,
        quality=req.quality,
        audio_only=req.audio_only,
        subtitle_lang=req.subtitle_lang,
    )
    return {"task_id": task_id}


@app.get("/api/progress/{task_id}")
def api_progress(task_id: str) -> dict:
    task = manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return task


@app.get("/api/file/{task_id}")
def api_file(task_id: str):
    task = manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    if task["status"] != "completed" or not task.get("filename"):
        raise HTTPException(status_code=409, detail="文件尚未就绪")
    file_path = DOWNLOAD_DIR / task_id / task["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=file_path,
        filename=task["filename"],
        media_type="application/octet-stream",
    )


# ---- AI 视频总结功能（DeepSeek + 字幕）----
@app.post("/api/ai/summary")
def api_ai_summary(req: AISummaryRequest) -> dict:
    """创建 AI 总结任务（异步），返回 task_id；前端轮询 GET 取结果。"""
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="请输入视频链接")
    ai_manager.cleanup_expired()
    task_id = ai_manager.create_task(url=url)
    return {"task_id": task_id}


@app.get("/api/ai/summary/{task_id}")
def api_ai_summary_status(task_id: str) -> dict:
    task = ai_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return task


@app.post("/api/ai/chat")
def api_ai_chat(req: AIChatRequest) -> dict:
    ctx = ai_manager.get_context(req.content_key)
    if not ctx:
        raise HTTPException(status_code=409, detail="总结上下文不存在或已过期，请重新生成总结")
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="请输入你的问题")
    try:
        answer = chat_over_transcript(
            ctx["transcript_text"], ctx["title"], req.history or [], question
        )
        return {"answer": answer}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"AI 回答失败：{friendly_error(exc)}")


@app.post("/api/ai/translate")
def api_ai_translate(req: AITranslateRequest) -> dict:
    ctx = ai_manager.get_context(req.content_key)
    if not ctx or not ctx.get("result"):
        raise HTTPException(status_code=409, detail="总结上下文不存在或已过期，请重新生成总结")
    try:
        translated = translate_summary(ctx["result"], req.target)
        return {"result": translated}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"翻译失败：{friendly_error(exc)}")


@app.get("/api/ai/transcript/{task_id}.srt")
def api_ai_transcript_srt(task_id: str):
    download = ai_manager.get_transcript_download(task_id)
    if not download:
        raise HTTPException(status_code=404, detail="字幕不存在或总结任务尚未完成")
    filename = f"{download['title']}.srt"
    encoded = quote(filename)
    return Response(
        content=download["content"],
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


# ---- 托管前端构建产物（生产环境）----
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:

    @app.get("/")
    def dev_root() -> dict:
        return {
            "message": "后端已启动。前端开发请运行 frontend 下的 npm run dev；"
            "或先 npm run build 生成 dist 后由本服务托管。"
        }
