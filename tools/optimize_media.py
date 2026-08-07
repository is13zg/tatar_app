# -*- coding: utf-8 -*-
"""Батч-оптимизация всей медиа-базы: картинки слов → ≤512px JPEG, WAV-звуки →
22050/моно/16бит (app/media.py). Обходит файлы, на которые ссылаются words.*,
перезаписывает на месте и бампит ?v= в БД, чтобы у клиентов слетел кэш.

  python tools/optimize_media.py [--db app.db] [--static static] [--dry]

--dry — только посчитать, ничего не менять.
"""
import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, os.getcwd())
from app.media import optimize_image, optimize_wav  # noqa: E402


def url_to_path(url: str, static_dir: Path):
    if not url or not url.startswith("/static/"):
        return None
    rel = url.split("?", 1)[0][len("/static/"):]
    p = static_dir / rel
    return p if p.is_file() else None


def bump(url: str) -> str:
    return url.split("?", 1)[0] + f"?v={int(time.time())}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    ap.add_argument("--static", default="static")
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    static_dir = Path(args.static)
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "select id, image_url, audio_url, sentence_audio_url from words order by id").fetchall()

    stats = {"img": [0, 0, 0], "wav": [0, 0, 0]}  # [файлов затронуто, байт до, байт после]
    skipped = errors = 0
    seen: set[Path] = set()

    def handle(kind: str, wid: int, col: str, url: str) -> None:
        nonlocal skipped, errors
        path = url_to_path(url, static_dir)
        if path is None or path in seen:
            return
        seen.add(path)
        if kind == "wav" and path.suffix.lower() != ".wav":
            return  # сжатые форматы не трогаем
        try:
            data = path.read_bytes()
            opt = optimize_image(data) if kind == "img" else optimize_wav(data)
        except Exception as e:
            errors += 1
            print(f"  ERR {path.name}: {e}")
            return
        if not opt:
            skipped += 1
            return
        stats[kind][0] += 1
        stats[kind][1] += len(data)
        stats[kind][2] += len(opt)
        if not args.dry:
            path.write_bytes(opt)
            con.execute(f"update words set {col}=? where id=?", (bump(url), wid))

    for r in rows:
        handle("img", r["id"], "image_url", r["image_url"])
        handle("wav", r["id"], "audio_url", r["audio_url"])
        handle("wav", r["id"], "sentence_audio_url", r["sentence_audio_url"])

    # второй проход: файлы-сироты в uploads (в БД не упомянуты, но место едят)
    def sweep(folder: Path, kind: str) -> None:
        nonlocal skipped, errors
        if not folder.is_dir():
            return
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path in seen:
                continue
            if kind == "wav" and path.suffix.lower() != ".wav":
                continue
            if kind == "img" and path.suffix.lower() == ".svg":
                continue
            seen.add(path)
            try:
                data = path.read_bytes()
                opt = optimize_image(data) if kind == "img" else optimize_wav(data)
            except Exception as e:
                errors += 1
                print(f"  ERR {path.name}: {e}")
                continue
            if not opt:
                skipped += 1
                continue
            stats[kind][0] += 1
            stats[kind][1] += len(data)
            stats[kind][2] += len(opt)
            if not args.dry:
                path.write_bytes(opt)

    sweep(static_dir / "image" / "uploads", "img")
    sweep(static_dir / "voice" / "uploads", "wav")

    if not args.dry:
        con.commit()
    mode = "DRY-RUN" if args.dry else "ГОТОВО"
    for kind, label in (("img", "картинки"), ("wav", "звуки")):
        n, before, after = stats[kind]
        if n:
            print(f"{label}: {n} файлов, {before/1e6:.1f} МБ → {after/1e6:.1f} МБ "
                  f"(-{100 * (1 - after / max(before, 1)):.0f}%)")
        else:
            print(f"{label}: оптимизировать нечего")
    print(f"{mode}. Пропущено (уже оптимально/svg): {skipped}, ошибок: {errors}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
