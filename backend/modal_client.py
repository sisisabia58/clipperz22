from __future__ import annotations

import base64
import io
import json
import os
import time
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


def _retryable_url_error(exc: URLError) -> bool:
    reason = getattr(exc, "reason", None)
    if reason is None:
        return True
    message = str(reason).lower()
    return any(
        token in message
        for token in (
            "broken pipe",
            "connection reset",
            "timed out",
            "temporarily unavailable",
            "connection refused",
            "eof",
        )
    )


class UrllibTransport:
    def __init__(self, timeout: float = 3600, retries: int = 4) -> None:
        self.timeout = timeout
        self.retries = retries

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        last_error: URLError | None = None
        for attempt in range(self.retries):
            request = Request(url, data=body, method=method, headers=headers)
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = response.read()
                    return int(response.status), dict(response.headers.items()), payload
            except HTTPError as exc:
                payload = exc.read() if exc.fp is not None else b""
                return int(exc.code), dict(exc.headers.items() if exc.headers else []), payload
            except URLError as exc:
                last_error = exc
                if attempt + 1 >= self.retries or not _retryable_url_error(exc):
                    break
                time.sleep(min(2**attempt, 8))
        raise ModalGPUError(f"Failed to reach Modal GPU endpoint: {last_error}") from last_error


class ModalGPUClient:
    def __init__(
        self,
        base_url: str = "",
        key: str = "",
        secret: str = "",
        transport: HttpTransport | None = None,
        poll_interval: float = 5.0,
        poll_timeout: float = 3600.0,
        app_name: str = "clipforge-gpu",
        function_name: str = "execute_clip_job",
        token_id: str = "",
        token_secret: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.key = key
        self.secret = secret
        self.transport = transport or UrllibTransport()
        self.poll_interval = poll_interval
        self.poll_timeout = poll_timeout
        self.app_name = app_name
        self.function_name = function_name
        self.token_id = token_id
        self.token_secret = token_secret

    @classmethod
    def from_env(cls) -> "ModalGPUClient":
        poll_interval = float(os.environ.get("MODAL_JOB_POLL_INTERVAL", "5"))
        poll_timeout = float(os.environ.get("MODAL_JOB_POLL_TIMEOUT", "3600"))
        token_id = os.environ.get("MODAL_TOKEN_ID", "").strip()
        token_secret = os.environ.get("MODAL_TOKEN_SECRET", "").strip()
        base_url = os.environ.get("MODAL_GPU_BASE_URL", "").strip()
        if not token_id and not base_url:
            raise ModalGPUError("Set MODAL_TOKEN_ID/MODAL_TOKEN_SECRET or MODAL_GPU_BASE_URL")
        return cls(
            base_url,
            os.environ.get("MODAL_PROXY_KEY")
            or os.environ.get("MODAL_KEY")
            or "",
            os.environ.get("MODAL_PROXY_SECRET")
            or os.environ.get("MODAL_SECRET")
            or "",
            poll_interval=poll_interval,
            poll_timeout=poll_timeout,
            app_name=os.environ.get("MODAL_APP_NAME", "clipforge-gpu").strip() or "clipforge-gpu",
            function_name=os.environ.get("MODAL_FUNCTION_NAME", "execute_clip_job").strip() or "execute_clip_job",
            token_id=token_id,
            token_secret=token_secret,
        )

    def _uses_sdk(self) -> bool:
        return bool(self.token_id and self.token_secret)

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        headers = {
            "Accept": "*/*",
            "Content-Type": content_type,
            "Connection": "close",
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
        if self._uses_sdk():
            return {
                "status": "ok",
                "gpu": True,
                "transport": "modal-sdk",
                "app": self.app_name,
                "function": self.function_name,
            }
        if not self.base_url:
            raise ModalGPUError("MODAL_GPU_BASE_URL is not set")
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

    def _wait_for_job(self, call_id: str) -> bytes:
        deadline = time.time() + self.poll_timeout
        while time.time() < deadline:
            headers, payload = self._request("GET", f"/jobs/{call_id}")
            content_type = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
            if "application/zip" in content_type or payload.startswith(b"PK"):
                return payload
            try:
                status = json.loads(payload.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ModalGPUError("Modal GPU job returned an unexpected response while polling") from exc
            if status.get("status") == "running":
                time.sleep(self.poll_interval)
                continue
            raise ModalGPUError(f"Modal GPU job ended unexpectedly: {status}")
        raise ModalGPUError(f"Modal GPU job timed out after {int(self.poll_timeout)}s")

    def _build_job_payload(self, request: dict[str, Any], source_bytes: bytes | None) -> dict[str, Any]:
        payload: dict[str, Any] = {"request": request}
        if source_bytes is not None:
            payload["source_b64"] = base64.b64encode(source_bytes).decode("ascii")
            payload["source_name"] = Path(str(request.get("source_file") or "upload.mp4")).name
        return payload

    def _extract_archive(self, archive_bytes: bytes, output_dir: Path) -> str:
        output_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            archive.extractall(output_dir)
            names = archive.namelist()
        top_levels = {Path(name).parts[0] for name in names if name}
        if len(top_levels) == 1:
            return str(output_dir / next(iter(top_levels)))
        return str(output_dir)

    def _run_job_sdk(self, payload: dict[str, Any]) -> bytes:
        import modal

        fn = modal.Function.from_name(self.app_name, self.function_name)
        call = fn.spawn(payload)
        deadline = time.time() + self.poll_timeout
        while time.time() < deadline:
            try:
                return call.get(timeout=0)
            except TimeoutError:
                time.sleep(self.poll_interval)
        raise ModalGPUError(f"Modal GPU job timed out after {int(self.poll_timeout)}s")

    def _run_job_http(self, payload: dict[str, Any]) -> bytes:
        if not self.base_url:
            raise ModalGPUError("MODAL_GPU_BASE_URL is not set")
        _headers, body = self._request("POST", "/jobs", json.dumps(payload).encode("utf-8"))
        queued = json.loads(body.decode("utf-8"))
        call_id = queued.get("call_id")
        if not call_id:
            raise ModalGPUError("Modal GPU job did not return a call_id")
        return self._wait_for_job(call_id)

    def run_job(self, request: dict[str, Any], output_dir: Path, source_bytes: bytes | None = None) -> str:
        payload = self._build_job_payload(request, source_bytes)
        archive_bytes = self._run_job_sdk(payload) if self._uses_sdk() else self._run_job_http(payload)
        return self._extract_archive(archive_bytes, output_dir)
