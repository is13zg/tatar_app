# -*- coding: utf-8 -*-
"""Генерация картинки слова через Cloudflare Workers AI (flux-1-schnell) из админки.

Промпт по умолчанию строится как в tools/gen_images.py: английская глосса из EN_GLOSS
(русские промпты рисуют не то) + CF-шаблон без слова «book» (иначе появляются подписи).
EN_GLOSS подгружается из tools/gen_images.py — единый источник, без дублирования.
"""
import base64
import importlib.util
import os
from pathlib import Path

import httpx

PROMPT_EN_CF = (
    "cute flat illustration for a children's app: {en}. "
    "single subject centered, plain white background, bright saturated colors, "
    "kawaii cartoon style, absolutely no text, no letters, no words, no captions"
)

_gloss: dict | None = None


def _en_gloss() -> dict:
    global _gloss
    if _gloss is None:
        path = Path(__file__).resolve().parent.parent / "tools" / "gen_images.py"
        try:
            spec = importlib.util.spec_from_file_location("_gen_images_glossary", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # модуль import-safe: main() под __main__
            _gloss = dict(mod.EN_GLOSS)
        except Exception:
            _gloss = {}
    return _gloss


def default_prompt(text_ru: str) -> str:
    en = _en_gloss().get((text_ru or "").lower())
    return PROMPT_EN_CF.format(en=en or text_ru)


async def generate_cf(prompt: str) -> bytes:
    token = os.getenv("CF_API_TOKEN")
    acct = os.getenv("CF_ACCOUNT_ID")
    if not token or not acct:
        raise RuntimeError("не настроены CF_API_TOKEN/CF_ACCOUNT_ID на сервере")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    async with httpx.AsyncClient(timeout=90) as client:
        last_err: Exception | None = None
        for attempt in range(2):
            try:
                r = await client.post(url, headers={"Authorization": f"Bearer {token}"},
                                      json={"prompt": prompt, "steps": 8})
                if r.status_code == 429:
                    raise RuntimeError("лимит Cloudflare (429) — попробуйте через минуту")
                r.raise_for_status()
                return base64.b64decode(r.json()["result"]["image"])
            except Exception as e:
                last_err = e
        raise RuntimeError(str(last_err))
