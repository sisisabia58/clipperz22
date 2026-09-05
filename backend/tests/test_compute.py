from __future__ import annotations

import pytest

from compute import (
    compute_backend,
    modal_configured,
    should_dispatch_to_modal,
    video_encoder_args,
    whisper_runtime,
)


def test_modal_configured_when_base_url_is_set(monkeypatch):
    monkeypatch.setenv("MODAL_GPU_BASE_URL", "https://example.modal.run")
    assert modal_configured() is True


def test_modal_not_configured_without_url_or_token(monkeypatch):
    monkeypatch.delenv("MODAL_GPU_BASE_URL", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    assert modal_configured() is False


def test_defaults_to_modal_when_endpoint_is_configured(monkeypatch):
    monkeypatch.setenv("MODAL_GPU_BASE_URL", "https://example.modal.run")
    monkeypatch.delenv("CLIPFORGE_COMPUTE", raising=False)
    assert compute_backend() == "modal"
    assert should_dispatch_to_modal() is True


def test_falls_back_to_local_when_modal_is_requested_but_unconfigured(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_COMPUTE", "modal")
    monkeypatch.delenv("MODAL_GPU_BASE_URL", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    assert compute_backend() == "local"
    assert should_dispatch_to_modal() is False


def test_explicit_local_overrides_configured_modal(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_COMPUTE", "local")
    monkeypatch.setenv("MODAL_GPU_BASE_URL", "https://example.modal.run")
    assert compute_backend() == "local"
    assert should_dispatch_to_modal() is False


def test_whisper_runtime_defaults_to_cpu_int8(monkeypatch):
    monkeypatch.delenv("CLIPFORGE_WHISPER_DEVICE", raising=False)
    monkeypatch.delenv("CLIPFORGE_WHISPER_COMPUTE_TYPE", raising=False)
    assert whisper_runtime() == ("cpu", "int8")


def test_whisper_runtime_uses_cuda_float16_on_gpu_workers(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_WHISPER_DEVICE", "cuda")
    monkeypatch.delenv("CLIPFORGE_WHISPER_COMPUTE_TYPE", raising=False)
    assert whisper_runtime() == ("cuda", "float16")


def test_video_encoder_args_use_nvenc_when_requested(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_VIDEO_ENCODER", "h264_nvenc")
    args = video_encoder_args(has_nvenc=True)
    assert args[:2] == ["-c:v", "h264_nvenc"]


def test_video_encoder_args_fall_back_to_libx264_without_nvenc(monkeypatch):
    monkeypatch.setenv("CLIPFORGE_VIDEO_ENCODER", "h264_nvenc")
    args = video_encoder_args(has_nvenc=False)
    assert args[:2] == ["-c:v", "libx264"]
