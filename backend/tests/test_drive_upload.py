from __future__ import annotations

from pathlib import Path

from api import ClipFile, ClipJobRequest, upload_clips_to_drive
from gdrive import DriveSettings


class FakeDrive:
    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str]] = []

    def upload_file(self, path: Path, folder_id: str, name: str | None = None) -> str:
        self.uploaded.append((path.name, folder_id, name or path.name))
        return "drive-id"


def test_upload_clips_to_drive_skips_when_disabled(tmp_path: Path):
    fake = FakeDrive()
    request = ClipJobRequest(url="https://youtu.be/x", drive_upload=False)
    logs = upload_clips_to_drive(
        request,
        [ClipFile(name="a.mp4", url="/outputs/a.mp4", size_bytes=1)],
        ["done"],
        client=fake,
        outputs_dir=tmp_path,
    )
    assert fake.uploaded == []
    assert logs == ["done"]


def test_upload_clips_to_drive_sends_local_mp4s(tmp_path: Path):
    clip_path = tmp_path / "demo" / "clips" / "clip_01_hello.mp4"
    clip_path.parent.mkdir(parents=True)
    clip_path.write_bytes(b"mp4")
    fake = FakeDrive()
    request = ClipJobRequest(url="https://youtu.be/x", drive_upload=True, drive_folder_id="folder-dest")
    logs = upload_clips_to_drive(
        request,
        [ClipFile(name="clip_01_hello.mp4", url="/outputs/demo/clips/clip_01_hello.mp4", size_bytes=3)],
        ["done"],
        client=fake,
        outputs_dir=tmp_path,
    )
    assert fake.uploaded == [("clip_01_hello.mp4", "folder-dest", "clip_01_hello.mp4")]
    assert any("Google Drive" in line for line in logs)
