import re
from pathlib import Path


VOICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def normalize_voice_id(value: str) -> str:
    voice_id = str(value or "").strip()
    if voice_id.lower().endswith(".wav"):
        voice_id = voice_id[:-4]
    if "/" in voice_id or "\\" in voice_id or not VOICE_ID_PATTERN.fullmatch(voice_id):
        raise ValueError("Voice ID must use only letters, numbers, dot, dash, or underscore.")
    return voice_id


def delete_voice_artifacts(voice_dir: Path, voice_id: str) -> list[str]:
    normalized = normalize_voice_id(voice_id)
    removed: list[str] = []
    for suffix in (".wav", ".pt"):
        path = voice_dir / f"{normalized}{suffix}"
        if path.is_file():
            path.unlink()
            removed.append(path.name)
    return removed
