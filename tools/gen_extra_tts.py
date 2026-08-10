# -*- coding: utf-8 -*-
"""Предозвучка фраз для новых упражнений (движок берёт их только из кэша):

  • формы множественного числа — тренажёр «Один или много?» (app/forms.py);
  • «Марат X кия.» — сюжет «одень по погоде» (DRESS_SCENES).

Запуск в контейнере:
  docker exec tatar_app python tools/gen_extra_tts.py --db /usr/src/app/data/app.db
"""
import argparse
import asyncio
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

from app.forms import PLURAL_TT  # noqa: E402
from app.routers.lessons import DRESS_SCENES, SEASON_SIGNS  # noqa: E402
from app.tts import cached_tts_url, synthesize_to_file  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    have = {r[0].lower() for r in con.execute("select text_tt from words")}

    phrases = [pl for tt, pl in PLURAL_TT.items() if tt in have]
    for scene in DRESS_SCENES:
        for tt in scene["right"] + scene["wrong"]:
            if tt in have:
                phrases.append(f"Марат {tt} кия.")
    for signs in SEASON_SIGNS.values():
        phrases += [ph for ph, _ru in signs]
    phrases = list(dict.fromkeys(phrases))  # без повторов между сценами

    done = skip = err = 0
    for p in phrases:
        if cached_tts_url(p):
            skip += 1
            continue
        try:
            await synthesize_to_file(p)
            done += 1
            if done % 20 == 0:
                print(f"...{done}")
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
