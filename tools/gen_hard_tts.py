# -*- coding: utf-8 -*-
"""Предозвучка фраз для форматов выше уровня слова (движок берёт их только из кэша):

  • «Песи карават астында.» — послелоги места (ex_where);
  • «барды», «ашады» — прошедшее время (ex_past);
  • «Ничә алма?» и «ике алма … биш алма» — счёт с существительным (ex_count);
  • «Ул ашамады.» — причина состояния (ex_why).

Запуск в контейнере:
  docker exec tatar_app python tools/gen_hard_tts.py --db /usr/src/app/data/app.db
"""
import argparse
import asyncio
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

from app.forms import PAST_TT  # noqa: E402
from app.routers.lessons import (ANCHOR_TT, COUNT_MAX, COUNTABLE_TT,  # noqa: E402
                                 MOOD_CAUSES, NUMERALS_TT, PLACE_SCENES)
from app.tts import cached_tts_url, synthesize_to_file  # noqa: E402


def collect(db: str) -> list[str]:
    con = sqlite3.connect(db)
    have = {r[0].lower() for r in con.execute("select text_tt from words")}
    phrases: list[str] = []

    # послелоги: у каждого своя фраза НА КАЖДОЙ опоре — «Песи карават астында.»
    # и «Песи тартма астында.»; движок берёт их только из кэша
    for tt, scene in PLACE_SCENES.items():
        for anchor in scene["anchors"]:
            phrases.append(f"Песи {ANCHOR_TT[anchor]} {tt}.")

    phrases += [past for verb, past in PAST_TT.items() if verb in have]

    for tt in COUNTABLE_TT:
        if tt not in have:
            continue
        phrases.append(f"Ничә {tt}?")
        phrases += [f"{NUMERALS_TT[n]} {tt}" for n in range(2, COUNT_MAX + 1)]

    phrases += [cause for cause, _ru in MOOD_CAUSES.values()]

    # фразы самих новых тем (карточка озвучивает предложение)
    for theme in ("Кайда? Где что лежит", "Кәеф ничек? Настроения", "Һава торышы. Погода"):
        for (s,) in con.execute(
            "select sentence_tt from words where theme_id=(select id from themes where title_ru=?) "
            "and sentence_tt is not null", (theme,)
        ):
            phrases.append(s)
    return list(dict.fromkeys(phrases))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    args = ap.parse_args()

    phrases = collect(args.db)
    done = skip = err = 0
    for p in phrases:
        if cached_tts_url(p):
            skip += 1
            continue
        try:
            await synthesize_to_file(p)
            done += 1
            if done % 25 == 0:
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
