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
        "opencv-python-headless>=4.10.0",
        "uvicorn==0.38.0",
        "yt-dlp==2026.6.9",
    )
    .env(
        {
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


@app.function(
    gpu="L4",
    timeout=60 * MINUTES,
    memory=16384,
    scaledown_window=5 * MINUTES,
)
@modal.asgi_app(requires_proxy_auth=True)
def web():
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import Response
    from pydantic import BaseModel, Field

    os.chdir("/app")

    from clipper import (
        CaptionStyle,
        ClipCandidate,
        export_clip,
        transcribe,
    )

    api = FastAPI(title="ClipForge GPU", version="0.1.0")

    class TranscribeRequest(BaseModel):
        audio_b64: str
        model: str = "Systran/faster-whisper-small"
        language: str = "id"

    class EncodeRequest(BaseModel):
        video_b64: str
        clip: dict
        options: dict = Field(default_factory=dict)

    class JobRequest(BaseModel):
        request: dict
        source_b64: str | None = None
        source_name: str = "upload.mp4"

    @api.get("/health")
    def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "gpu": True,
            "whisper_device": os.environ.get("CLIPFORGE_WHISPER_DEVICE", "cuda"),
            "video_encoder": os.environ.get("CLIPFORGE_VIDEO_ENCODER", "h264_nvenc"),
        }

    @api.post("/transcribe")
    def transcribe_endpoint(payload: TranscribeRequest) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            audio_path = _write_b64(work / "audio.wav", payload.audio_b64)
            transcript_path = work / "transcript.json"
            segments = transcribe(audio_path, transcript_path, payload.model, payload.language, force=True)
            return {
                "segments": [
                    {"start": item.start, "end": item.end, "text": item.text}
                    for item in segments
                ]
            }

    @api.post("/encode")
    def encode_endpoint(payload: EncodeRequest) -> Response:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            video_path = _write_b64(work / "source.mp4", payload.video_b64)
            clip = ClipCandidate(
                index=int(payload.clip.get("index") or 1),
                start=float(payload.clip["start"]),
                end=float(payload.clip["end"]),
                duration=float(payload.clip.get("duration") or (float(payload.clip["end"]) - float(payload.clip["start"]))),
                score=int(payload.clip.get("score") or 0),
                title=str(payload.clip.get("title") or "clip"),
                reason=str(payload.clip.get("reason") or ""),
                text=str(payload.clip.get("text") or ""),
            )
            options = payload.options
            caption = CaptionStyle(
                font_size=int(options.get("caption_font_size") or 30),
                position=options.get("caption_position") or "center",
                color=options.get("caption_color") or "#FFFFFF",
                font_family=options.get("caption_font") or "DejaVu Sans",
                outline_width=float(options.get("caption_outline") or 2),
                outline_color=options.get("caption_outline_color") or "#000000",
            )
            out = export_clip(
                video_path,
                clip,
                [],
                work / "clips",
                bool(options.get("burn_subtitles", True)),
                options.get("crop_mode") or "center",
                caption,
                None,
                options.get("cam_corner") or "auto",
                options.get("required_hashtags") or [],
            )
            return Response(content=out.read_bytes(), media_type="video/mp4")

    @api.post("/jobs")
    def jobs_endpoint(payload: JobRequest) -> Response:
        import clipper as clipper_mod

        request = payload.request
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

            if payload.source_b64:
                source_path = work_root / payload.source_name
                _write_b64(source_path, payload.source_b64)
                argv.extend(["--source-file", str(source_path)])
            elif request.get("url"):
                argv.insert(1, request["url"])
            else:
                raise HTTPException(status_code=400, detail="Provide a YouTube URL or uploaded video")

            import sys

            old_argv = sys.argv
            try:
                sys.argv = argv
                code = clipper_mod.main()
            finally:
                sys.argv = old_argv
            if code != 0:
                raise HTTPException(status_code=500, detail=f"clipper.py exited with code {code}")
            return Response(content=_zip_directory(work_root), media_type="application/zip")

    return api
