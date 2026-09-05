from __future__ import annotations

import base64
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModalGPUError(RuntimeError):
    pass


class HttpTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        ...


class UrllibTransport:
    def __init__(self, timeout: float = 3600) -> None:
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
                return int(response.status), dict(response.headers.items()), payload
        except HTTPError as exc:
            payload = exc.read() if exc.fp is not None else b""
            return int(exc.code), dict(exc.headers.items() if exc.headers else []), payload
        except URLError as exc:
            raise ModalGPUError(f"Failed to reach Modal GPU endpoint: {exc}") from exc


class ModalGPUClient:
    def __init__(
        self,
        base_url: str,
        key: str = "",
        secret: str = "",
        transport: HttpTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.key = key
        self.secret = secret
        self.transport = transport or UrllibTransport()

    @classmethod
    def from_env(cls) -> "ModalGPUClient":
        base_url = os.environ.get("MODAL_GPU_BASE_URL", "").strip()
        if not base_url:
            raise ModalGPUError("MODAL_GPU_BASE_URL is not set")
        return cls(
            base_url,
            os.environ.get("MODAL_PROXY_KEY")
            or os.environ.get("MODAL_KEY")
            or "",
            os.environ.get("MODAL_PROXY_SECRET")
            or os.environ.get("MODAL_SECRET")
            or "",
        )

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "Content-Type": content_type,
        }
        if self.key:
            headers["Modal-Key"] = self.key
        if self.secret:
            headers["Modal-Secret"] = self.secret
        return headers

    def _request(self, method: str, path: str, body: bytes | None = None) -> tuple[dict[str, str], bytes]:
        url = f"{self.base_url}{path}"
        status, headers, payload = self.transport.request(method, url, self._headers(), body)
        if status >= 400:
            detail = payload.decode("utf-8", errors="replace") or f"HTTP {status}"
            raise ModalGPUError(detail)
        return headers, payload

    def health(self) -> dict[str, Any]:
        _headers, payload = self._request("GET", "/health")
        return json.loads(payload.decode("utf-8"))

    def transcribe(
        self,
        audio_bytes: bytes,
        model: str,
        language: str,
    ) -> dict[str, Any]:
        body = json.dumps(
            {
                "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
                "model": model,
                "language": language,
            }
        ).encode("utf-8")
        _headers, payload = self._request("POST", "/transcribe", body)
        return json.loads(payload.decode("utf-8"))

    def encode(self, video_bytes: bytes, clip: dict[str, Any], options: dict[str, Any] | None = None) -> bytes:
        body = json.dumps(
            {
                "video_b64": base64.b64encode(video_bytes).decode("ascii"),
                "clip": clip,
                "options": options or {},
            }
        ).encode("utf-8")
        _headers, payload = self._request("POST", "/encode", body)
        return payload

    def run_job(self, request: dict[str, Any], output_dir: Path, source_bytes: bytes | None = None) -> str:
        payload = {"request": request}
        if source_bytes is not None:
            payload["source_b64"] = base64.b64encode(source_bytes).decode("ascii")
            payload["source_name"] = Path(str(request.get("source_file") or "upload.mp4")).name
        _headers, archive_bytes = self._request("POST", "/jobs", json.dumps(payload).encode("utf-8"))
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            archive.extractall(output_dir)
            names = archive.namelist()
        top_levels = {Path(name).parts[0] for name in names if name}
        if len(top_levels) == 1:
            return str(output_dir / next(iter(top_levels)))
        return str(output_dir)
