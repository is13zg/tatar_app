# -*- coding: utf-8 -*-
"""Оптимизация медиа при загрузке и батчем (tools/optimize_media.py).

Картинки: ужимаются до 512px по большей стороне и пережимаются в JPEG q85
(в приложении они показываются максимум ~240px — 1024px от flux избыточны).
Файл сохраняется под именем word_N.png независимо от байтов внутри — браузеры
определяют формат по содержимому (так уже работают все flux-картинки).
SVG не трогаем (вектор).

Звук: WAV приводится к 22050 Гц / моно / 16 бит (формат tat-tts) — студийные
44100-стерео записи становятся в 4 раза меньше без слышимой потери для речи.
Сжатые форматы (mp3/ogg/m4a/webm) не трогаем.
"""
import io
from typing import Optional

MAX_SIDE = 512
JPEG_QUALITY = 85
TARGET_RATE = 22050


def optimize_image(data: bytes) -> Optional[bytes]:
    """Оптимизированные JPEG-байты или None (SVG/не картинка/уже оптимально)."""
    head = data[:200].lstrip()[:64].lower()
    if head.startswith(b"<svg") or head.startswith(b"<?xml"):
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    small_enough = max(img.size) <= MAX_SIDE
    # прозрачность кладём на белый фон (в приложении фон и так белый)
    if img.mode != "RGB":
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        img = bg
    if not small_enough:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    result = out.getvalue()
    if len(result) >= len(data):
        return None  # уже компактнее нашего — не портим
    return result


def optimize_wav(data: bytes) -> Optional[bytes]:
    """WAV → 22050/моно/16бит; None если не WAV, уже оптимален или не распарсился."""
    if data[:4] != b"RIFF":
        return None
    import audioop  # deprecated с 3.13, контейнер на 3.12; при апгрейде питона заменить
    import wave
    try:
        src = wave.open(io.BytesIO(data))
        nch, sw, rate = src.getnchannels(), src.getsampwidth(), src.getframerate()
        frames = src.readframes(src.getnframes())
    except Exception:
        return None
    if nch == 1 and sw == 2 and rate <= TARGET_RATE:
        return None  # уже формат tat-tts
    try:
        if sw != 2:
            frames = audioop.lin2lin(frames, sw, 2)
        if nch == 2:
            frames = audioop.tomono(frames, 2, 0.5, 0.5)
        elif nch != 1:
            return None
        if rate > TARGET_RATE:
            frames, _ = audioop.ratecv(frames, 2, 1, rate, TARGET_RATE, None)
            rate = TARGET_RATE
    except Exception:
        return None
    out = io.BytesIO()
    dst = wave.open(out, "wb")
    dst.setnchannels(1)
    dst.setsampwidth(2)
    dst.setframerate(rate)
    dst.writeframes(frames)
    dst.close()
    result = out.getvalue()
    return result if len(result) < len(data) else None
