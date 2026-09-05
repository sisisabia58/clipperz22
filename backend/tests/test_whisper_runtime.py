from __future__ import annotations

import sys
import types
from pathlib import Path


def test_transcribe_loads_faster_whisper_on_cuda(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CLIPFORGE_WHISPER_DEVICE", "cuda")
    monkeypatch.delenv("CLIPFORGE_WHISPER_COMPUTE_TYPE", raising=False)
    captured: dict[str, str] = {}

    class FakeModel:
        def __init__(self, name, device, compute_type):
            captured["name"] = name
            captured["device"] = device
            captured["compute_type"] = compute_type

        def transcribe(self, *args, **kwargs):
            class Info:
                language = "id"

            return iter([]), Info()

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    from clipper import transcribe

    transcribe(tmp_path / "audio.wav", tmp_path / "transcript.json", "Systran/faster-whisper-small", "id", force=True)
    assert captured["device"] == "cuda"
    assert captured["compute_type"] == "float16"
