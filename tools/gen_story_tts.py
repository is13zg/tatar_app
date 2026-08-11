# -*- coding: utf-8 -*-
"""Озвучка мини-историй: по четыре предложения и два вопроса на историю.

Движок берёт фразы только из кэша app.tts (ключ — точная строка), поэтому
без прогона этого скрипта формат просто не выпадет.

Запуск в контейнере:
  docker exec tatar_app python tools/gen_story_tts.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.getcwd())

from app.tts import cached_tts_url, synthesize_to_file  # noqa: E402
from tools.stories import STORIES  # noqa: E402


async def main() -> None:
    phrases = []
    for st in STORIES:
        phrases += [tt for tt, _ru, _subj in st["parts"]]
        phrases += [q["tt"] for q in st["questions"]]
    phrases = list(dict.fromkeys(phrases))

    done = skip = err = 0
    for p in phrases:
        if cached_tts_url(p):
            skip += 1
            continue
        try:
            await synthesize_to_file(p)
            done += 1
            if done % 15 == 0:
                print(f"...{done}", flush=True)
            await asyncio.sleep(0.25)
        except Exception as e:
            err += 1
            print(f"ERR {p!r}: {e}")
            if err >= 10:
                sys.exit("слишком много ошибок TTS")
            await asyncio.sleep(3)
    print(f"готово: новых {done}, в кэше {skip}, ошибок {err} (всего фраз {len(phrases)})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
