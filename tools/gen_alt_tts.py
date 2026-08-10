# -*- coding: utf-8 -*-
"""Предозвучка альтернативных вопросов «Калынмы, юкамы?» по парам OPPOSITES_TT.

Движок берёт фразу только из кэша TTS, поэтому её надо синтезировать заранее.

Запуск в контейнере:
  docker exec tatar_app python tools/gen_alt_tts.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from app.qneg import question_particle  # noqa: E402
from app.routers.lessons import OPPOSITES_TT  # noqa: E402
from app.tts import cached_tts_url, synthesize_to_file  # noqa: E402


async def main() -> None:
    phrases = []
    for a, b in OPPOSITES_TT.items():
        phrase = f"{a.capitalize()}{question_particle(a)}, {b}{question_particle(b)}?"
        if phrase not in phrases:
            phrases.append(phrase)
    done = skip = err = 0
    for p in phrases:
        if cached_tts_url(p):
            skip += 1
            continue
        try:
            await synthesize_to_file(p)
            done += 1
            print(f"ok  {p}")
            await asyncio.sleep(0.3)
        except Exception as e:
            err += 1
            print(f"ERR {p}: {e}")
            await asyncio.sleep(3)
    print(f"готово: новых {done}, в кэше {skip}, ошибок {err}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
