# -*- coding: utf-8 -*-
"""Генерация детских иллюстраций для слов без картинок.

Провайдеры:
  fusionbrain — Kandinsky от Сбера, БЕСПЛАТНЫЙ ключ: https://fusionbrain.ai/docs/
                env: FB_KEY, FB_SECRET
  openai      — gpt-image-1, платный. env: OPENAI_API_KEY

Скрипт берёт слова без картинок через API приложения и загружает готовые
изображения обратно через /admin/word_image/{id} — работает и с локальным,
и с боевым сервером.

Примеры:
  python tools/gen_images.py --app http://127.0.0.1:8001 --password admin217 --dry-run
  FB_KEY=... FB_SECRET=... python tools/gen_images.py --app http://127.0.0.1:8001 --password ... --limit 20
"""
import argparse
import base64
import io
import json
import os
import sys
import time

import httpx

PROMPT = (
    "Яркая плоская иллюстрация для детской обучающей игры: {ru}. "
    "Один крупный объект по центру, простой светлый фон, добрый стиль детской книги, "
    "насыщенные цвета, без текста и букв."
)


def login(app: str, user: str, password: str) -> dict:
    r = httpx.post(f"{app}/auth/login", data={"username": user, "password": password}, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def words_without_images(app: str, headers: dict, theme_filter: int | None) -> list[dict]:
    themes = httpx.get(f"{app}/themes", headers=headers, timeout=30).json()
    result = []
    for t in themes:
        if theme_filter and t["id"] != theme_filter:
            continue
        words = httpx.get(f"{app}/themes/{t['id']}/words", headers=headers, timeout=30).json()
        for w in words:
            if not w.get("image_url") or "noimg" in (w.get("image_url") or ""):
                w["theme_title"] = t["title_ru"]
                result.append(w)
    return result


# ---------- FusionBrain (Kandinsky) ----------

FB_URL = "https://api-key.fusionbrain.ai"


class FusionBrain:
    def __init__(self) -> None:
        key, secret = os.getenv("FB_KEY"), os.getenv("FB_SECRET")
        if not key or not secret:
            sys.exit("Нужны env-переменные FB_KEY и FB_SECRET (бесплатно: https://fusionbrain.ai/docs/)")
        self.headers = {"X-Key": f"Key {key}", "X-Secret": f"Secret {secret}"}
        pipelines = httpx.get(f"{FB_URL}/key/api/v1/pipelines", headers=self.headers, timeout=30).json()
        self.pipeline_id = pipelines[0]["id"]

    def generate(self, prompt: str) -> bytes:
        params = {
            "type": "GENERATE",
            "numImages": 1,
            "width": 512,
            "height": 512,
            "generateParams": {"query": prompt},
        }
        files = {
            "pipeline_id": (None, self.pipeline_id),
            "params": (None, json.dumps(params), "application/json"),
        }
        r = httpx.post(f"{FB_URL}/key/api/v1/pipeline/run", headers=self.headers, files=files, timeout=60)
        r.raise_for_status()
        uuid = r.json()["uuid"]
        for _ in range(60):
            time.sleep(3)
            st = httpx.get(f"{FB_URL}/key/api/v1/pipeline/status/{uuid}", headers=self.headers, timeout=30).json()
            if st.get("status") == "DONE":
                return base64.b64decode(st["result"]["files"][0])
            if st.get("status") == "FAIL":
                raise RuntimeError(f"FusionBrain FAIL: {st}")
        raise TimeoutError("FusionBrain: генерация не завершилась за 3 минуты")


# ---------- OpenAI ----------

class OpenAIImages:
    def __init__(self) -> None:
        self.key = os.getenv("OPENAI_API_KEY")
        if not self.key:
            sys.exit("Нужна env-переменная OPENAI_API_KEY")

    def generate(self, prompt: str) -> bytes:
        r = httpx.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {self.key}"},
            json={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024", "quality": "low"},
            timeout=120,
        )
        r.raise_for_status()
        return base64.b64decode(r.json()["data"][0]["b64_json"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="http://127.0.0.1:8001")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--provider", choices=["fusionbrain", "openai"], default="fusionbrain")
    ap.add_argument("--theme", type=int, help="только одна тема (id)")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--delay", type=float, default=1.0, help="пауза между генерациями, сек")
    ap.add_argument("--dry-run", action="store_true", help="только показать, что будет сгенерировано")
    args = ap.parse_args()

    headers = login(args.app, args.user, args.password)
    todo = words_without_images(args.app, headers, args.theme)[: args.limit]
    print(f"Слов без картинок: {len(todo)}")
    if args.dry_run:
        for w in todo[:30]:
            print(f"  [{w['theme_title']}] {w['text_ru']} — {w['text_tt']}")
        return

    provider = FusionBrain() if args.provider == "fusionbrain" else OpenAIImages()
    ok, fail = 0, 0
    for i, w in enumerate(todo, 1):
        prompt = PROMPT.format(ru=w["text_ru"])
        try:
            png = provider.generate(prompt)
            files = {"file": (f"word_{w['id']}.png", io.BytesIO(png), "image/png")}
            r = httpx.post(f"{args.app}/admin/word_image/{w['id']}", headers=headers, files=files, timeout=60)
            r.raise_for_status()
            ok += 1
            print(f"[{i}/{len(todo)}] ✅ {w['text_ru']} — {w['text_tt']}")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(todo)}] ❌ {w['text_ru']}: {e}")
            if fail >= 5:
                print("Слишком много ошибок подряд — останавливаюсь.")
                break
        time.sleep(args.delay)
    print(f"Готово: {ok} ок, {fail} ошибок")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
