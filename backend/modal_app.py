"""Modal GPU endpoints for ClipForge transcription, encoding, and full clip jobs.

Deploy from the repo root:

    modal deploy backend/modal_app.py

The web app is served at a `*.modal.run` URL. Point ClipForge at it with
`MODAL_GPU_BASE_URL` and optional proxy-auth headers.
"""

from __future__ import annotations

import base64
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import modal


APP_NAME = "clipforge-gpu"
MINUTES = 60

image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04",
        add_python="3.12",
    )
    .apt_install(
        "ffmpeg",
        "git",
        "libglib2.0-0",
        "libgl1",
        "libgomp1",
        "fontconfig",
        "fonts-dejavu-core",
        "fonts-dejavu",
        "fonts-liberation",
        "fonts-noto-core",
    )
    .pip_install(
        "faster-whisper==1.2.1",
        "fastapi==0.125.0",
        "imageio-ffmpeg==0.6.0",
        "pydantic==2.13.4",
        "python-multipart==0.0.20",
        "python-slugify==8.0.4",
        "rich==15.0.0",
        "opencv-python-headless>=4.10.0,<5",
        "uvicorn==0.38.0",
        "yt-dlp==2026.6.9",
    )
    .env(
        {
            "PYTHONPATH": "/app",
            "CLIPFORGE_COMPUTE": "local",
            "CLIPFORGE_WHISPER_DEVICE": "cuda",
            "CLIPFORGE_WHISPER_COMPUTE_TYPE": "float16",
            "CLIPFORGE_VIDEO_ENCODER": "h264_nvenc",
            "CLIPFORGE_PREFER_SYSTEM_FFMPEG": "1",
            "CLIPFORGE_FFMPEG": "/usr/bin/ffmpeg",
        }
    )
    .add_local_dir(
        str(Path(__file__).resolve().parent),
        remote_path="/app",
        ignore=["**/.venv/**", "**/__pycache__/**", "**/outputs/**", "**/uploads/**", "**/tests/**", "**/*.pyc"],
        copy=True,
    )
)

app = modal.App(APP_NAME, image=image)


def _write_b64(path: Path, payload: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(payload))
    return path


def _zip_directory(root: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in root.rglob("*"):
            if item.is_file():
                archive.write(item, item.relative_to(root).as_posix())
    return buffer.getvalue()


def _prepare_app_root() -> None:
    app_root = "/app"
    os.chdir(app_root)
    if app_root not in sys.path:
        sys.path.insert(0, app_root)


def _run_clip_job(job_payload: dict) -> bytes:
    import clipper as clipper_mod

    _prepare_app_root()

    request = job_payload.get("request") or {}
    source_b64 = job_payload.get("source_b64")
    source_name = str(job_payload.get("source_name") or "upload.mp4")

    with tempfile.TemporaryDirectory() as tmp:
        work_root = Path(tmp) / "outputs"
        work_root.mkdir(parents=True, exist_ok=True)
        argv = [
            "clipper.py",
            "--output",
            str(work_root),
            "--top",
            str(request.get("top") or 3),
            "--min",
            str(request.get("min_duration") or 35),
            "--max",
            str(request.get("max_duration") or 180),
            "--model",
            str(request.get("model") or "Systran/faster-whisper-small"),
            "--language",
            str(request.get("language") or "id"),
            "--crop-mode",
            str(request.get("crop_mode") or "center"),
            "--cam-corner",
            str(request.get("cam_corner") or "auto"),
            "--caption-font-size",
            str(request.get("caption_font_size") or 30),
            "--caption-position",
            str(request.get("caption_position") or "center"),
            "--caption-color",
            str(request.get("caption_color") or "#FFFFFF"),
            "--caption-font",
            str(request.get("caption_font") or "DejaVu Sans"),
            "--caption-outline",
            str(request.get("caption_outline") or 2),
            "--caption-outline-color",
            str(request.get("caption_outline_color") or "#000000"),
        ]
        if request.get("analyze_seconds"):
            argv.extend(["--analyze-seconds", str(request["analyze_seconds"])])
        if not request.get("burn_subtitles", True):
            argv.append("--no-burn-subtitles")
        hashtags = request.get("required_hashtags") or []
        if hashtags:
            argv.extend(["--required-hashtags", ",".join(hashtags)])
        if request.get("ai_enabled"):
            argv.append("--ai-enabled")
            if request.get("ai_base_url"):
                argv.extend(["--ai-base-url", request["ai_base_url"]])
            if request.get("ai_model"):
                argv.extend(["--ai-model", request["ai_model"]])
            if request.get("ai_api_key"):
                argv.extend(["--ai-api-key", request["ai_api_key"]])

        if source_b64:
            source_path = work_root / source_name
            _write_b64(source_path, source_b64)
            argv.extend(["--source-file", str(source_path)])
        elif request.get("url"):
            argv.insert(1, request["url"])
        else:
            raise ValueError("Provide a YouTube URL or uploaded video")

        old_argv = sys.argv
        try:
            sys.argv = argv
            code = clipper_mod.main()
        finally:
            sys.argv = old_argv
        if code != 0:
            raise RuntimeError(f"clipper.py exited with code {code}")
        return _zip_directory(work_root)


@app.function(
    gpu="L4",
    timeout=60 * MINUTES,
    memory=16384,
    scaledown_window=5 * MINUTES,
)
def execute_clip_job(job_payload: dict) -> bytes:
    return _run_clip_job(job_payload)


@app.function(
    timeout=10 * MINUTES,
    memory=1024,
    scaledown_window=5 * MINUTES,
)
@modal.asgi_app(requires_proxy_auth=True)
def web():
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import Response
    from modal.functions import FunctionCall
    from pydantic import BaseModel

    api = FastAPI(title="ClipForge GPU Router", version="0.1.0")

    class JobRequest(BaseModel):
        request: dict
        source_b64: str | None = None
        source_name: str = "upload.mp4"

    @api.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "gpu": False,
            "role": "router",
            "worker": "execute_clip_job",
            "worker_gpu": True,
        }

    @api.post("/jobs")
    async def jobs_start(request: Request) -> dict[str, str]:
        payload = JobRequest.model_validate(await request.json())
        try:
            call = execute_clip_job.spawn(payload.model_dump())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to queue GPU job: {exc}") from exc
        return {"call_id": call.object_id, "status": "running"}

    @api.get("/jobs/{call_id}")
    async def jobs_poll(call_id: str):
        fc = FunctionCall.from_id(call_id)
        try:
            result = await fc.get(timeout=0)
        except TimeoutError:
            return {"call_id": call_id, "status": "running"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return Response(content=result, media_type="application/zip")

    return api
