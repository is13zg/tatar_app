# -*- coding: utf-8 -*-
"""Починка заголовков WAV после Сбера SaluteSpeech.

Сбер отдаёт потоковый WAV: в RIFF-заголовке размеры записаны как 0xFFFFFFF7,
из-за чего браузер считает длительность равной 89478 секундам. Событие
окончания воспроизведения может не сработать, и плеер ждёт страховочный
таймаут — перед словом появляется пауза в несколько секунд.

Скрипт переписывает размеры на фактические, аудиоданные не трогает.

Запуск:  python tools/fix_wav_headers.py static/voice/ru
         docker exec tatar_app python tools/fix_wav_headers.py /usr/src/app/static/voice/ru
"""
import glob
import os
import struct
import sys


def fix(path: str) -> str:
    raw = open(path, "rb").read()
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        return "не WAV"
    fmt = None
    i = 12
    while i + 8 <= len(raw):
        cid = raw[i:i + 4]
        size = struct.unpack("<I", raw[i + 4:i + 8])[0]
        if cid == b"fmt ":
            fmt = raw[i + 8:i + 8 + 16]
        if cid == b"data":
            data = raw[i + 8:]          # всё до конца файла — это и есть аудио
            if size == len(data):
                return "ок"
            if not fmt:
                return "нет fmt-чанка"
            head = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
                    + b"fmt " + struct.pack("<I", 16) + fmt
                    + b"data" + struct.pack("<I", len(data)))
            open(path, "wb").write(head + data)
            return f"починен ({size} → {len(data)} байт)"
        if size == 0xFFFFFFFF or size > len(raw):
            return "битый размер чанка, data не найден"
        i += 8 + size + (size & 1)
    return "data не найден"


def main() -> None:
    folder = sys.argv[1] if len(sys.argv) > 1 else "static/voice/ru"
    files = sorted(glob.glob(os.path.join(folder, "*.wav")))
    counts: dict[str, int] = {}
    for p in files:
        res = fix(p)
        key = res.split(" (")[0]
        counts[key] = counts.get(key, 0) + 1
        if key not in ("ок",):
            print(f"{os.path.basename(p):26} {res}")
    print(f"\nвсего файлов: {len(files)}; " + ", ".join(f"{k}: {v}" for k, v in counts.items()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
