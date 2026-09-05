from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/userinfo.email",
]


class DriveError(RuntimeError):
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
    def __init__(self, timeout: float = 120) -> None:
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
                return int(response.status), dict(response.headers.items()), response.read()
        except HTTPError as exc:
            payload = exc.read() if exc.fp is not None else b""
            return int(exc.code), dict(exc.headers.items() if exc.headers else []), payload
        except URLError as exc:
            raise DriveError(f"Failed to reach Google: {exc}") from exc


@dataclass
class DriveToken:
    access_token: str = ""
    refresh_token: str = ""
    email: str = ""
    expiry: float = 0.0


@dataclass
class DriveSettings:
    folder_id: str = ""
    folder_name: str = ""
    auto_upload: bool = False


@dataclass
class DriveFile:
    id: str
    name: str
    mime_type: str = ""
    size: str = ""
    thumbnail: str = ""


@dataclass
class ImportedVideo:
    source_file: str
    original_name: str
    duration: float | None = None


@dataclass
class DriveStore:
    token: DriveToken = field(default_factory=DriveToken)
    settings: DriveSettings = field(default_factory=DriveSettings)


class DriveClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        store_path: Path | None = None,
        transport: HttpTransport | None = None,
    ) -> None:
        self.client_id = (client_id if client_id is not None else os.environ.get("GOOGLE_CLIENT_ID", "")).strip()
        self.client_secret = (
            client_secret if client_secret is not None else os.environ.get("GOOGLE_CLIENT_SECRET", "")
        ).strip()
        self.redirect_uri = (
            redirect_uri
            if redirect_uri is not None
            else os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "http://127.0.0.1:43123/api/drive/callback")
        ).strip()
        data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent))
        self.store_path = store_path or Path(os.environ.get("GDRIVE_STORE", str(data_dir / "gdrive.json")))
        self.transport = transport or UrllibTransport()

    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def connected(self) -> bool:
        token = self.load_token()
        return bool(token.access_token or token.refresh_token)

    def authorization_url(self, state: str) -> str:
        if not self.client_id:
            raise DriveError("GOOGLE_CLIENT_ID is not set")
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(SCOPES),
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true",
                "state": state,
            }
        )
        return f"{AUTH_URL}?{query}"

    def _read_store(self) -> DriveStore:
        if not self.store_path.exists():
            return DriveStore()
        payload = json.loads(self.store_path.read_text(encoding="utf-8"))
        token = DriveToken(
            access_token=str(payload.get("access_token") or ""),
            refresh_token=str(payload.get("refresh_token") or ""),
            email=str(payload.get("email") or ""),
            expiry=float(payload.get("expiry") or 0),
        )
        settings = DriveSettings(
            folder_id=str(payload.get("folder_id") or ""),
            folder_name=str(payload.get("folder_name") or ""),
            auto_upload=bool(payload.get("auto_upload")),
        )
        return DriveStore(token=token, settings=settings)

    def _write_store(self, store: DriveStore) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            **asdict(store.token),
            **asdict(store.settings),
        }
        self.store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def save_token(self, token: DriveToken) -> None:
        store = self._read_store()
        if not token.refresh_token:
            token.refresh_token = store.token.refresh_token
        if not token.email:
            token.email = store.token.email
        store.token = token
        self._write_store(store)

    def load_token(self) -> DriveToken:
        return self._read_store().token

    def save_settings(self, settings: DriveSettings) -> None:
        store = self._read_store()
        store.settings = settings
        self._write_store(store)

    def load_settings(self) -> DriveSettings:
        return self._read_store().settings

    def clear(self) -> None:
        if self.store_path.exists():
            self.store_path.unlink()

    def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
        auth: bool = False,
        retry: bool = True,
    ) -> tuple[dict[str, str], bytes]:
        request_headers = dict(headers or {})
        if auth:
            token = self._valid_token()
            request_headers["Authorization"] = f"Bearer {token.access_token}"
        status, response_headers, payload = self.transport.request(method, url, request_headers, body)
        if status == 401 and auth and retry:
            self._refresh_access_token()
            return self._request(method, url, headers, body, auth=True, retry=False)
        if status >= 400:
            detail = payload.decode("utf-8", errors="replace") or f"HTTP {status}"
            raise DriveError(detail)
        return response_headers, payload

    def _valid_token(self) -> DriveToken:
        token = self.load_token()
        if not token.access_token and not token.refresh_token:
            raise DriveError("Google Drive is not connected")
        if token.refresh_token and token.expiry and token.expiry < time.time() + 30:
            self._refresh_access_token()
            token = self.load_token()
        return token

    def _refresh_access_token(self) -> None:
        token = self.load_token()
        if not token.refresh_token:
            raise DriveError("Google Drive session expired. Connect again.")
        body = urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": token.refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode()
        _headers, payload = self._request(
            "POST",
            TOKEN_URL,
            {"Content-Type": "application/x-www-form-urlencoded"},
            body,
            auth=False,
            retry=False,
        )
        data = json.loads(payload.decode("utf-8"))
        token.access_token = str(data.get("access_token") or "")
        token.expiry = time.time() + float(data.get("expires_in") or 3600)
        self.save_token(token)

    def exchange_code(self, code: str) -> DriveToken:
        body = urlencode(
            {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }
        ).encode()
        _headers, payload = self._request(
            "POST",
            TOKEN_URL,
            {"Content-Type": "application/x-www-form-urlencoded"},
            body,
        )
        data = json.loads(payload.decode("utf-8"))
        token = DriveToken(
            access_token=str(data.get("access_token") or ""),
            refresh_token=str(data.get("refresh_token") or ""),
            expiry=time.time() + float(data.get("expires_in") or 3600),
        )
        self.save_token(token)
        _headers, userinfo = self._request("GET", USERINFO_URL, auth=True)
        profile = json.loads(userinfo.decode("utf-8"))
        token.email = str(profile.get("email") or "")
        self.save_token(token)
        return token

    def list_videos(self, page_token: str = "") -> list[DriveFile]:
        query = {
            "q": "mimeType contains 'video/' and trashed = false",
            "pageSize": "50",
            "fields": "nextPageToken,files(id,name,mimeType,size,thumbnailLink,modifiedTime)",
            "orderBy": "modifiedTime desc",
        }
        if page_token:
            query["pageToken"] = page_token
        _headers, payload = self._request("GET", f"{DRIVE_FILES_URL}?{urlencode(query)}", auth=True)
        data = json.loads(payload.decode("utf-8"))
        return [
            DriveFile(
                id=str(item.get("id") or ""),
                name=str(item.get("name") or "video"),
                mime_type=str(item.get("mimeType") or ""),
                size=str(item.get("size") or ""),
                thumbnail=str(item.get("thumbnailLink") or ""),
            )
            for item in data.get("files") or []
        ]

    def list_folders(self) -> list[DriveFile]:
        query = {
            "q": "mimeType = 'application/vnd.google-apps.folder' and trashed = false",
            "pageSize": "100",
            "fields": "files(id,name)",
            "orderBy": "name",
        }
        _headers, payload = self._request("GET", f"{DRIVE_FILES_URL}?{urlencode(query)}", auth=True)
        data = json.loads(payload.decode("utf-8"))
        return [
            DriveFile(id=str(item.get("id") or ""), name=str(item.get("name") or "Folder"))
            for item in data.get("files") or []
        ]

    def import_video(self, file_id: str, uploads_dir: Path) -> ImportedVideo:
        _headers, payload = self._request(
            "GET",
            f"{DRIVE_FILES_URL}/{file_id}?fields=id,name,mimeType",
            auth=True,
        )
        meta = json.loads(payload.decode("utf-8"))
        original_name = str(meta.get("name") or "drive-video.mp4")
        suffix = Path(original_name).suffix.lower() or ".mp4"
        if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}:
            suffix = ".mp4"
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        _headers, media = self._request(
            "GET",
            f"{DRIVE_FILES_URL}/{file_id}?alt=media",
            auth=True,
        )
        target = uploads_dir / stored_name
        target.write_bytes(media)
        return ImportedVideo(source_file=stored_name, original_name=original_name)

    def upload_file(self, path: Path, folder_id: str, name: str | None = None) -> str:
        filename = name or path.name
        boundary = f"clipforge_{uuid.uuid4().hex}"
        metadata = json.dumps({"name": filename, "parents": [folder_id]})
        preamble = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{metadata}\r\n"
            f"--{boundary}\r\n"
            "Content-Type: video/mp4\r\n\r\n"
        ).encode("utf-8")
        closing = f"\r\n--{boundary}--\r\n".encode("utf-8")
        body = preamble + path.read_bytes() + closing
        _headers, payload = self._request(
            "POST",
            f"{DRIVE_UPLOAD_URL}?uploadType=multipart",
            {
                "Content-Type": f"multipart/related; boundary={boundary}",
            },
            body,
            auth=True,
        )
        data = json.loads(payload.decode("utf-8"))
        return str(data.get("id") or "")
