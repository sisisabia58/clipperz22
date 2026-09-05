from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from gdrive import DriveClient, DriveError, DriveSettings, DriveToken


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.responses: list[tuple[int, dict[str, str], bytes]] = []

    def queue(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.responses.append((status, headers or {"content-type": "application/json"}, body))

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        if not self.responses:
            raise AssertionError(f"unexpected request {method} {url}")
        return self.responses.pop(0)


def test_authorization_url_includes_drive_scopes_and_offline_access():
    client = DriveClient(
        client_id="cid.apps.googleusercontent.com",
        client_secret="secret",
        redirect_uri="http://127.0.0.1:43123/api/drive/callback",
    )
    url = client.authorization_url("state-123")
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert query["client_id"] == ["cid.apps.googleusercontent.com"]
    assert query["state"] == ["state-123"]
    assert query["access_type"] == ["offline"]
    assert "drive.readonly" in query["scope"][0]
    assert "drive.file" in query["scope"][0] or "auth/drive" in query["scope"][0]


def test_exchange_code_stores_refresh_token(tmp_path: Path):
    transport = FakeTransport()
    transport.queue(
        200,
        json.dumps(
            {
                "access_token": "ya29.access",
                "refresh_token": "1//refresh",
                "expires_in": 3600,
                "token_type": "Bearer",
            }
        ).encode(),
    )
    transport.queue(200, json.dumps({"email": "creator@gmail.com"}).encode())
    client = DriveClient(
        client_id="cid",
        client_secret="secret",
        redirect_uri="http://localhost/callback",
        store_path=tmp_path / "gdrive.json",
        transport=transport,
    )

    token = client.exchange_code("auth-code")

    assert token.access_token == "ya29.access"
    assert token.refresh_token == "1//refresh"
    saved = json.loads((tmp_path / "gdrive.json").read_text())
    assert saved["refresh_token"] == "1//refresh"
    assert saved["email"] == "creator@gmail.com"


def test_list_videos_returns_drive_files(tmp_path: Path):
    transport = FakeTransport()
    transport.queue(
        200,
        json.dumps(
            {
                "files": [
                    {"id": "vid1", "name": "podcast.mp4", "mimeType": "video/mp4", "size": "12"},
                ]
            }
        ).encode(),
    )
    client = DriveClient(store_path=tmp_path / "gdrive.json", transport=transport)
    client.save_token(DriveToken(access_token="tok", refresh_token="ref", email="a@b.c"))

    files = client.list_videos()

    assert files[0].id == "vid1"
    assert files[0].name == "podcast.mp4"
    assert "drive/v3/files" in transport.calls[0]["url"]
    assert "video/" in unquote(transport.calls[0]["url"])


def test_import_downloads_video_into_uploads(tmp_path: Path):
    transport = FakeTransport()
    transport.queue(200, json.dumps({"id": "vid1", "name": "talk.mp4", "mimeType": "video/mp4"}).encode())
    transport.queue(200, b"FAKEVIDEO", {"content-type": "video/mp4"})
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    client = DriveClient(store_path=tmp_path / "gdrive.json", transport=transport)
    client.save_token(DriveToken(access_token="tok", refresh_token="ref"))

    imported = client.import_video("vid1", uploads)

    assert imported.original_name == "talk.mp4"
    assert (uploads / imported.source_file).read_bytes() == b"FAKEVIDEO"
    assert imported.source_file.endswith(".mp4")


def test_upload_clip_posts_to_configured_folder(tmp_path: Path):
    transport = FakeTransport()
    transport.queue(200, json.dumps({"id": "file-uploaded"}).encode())
    client = DriveClient(store_path=tmp_path / "gdrive.json", transport=transport)
    client.save_token(DriveToken(access_token="tok", refresh_token="ref"))
    clip = tmp_path / "clip_01.mp4"
    clip.write_bytes(b"clip-bytes")

    uploaded_id = client.upload_file(clip, folder_id="folder-dest", name="clip_01.mp4")

    assert uploaded_id == "file-uploaded"
    call = transport.calls[0]
    assert call["method"] == "POST"
    assert "upload/drive/v3/files" in call["url"]
    assert b"folder-dest" in (call["body"] or b"")


def test_save_and_load_destination_settings(tmp_path: Path):
    client = DriveClient(store_path=tmp_path / "gdrive.json")
    client.save_token(DriveToken(access_token="tok", refresh_token="ref", email="a@b.c"))
    client.save_settings(
        DriveSettings(folder_id="abc", folder_name="ClipForge Out", auto_upload=True)
    )
    settings = client.load_settings()
    assert settings.folder_id == "abc"
    assert settings.auto_upload is True


def test_authorization_url_requires_client_id():
    client = DriveClient(client_id="", client_secret="")
    with pytest.raises(DriveError):
        client.authorization_url("state")
