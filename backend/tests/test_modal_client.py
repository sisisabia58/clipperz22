from __future__ import annotations

import json
from pathlib import Path

import pytest

from modal_client import ModalGPUClient, ModalGPUError


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.response_status = 200
        self.response_body = b"{}"
        self.response_content_type = "application/json"

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        return (
            self.response_status,
            {"content-type": self.response_content_type},
            self.response_body,
        )


def test_transcribe_posts_audio_to_modal_endpoint():
    transport = FakeTransport()
    transport.response_body = json.dumps(
        {"segments": [{"start": 0.0, "end": 1.2, "text": "halo"}]}
    ).encode()
    client = ModalGPUClient("https://clipforge.modal.run", "wk-test", "ws-test", transport=transport)

    result = client.transcribe(audio_bytes=b"RIFF", model="Systran/faster-whisper-small", language="id")

    assert result["segments"][0]["text"] == "halo"
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://clipforge.modal.run/transcribe"
    assert call["headers"]["Modal-Key"] == "wk-test"
    assert call["headers"]["Modal-Secret"] == "ws-test"


def test_encode_posts_clip_request_and_returns_mp4_bytes():
    transport = FakeTransport()
    transport.response_body = b"mp4-bytes"
    transport.response_content_type = "video/mp4"
    client = ModalGPUClient("https://clipforge.modal.run", transport=transport)

    payload = client.encode(video_bytes=b"video", clip={"start": 1, "end": 4})

    assert payload == b"mp4-bytes"
    assert transport.calls[0]["url"] == "https://clipforge.modal.run/encode"


def test_run_job_writes_returned_archive_into_output_dir(tmp_path: Path):
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("demo/clips/clip_01_test.mp4", b"clip")
        archive.writestr("demo/candidates.json", b"[]")
    transport = FakeTransport()
    transport.response_body = buffer.getvalue()
    transport.response_content_type = "application/zip"
    client = ModalGPUClient("https://clipforge.modal.run", transport=transport)

    extracted = client.run_job({"url": "https://youtu.be/x"}, output_dir=tmp_path)

    assert (tmp_path / "demo/clips/clip_01_test.mp4").read_bytes() == b"clip"
    assert extracted.endswith("demo") or (tmp_path / "demo").is_dir()
    assert transport.calls[0]["url"] == "https://clipforge.modal.run/jobs"


def test_client_raises_on_error_status():
    transport = FakeTransport()
    transport.response_status = 502
    transport.response_body = b"gpu unavailable"
    client = ModalGPUClient("https://clipforge.modal.run", transport=transport)

    with pytest.raises(ModalGPUError, match="gpu unavailable"):
        client.health()
