import base64
import hashlib
import re
from pathlib import Path
from typing import Optional

import httpx

from .config import STATIC_DIR

TTS_API_URL = "https://tat-tts.api.translate.tatar/listening/"
DEFAULT_SPEAKER = "alsu"  # женский голос — звучит стабильнее мужского almaz
MAX_TEXT_LEN = 200

_slug_re = re.compile(r"[^\wәөүҗңһӘӨҮҖҢҺ-]+", re.UNICODE)


def _cache_path(text: str, speaker: str) -> Path:
    digest = hashlib.md5(f"{speaker}:{text}".encode("utf-8")).hexdigest()[:10]
    slug = _slug_re.sub("_", text.strip().lower())[:40].strip("_") or "tts"
    return Path(STATIC_DIR) / "voice" / "tts" / f"{slug}_{digest}.wav"


def _to_url(path: Path) -> str:
    rel = path.relative_to(Path(STATIC_DIR)).as_posix()
    return f"/static/{rel}"


def cached_tts_url(text: str, speaker: str = DEFAULT_SPEAKER) -> Optional[str]:
    path = _cache_path(text, speaker)
    return _to_url(path) if path.exists() else None


async def synthesize_to_file(text: str, speaker: str = DEFAULT_SPEAKER,
                             force: bool = False) -> str:
    """Synthesize Tatar speech via tat-tts API, cache as wav under static, return URL.

    force=True — сгенерировать заново, даже если файл уже есть: tat-tts каждый
    раз произносит чуть по-разному, и кнопка «переозвучить» обязана давать
    новый дубль, а не возвращать старый из кэша. Файл перезаписывается по тому
    же пути (кэш ключуется строкой), поэтому вызывающий обязан добавить ?v=
    к сохранённому URL — иначе браузеры продолжат играть старую версию."""
    text = text.strip()
    if not text:
        raise ValueError("Пустой текст для озвучки")
    if len(text) > MAX_TEXT_LEN:
        raise ValueError("Слишком длинный текст для озвучки")

    path = _cache_path(text, speaker)
    if path.exists() and not force:
        return _to_url(path)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(TTS_API_URL, params={"speaker": speaker, "text": text})
        resp.raise_for_status()
        data = resp.json()
    wav_b64 = data.get("wav_base64")
    if not wav_b64:
        raise RuntimeError(f"TTS API не вернул аудио: {str(data)[:200]}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(wav_b64))
    return _to_url(path)
