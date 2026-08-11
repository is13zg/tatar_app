# -*- coding: utf-8 -*-
"""Сверка всей базы со словарём Ганиева (syzlek.ru).

Для каждого татарского слова берём статью из татарско-русского раздела и
смотрим, встречается ли в ней наш русский перевод. Так ловятся две беды,
которые глазами не видны: русское слово, записанное кириллицей и выданное
за татарское (кубик вместо шакмак, юла вместо бөтерчек), и перевод не из
того значения.

Скрипт НИЧЕГО не меняет — только печатает отчёт. Сайт отдаёт только http,
поэтому идём через httpx напрямую.

  python tools/check_dictionary.py words.json [--out report.json]
"""
import argparse
import json
import re
import sys
import time
import urllib.parse

import httpx

URL = "http://syzlek.ru/?word="
# «мяч» и «мячик», «санки» и «сани» — одно и то же; сравниваем по началу слова
STEM = 5


def norm(s: str) -> str:
    return s.lower().replace("ё", "е").strip()


def article(html: str, word: str) -> str:
    """Статья татарско-русского раздела, начинающаяся с этого слова."""
    text = re.sub(r"<[^>]+>", "\n", html)
    text = re.sub(r"\n\s*\n+", "\n", text)
    tt_ru = text.split("Татарско-русский словарь")[-1]
    w = norm(word)
    out = []
    for line in tt_ru.split("\n"):
        line = line.strip()
        if not line:
            continue
        head = norm(re.split(r"[\s(]", line)[0])
        if head == w or head == w + "I" or head.rstrip("i") == w:
            out.append(line)
    return " ".join(out)


def gloss_hit(art: str, ru: str) -> bool:
    """Есть ли наш перевод среди значений статьи (по корню, без окончаний)."""
    a = norm(art)
    for part in re.split(r"[,;/()]| или ", norm(ru)):
        part = part.strip()
        if len(part) < 3:
            continue
        if part in a or (len(part) > STEM and part[:STEM] in a):
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("words", help="json со списком {id, tt, ru, theme}")
    ap.add_argument("--out", default="dict_report.json")
    ap.add_argument("--delay", type=float, default=0.25)
    args = ap.parse_args()

    words = json.load(open(args.words, encoding="utf-8"))
    single = [w for w in words if " " not in w["tt"]]
    c = httpx.Client(timeout=60, follow_redirects=True)
    missing, mismatch, ok, err = [], [], 0, []
    for i, w in enumerate(single, 1):
        try:
            html = c.get(URL + urllib.parse.quote(w["tt"])).text
        except Exception as e:
            err.append({**w, "error": str(e)[:80]})
            continue
        art = article(html, w["tt"])
        if not art:
            missing.append(w)                    # слова нет в татарском словаре вовсе
        elif not gloss_hit(art, w["ru"]):
            mismatch.append({**w, "article": art[:300]})
        else:
            ok += 1
        if i % 50 == 0:
            print(f"...{i}/{len(single)}", flush=True)
        time.sleep(args.delay)

    print(f"\nсверено {len(single)} однословных из {len(words)}")
    print(f"совпало: {ok} | нет статьи: {len(missing)} | перевод не найден в статье: {len(mismatch)}"
          f" | сетевых ошибок: {len(err)}")
    json.dump({"missing": missing, "mismatch": mismatch, "errors": err},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("подробности:", args.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
