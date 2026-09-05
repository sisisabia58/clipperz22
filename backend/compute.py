from __future__ import annotations

import os
import shutil
import subprocess


def modal_configured() -> bool:
    return bool(os.environ.get("MODAL_GPU_BASE_URL") or os.environ.get("MODAL_TOKEN_ID"))


def compute_backend() -> str:
    requested = os.environ.get("CLIPFORGE_COMPUTE", "modal").strip().lower() or "modal"
    if requested == "local":
        return "local"
    if modal_configured():
        return "modal"
    return "local"


def should_dispatch_to_modal() -> bool:
    return compute_backend() == "modal"


def whisper_runtime() -> tuple[str, str]:
    device = os.environ.get("CLIPFORGE_WHISPER_DEVICE", "cpu").strip().lower() or "cpu"
    if device == "cuda":
        compute_type = os.environ.get("CLIPFORGE_WHISPER_COMPUTE_TYPE", "float16")
        return "cuda", compute_type
    compute_type = os.environ.get("CLIPFORGE_WHISPER_COMPUTE_TYPE", "int8")
    return "cpu", compute_type


def ffmpeg_has_encoder(name: str) -> bool:
    ffmpeg = os.environ.get("CLIPFORGE_FFMPEG") or shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return name in (result.stdout or "")


def video_encoder_args(has_nvenc: bool | None = None) -> list[str]:
    requested = os.environ.get("CLIPFORGE_VIDEO_ENCODER", "libx264").strip().lower() or "libx264"
    wants_nvenc = requested in {"h264_nvenc", "auto"}
    nvenc_available = ffmpeg_has_encoder("h264_nvenc") if has_nvenc is None else has_nvenc
    if wants_nvenc and nvenc_available:
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p4",
            "-rc",
            "vbr",
            "-cq",
            "19",
            "-b:v",
            "0",
        ]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
