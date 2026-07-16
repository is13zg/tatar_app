# -*- coding: utf-8 -*-
"""Заливка предложений: черновик + правки эксперта → приложение (через admin API).

Использование:
  python tools/apply_sentences.py --app http://127.0.0.1:8001 --password ...
Опции: --draft sentences_draft.json --fixes sentences_fixes.json
Также озвучивает предложения (батчами) и токены для конструктора.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import httpx

TOKEN_RE = re.compile(r"[^\wәөүҗңһӘӨҮҖҢҺ-]+")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="http://127.0.0.1:8001")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--draft", default="sentences_draft.json")
    ap.add_argument("--fixes", default="sentences_fixes.json")
    ap.add_argument("--skip-tts", action="store_true")
    args = ap.parse_args()

    draft = json.loads(Path(args.draft).read_text(encoding="utf-8"))
    fixes = {}
    if Path(args.fixes).exists():
        for f in json.loads(Path(args.fixes).read_text(encoding="utf-8")):
            fixes[f["id"]] = f
    print(f"черновик: {len(draft)}, правок эксперта: {len(fixes)}")

    items = []
    for d in draft:
        f = fixes.get(d["id"])
        st = (f or d).get("sentence_tt")
        sr = (f or d).get("sentence_ru")
        if st:
            items.append({"id": d["id"], "sentence_tt": st.strip(), "sentence_ru": (sr or "").strip()})

    def login() -> dict:
        r = httpx.post(f"{args.app}/auth/login", data={"username": args.user, "password": args.password}, timeout=30)
        r.raise_for_status()
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    h = login()
    r = httpx.post(f"{args.app}/admin/import_sentences", headers=h, json={"items": items}, timeout=300)
    r.raise_for_status()
    print("импорт:", r.json())

    if args.skip_tts:
        return

    # озвучка предложений батчами
    total = 0
    while True:
        r = httpx.post(f"{args.app}/admin/tts_sentences_all?limit=50", headers=h, timeout=600)
        if r.status_code == 401:
            h = login()
            continue
        r.raise_for_status()
        done = r.json().get("done", 0)
        errs = r.json().get("remaining_errors", [])
        total += done
        print(f"озвучено предложений: +{done} (всего {total}), ошибки: {errs}")
        if done == 0:
            break

    # токены для плиток конструктора (все уникальные слова всех предложений)
    tokens = set()
    for it in items:
        for t in TOKEN_RE.split(it["sentence_tt"]):
            if t:
                tokens.add(t.lower())
    tokens = sorted(tokens)
    print("уникальных токенов:", len(tokens))
    for i in range(0, len(tokens), 100):
        chunk = tokens[i:i + 100]
        r = httpx.post(f"{args.app}/admin/tts_tokens", headers=h, json={"tokens": chunk}, timeout=900)
        if r.status_code == 401:
            h = login()
            r = httpx.post(f"{args.app}/admin/tts_tokens", headers=h, json={"tokens": chunk}, timeout=900)
        r.raise_for_status()
        print(f"токены {i}-{i + len(chunk)}: {r.json().get('done')} ok, ошибок {len(r.json().get('errors', []))}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
