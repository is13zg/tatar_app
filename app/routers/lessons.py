import json
import math
import random
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user
from ..database import get_db
from ..qneg import QUESTION_THEMES as QNEG_THEMES
from ..models import (
    User, Theme, Word, UserProgress, UserMistake,
    UnitProgress, DailyLesson, UserSticker, LessonResult,
)
from sqlalchemy import func

router = APIRouter(prefix="/lesson", tags=["lessons"])

NEW_WORDS_PER_LESSON = 4
SRS_INTERVALS_DAYS = [0, 1, 2, 4, 7, 14, 30]  # индекс = strength
MAX_STRENGTH = len(SRS_INTERVALS_DAYS) - 1
KAZAN_UTC_OFFSET = timedelta(hours=3)
STREAK_STICKERS = {3: "🔥", 7: "⭐", 14: "🏆", 30: "👑"}
BOSS_QUESTIONS = 10
DAILY_REVIEW_LIMIT = 12

# Слова-категории: в «выбери картинку» среди слов своей темы у них нет
# единственного правильного ответа («хайван» среди четырёх животных).
CATEGORY_TT = {"хайван", "кош", "бөҗәк", "ашамлык", "кием", "аяк киеме", "савыт-саба", "төс"}

# Темы-«фразники»: слова учим только через карточки, звучание и повторение за диктором —
# выбор картинки для «как дела?» бессмыслен.
PHRASE_THEMES = {"Привет и пока", "Давай знакомиться", "Вежливые слова"}

# Дневной лимит НОВЫХ слов: методист — «очередь повторений растёт лавинообразно».
NEW_WORDS_DAILY_LIMIT = 10

# Пары тем с пересекающейся семантикой — сортировка по корзинам между ними неоднозначна.
SORT_INCOMPATIBLE = {
    frozenset({"Овощи", "Продукты и напитки"}),
    frozenset({"Овощи", "Блюда и вкусы"}),
    frozenset({"Фрукты/ягоды", "Продукты и напитки"}),
    frozenset({"Фрукты/ягоды", "Блюда и вкусы"}),
    frozenset({"Продукты и напитки", "Блюда и вкусы"}),
    frozenset({"Цифры", "Числа (10–19)"}),
    frozenset({"Цифры", "Десятки"}),
    frozenset({"Числа (10–19)", "Десятки"}),
    frozenset({"Моё тело", "Одежда и обувь"}),
    frozenset({"Лицо и голова", "Одежда и обувь"}),
    frozenset({"Моё тело", "Лицо и голова"}),
    frozenset({"Время и сезоны", "Дни недели"}),
    frozenset({"Вещи в доме", "Школа и урок"}),
    frozenset({"Вещи в доме", "Продукты и напитки"}),
    frozenset({"Вещи в доме", "Блюда и вкусы"}),
    frozenset({"Семья и наш дом", "Вещи в доме"}),
    frozenset({"Школа и урок", "Пенал и рюкзак"}),
    frozenset({"Действия: движемся", "Действия: говорим и думаем"}),
    frozenset({"Действия: движемся", "Действия: играем и мастерим"}),
    frozenset({"Действия: говорим и думаем", "Действия: играем и мастерим"}),
}

# Минимальные пары, неразличимые для новичка на слух, — не ставить дистракторами друг к другу.
CONFUSABLE_TT = {
    frozenset({"тел", "теш"}),
    frozenset({"иртә", "иртәгә"}),
    frozenset({"каймак", "коймак"}),
    frozenset({"укытучы", "укучы"}),
    frozenset({"каләм", "кылкаләм"}),
    frozenset({"кабак", "ташкабак"}),
    frozenset({"сау бул", "сау булыгыз"}),
    frozenset({"кич", "кичә"}),
    frozenset({"чеби", "чебен"}),
    frozenset({"чебен", "черки"}),
    frozenset({"чеби", "черки"}),
    frozenset({"сары", "сарык"}),
    frozenset({"миңа биш яшь", "миңа алты яшь"}),
    frozenset({"миңа алты яшь", "миңа җиде яшь"}),
    frozenset({"миңа биш яшь", "миңа җиде яшь"}),
    # глаголы 3-го лица (список эксперта): минимальные пары и структурные дубли
    frozenset({"эшли", "эзли"}),
    frozenset({"көтә", "китә"}),
    frozenset({"килә", "китә"}),
    frozenset({"кисә", "китә"}),
    frozenset({"кисә", "килә"}),
    frozenset({"бара", "торып баса"}),
    frozenset({"ала", "ача"}),
    frozenset({"ала", "сатып ала"}),
    frozenset({"оча", "ача"}),
    frozenset({"ача", "эчә"}),
    frozenset({"оча", "эчә"}),
    frozenset({"ята", "яба"}),
    frozenset({"яза", "ята"}),
    frozenset({"яза", "яба"}),
    frozenset({"таба", "яба"}),
    frozenset({"бирә", "белә"}),
    frozenset({"бирә", "җавап бирә"}),
    frozenset({"керә", "килә"}),
    frozenset({"керә", "сикерә"}),
    frozenset({"аңлый", "тыңлый"}),
    frozenset({"басып тора", "торып баса"}),
    frozenset({"утыра", "тын гына утыра"}),
    frozenset({"сорый", "карый"}),
    frozenset({"ашый", "ясый"}),
    frozenset({"ясый", "яши"}),
    frozenset({"ясый", "рәсем ясый"}),
    frozenset({"уйный", "уйлый"}),
    frozenset({"уйный", "буйый"}),
    frozenset({"буйый", "уйлый"}),
    frozenset({"сикерә", "йөгерә"}),
    frozenset({"йөри", "йөгерә"}),
    frozenset({"йөри", "йөзә"}),
    frozenset({"йөгерә", "йөзә"}),
    frozenset({"куя", "юа"}),
    frozenset({"ярдәм итә", "әйтә"}),
    frozenset({"белә", "килә"}),
    frozenset({"оныта", "утыра"}),
    frozenset({"ята", "ярата"}),
    frozenset({"ярдәм ит", "ярдәм итә"}),
}


def confusable(a: str, b: str) -> bool:
    return frozenset({a.strip().lower(), b.strip().lower()}) in CONFUSABLE_TT


def now_utc() -> datetime:
    return datetime.utcnow()


def today_str() -> str:
    return (now_utc() + KAZAN_UTC_OFFSET).date().isoformat()


def word_dto(w: Word) -> dict:
    return {
        "id": w.id,
        "theme_id": w.theme_id,
        "text_tt": w.text_tt,
        "text_ru": w.text_ru,
        "image_url": w.image_url,
        "emoji": w.emoji,
        "audio_url": w.audio_url or w.tts_url,
        "sentence_tt": w.sentence_tt,
        "sentence_ru": w.sentence_ru,
        "sentence_audio_url": w.sentence_audio_url,
    }


_token_re = None


def sentence_tokens(sentence: str) -> list[str]:
    """Слова предложения без знаков препинания (для конструктора)."""
    import re
    return [t for t in re.split(r"[^\wәөүҗңһӘӨҮҖҢҺ-]+", sentence) if t]


def lessons_total_for(word_count: int) -> int:
    return max(1, math.ceil(word_count / NEW_WORDS_PER_LESSON)) + 1  # + босс


async def get_ordered_units(db: AsyncSession) -> list[Theme]:
    return (await db.execute(select(Theme).order_by(Theme.order_index, Theme.id))).scalars().all()


async def unit_words(db: AsyncSession, theme_id: int) -> list[Word]:
    return (await db.execute(select(Word).where(Word.theme_id == theme_id).order_by(Word.id))).scalars().all()


async def word_counts_by_theme(db: AsyncSession) -> dict[int, int]:
    rows = (await db.execute(select(Word.theme_id, func.count(Word.id)).group_by(Word.theme_id))).all()
    return {theme_id: cnt for theme_id, cnt in rows}


# ---------- генераторы упражнений ----------

def _has_photo(w: dict) -> bool:
    """У слова настоящая картинка (а не эмодзи-заглушка)."""
    img = w.get("image_url")
    return bool(img and "noimg" not in img)


def visual_key(w: dict) -> str:
    """Как слово выглядит для ребёнка: картинка или эмодзи-заглушка.
    Упражнения с выбором по картинке обязаны различать варианты именно по этому ключу."""
    if _has_photo(w):
        return f"img:{w['image_url']}"
    return f"emoji:{w.get('emoji') or '?'}"


def distinct_visual_sample(target: dict, pool: list[dict], n: int) -> Optional[list[dict]]:
    """n дистракторов, визуально отличных от цели и друг от друга.
    Предпочитаем один и тот же формат плитки (фото/эмодзи), что и у цели: иначе
    правильный ответ угадывается по «непохожести» тайла, а не по знанию слова."""
    seen = {visual_key(target)}
    cands = [p for p in pool if p["id"] != target["id"]]
    random.shuffle(cands)
    tgt_photo = _has_photo(target)
    cands.sort(key=lambda p: _has_photo(p) != tgt_photo)  # свой формат — вперёд, чужой — добор
    out: list[dict] = []
    for p in cands:
        k = visual_key(p)
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
        if len(out) == n:
            return out
    return None


def ex_card(w: dict) -> dict:
    return {"type": "card", "word": w}


# «Презентационные» мини-игры подачи слова (уроки 1-2, без оценки, провал невозможен).
# color_reveal/grow_reveal убраны из ротации по просьбе владельца («просто нажимай» —
# слишком статичны); рендереры на фронте оставлены, форматы можно вернуть одной строкой.

def ex_surprise_box(w: dict) -> dict:
    return {"type": "surprise_box", "word": w}


def ex_shadow_reveal(w: dict) -> dict:
    return {"type": "shadow_reveal", "word": w}


def ex_color_reveal(w: dict) -> dict:
    return {"type": "color_reveal", "word": w}


def ex_grow_reveal(w: dict) -> dict:
    return {"type": "grow_reveal", "word": w}


PRESENTERS = [ex_card, ex_surprise_box, ex_shadow_reveal]


def ex_pick_image(target: dict, pool: list[dict]) -> Optional[dict]:
    if not target["audio_url"]:
        return None  # упражнение звуковое — без озвучки бессмысленно
    if target["text_tt"].lower() in CATEGORY_TT:
        return None  # у слова-категории нет единственной правильной картинки в своей теме
    safe_pool = [p for p in pool
                 if p["text_tt"].lower() not in CATEGORY_TT
                 and not confusable(p["text_tt"], target["text_tt"])]
    distractors = distinct_visual_sample(target, safe_pool, 3)
    if not distractors:
        return None
    options = distractors + [target]
    random.shuffle(options)
    return {
        "type": "pick_image",
        "word_id": target["id"],
        "text_tt": target["text_tt"],
        "audio_url": target["audio_url"],
        "options": [{"id": o["id"], "image_url": o["image_url"], "emoji": o["emoji"]} for o in options],
    }


def ex_yes_no(target: dict, pool: list[dict]) -> Optional[dict]:
    if not target["audio_url"]:
        return None
    if target["text_tt"].lower() in CATEGORY_TT:
        return None
    is_match = random.random() < 0.5
    shown = target
    if not is_match:
        safe_pool = [p for p in pool
                     if p["text_tt"].lower() not in CATEGORY_TT
                     and not confusable(p["text_tt"], target["text_tt"])]
        others = distinct_visual_sample(target, safe_pool, 1)
        if not others:
            is_match = True  # нет визуально отличного «чужого» — показываем правильную картинку
        else:
            shown = others[0]
    return {
        "type": "yes_no",
        "word_id": target["id"],
        "text_tt": target["text_tt"],
        "audio_url": target["audio_url"],
        "shown": {"id": shown["id"], "image_url": shown["image_url"], "emoji": shown["emoji"]},
        "is_match": is_match,
    }


def ex_memory(words: list[dict]) -> Optional[dict]:
    # только озвученные и визуально различимые слова — иначе пары немые/неразличимые
    voiced = [w for w in words if w["audio_url"]]
    pairs: list[dict] = []
    seen: set[str] = set()
    random.shuffle(voiced)
    for w in voiced:
        k = visual_key(w)
        if k in seen:
            continue
        seen.add(k)
        pairs.append(w)
        if len(pairs) == 3:
            break
    if len(pairs) < 3:
        return None
    return {"type": "memory", "pairs": [
        {"word_id": p["id"], "text_tt": p["text_tt"], "audio_url": p["audio_url"],
         "image_url": p["image_url"], "emoji": p["emoji"]} for p in pairs
    ]}


def ex_pick_word_audio(target: dict, pool: list[dict]) -> Optional[dict]:
    distractors = [
        p for p in pool
        if p["id"] != target["id"] and p["audio_url"] and not confusable(p["text_tt"], target["text_tt"])
    ]
    if not target["audio_url"] or len(distractors) < 2:
        return None
    options = random.sample(distractors, 2) + [target]
    random.shuffle(options)
    return {
        "type": "pick_word_audio",
        "word_id": target["id"],
        "shown": {"image_url": target["image_url"], "emoji": target["emoji"], "text_ru": target["text_ru"]},
        "options": [{"id": o["id"], "audio_url": o["audio_url"], "text_tt": o["text_tt"]} for o in options],
    }


def ex_build_word(target: dict) -> Optional[dict]:
    word = target["text_tt"].strip().lower()
    if not (3 <= len(word) <= 5) or " " in word or "-" in word or "?" in word:
        return None
    letters = list(word)
    random.shuffle(letters)
    return {
        "type": "build_word",
        "word_id": target["id"],
        "text_tt": word,
        "audio_url": target["audio_url"],
        "image_url": target["image_url"],
        "emoji": target["emoji"],
        "letters": letters,
    }


def ex_repeat_after(target: dict) -> dict:
    return {"type": "repeat_after", "word": target}


# ---- вторая волна мини-игр (по отчёту геймдизайнера) ----

def ex_bubbles(target: dict, pool: list[dict]) -> Optional[dict]:
    """Пузыри: как pick_image, но цели плавают — лопни пузырь с названным словом."""
    e = ex_pick_image(target, pool)
    if not e:
        return None
    e = dict(e)
    e["type"] = "bubbles"
    return e


def ex_feed(target: dict, pool: list[dict]) -> Optional[dict]:
    """Покорми Акбая: щенок просит слово голосом — дай ему правильный предмет (из 3)."""
    e = ex_pick_image(target, pool)
    if not e:
        return None
    distractors = [o for o in e["options"] if o["id"] != target["id"]][:2]
    options = distractors + [{"id": target["id"], "image_url": target["image_url"], "emoji": target["emoji"]}]
    random.shuffle(options)
    return {
        "type": "feed",
        "word_id": target["id"],
        "text_tt": target["text_tt"],
        "audio_url": target["audio_url"],
        "options": options,
    }


def ex_who_ran(pool: list[dict]) -> Optional[dict]:
    """Кто убежал: 3 картинки показываются и озвучиваются, одна исчезает — вспомни какая."""
    cands = [w for w in pool if w["audio_url"] and w["text_tt"].lower() not in CATEGORY_TT]
    seen: set[str] = set()
    trio: list[dict] = []
    random.shuffle(cands)
    for w in cands:
        k = visual_key(w)
        if k in seen:
            continue
        seen.add(k)
        trio.append(w)
        if len(trio) == 3:
            break
    if len(trio) < 3:
        return None
    missing = random.choice(trio)
    outsiders = [w for w in cands
                 if w["id"] not in {t["id"] for t in trio}
                 and visual_key(w) not in seen
                 and not confusable(w["text_tt"], missing["text_tt"])]
    if not outsiders:
        return None
    brief = lambda w: {"id": w["id"], "image_url": w["image_url"], "emoji": w["emoji"],
                       "audio_url": w["audio_url"], "text_tt": w["text_tt"]}
    options = [brief(missing), brief(random.choice(outsiders))]
    random.shuffle(options)
    return {
        "type": "who_ran",
        "word_id": missing["id"],
        "shown": [brief(w) for w in trio],
        "missing_id": missing["id"],
        "options": options,
    }


def ex_moles(target: dict, pool: list[dict]) -> Optional[dict]:
    """Кротовые норки (go/no-go): лови только названное слово, чужих пропускай."""
    if not target["audio_url"] or target["text_tt"].lower() in CATEGORY_TT:
        return None
    others = [p for p in pool
              if p["id"] != target["id"]
              and visual_key(p) != visual_key(target)
              and not confusable(p["text_tt"], target["text_tt"])]
    if len(others) < 2:
        return None
    appearances = [target] * 3 + random.sample(others, min(4, len(others)))
    random.shuffle(appearances)
    seq = [{"id": w["id"], "image_url": w["image_url"], "emoji": w["emoji"],
            "is_target": w["id"] == target["id"], "hole": random.randrange(4)} for w in appearances]
    return {
        "type": "moles",
        "word_id": target["id"],
        "text_tt": target["text_tt"],
        "audio_url": target["audio_url"],
        "seq": seq,
    }


def with_sentence_audio(e: Optional[dict], target: dict) -> Optional[dict]:
    """Вариант упражнения, где вместо слова звучит предложение с ним."""
    if not e or not target.get("sentence_audio_url"):
        return e
    e = dict(e)
    e["audio_url"] = target["sentence_audio_url"]
    e["text_tt"] = target["sentence_tt"]
    e["sentence_mode"] = True
    return e


# Противоположности (по книге «Сүзләр дөньясы», раздел «Капма-каршылык»)
OPPOSITES_TT = {
    "зур": "нәни", "нәни": "зур",
    "озын": "кыска", "кыска": "озын",
    "кайнар": "салкын", "салкын": "кайнар",
    "тәмле": "тәмсез", "тәмсез": "тәмле",
    "ак": "кара", "кара": "ак",
    "көн": "төн", "төн": "көн",
}


# Темы-категории, где «найди лишнее» осмысленно для нечитающего: ребёнок видит
# 3 картинки «про одно» и 1 «не про то». На темах-НЕ-категориях (цвета, местоимения,
# действия…) единой перцептивной группы нет и «лишнее» неопределимо — там odd_one не даём.
ODD_ONE_CATEGORY_THEMES = {
    "Животные: дома и во дворе",
    "Животные: в лесу и зоопарке",
    "Фрукты/ягоды",
    "Овощи",
    "Птицы, рыбки, букашки",
    "Одежда и обувь",
    "Продукты и напитки",
    "Вещи в доме",
    "Пенал и рюкзак",
}

# «Покорми Акбая» осмысленно только на съедобном: щенка кормят едой, а не овцой/коровой.
# На остальных темах закрепление даёт обычный «найди картинку».
EDIBLE_THEMES = {
    "Продукты и напитки",
    "Фрукты/ягоды",
    "Овощи",
    "Блюда и вкусы",
}


def ex_opposite(target: dict, pool: list[dict], known_pool: list[dict]) -> Optional[dict]:
    """Найди наоборот: звучит слово — выбери картинку противоположности.
    Партнёр-антоним берётся только из уже знакомых ребёнку слов (known_pool): у формата
    нет экспозиции, и картинка ещё не пройденного слова была бы неразрешима не угадыванием."""
    partner_tt = OPPOSITES_TT.get(target["text_tt"].lower())
    if not partner_tt or not target["audio_url"]:
        return None
    partner = next((p for p in known_pool if p["text_tt"].lower() == partner_tt), None)
    if not partner:
        return None
    # дистракторы не должны содержать ДРУГИХ контрастных слов (короткий как «наоборот» большому)
    distractor_pool = [p for p in pool
                       if p["text_tt"].lower() != target["text_tt"].lower()
                       and p["text_tt"].lower() not in OPPOSITES_TT]
    e = ex_pick_image(partner, distractor_pool)
    if not e:
        return None
    e = dict(e)
    e["type"] = "pick_image"
    e["opposite_mode"] = True
    e["text_tt"] = target["text_tt"]      # показываем/озвучиваем исходное слово
    e["audio_url"] = target["audio_url"]  # правильный ответ — картинка противоположности (word_id = partner)
    e["source"] = {"id": target["id"], "image_url": target["image_url"],
                   "emoji": target["emoji"]}  # якорь: картинка исходного слова, от которого ищем «наоборот»
    return e


def ex_odd_one(pool: list[dict], other_words: list[dict]) -> Optional[dict]:
    """Что лишнее: 3 слова темы + 1 чужое (по книге, «Рәсемнәргә туры килми торган сүзләрне тап»).
    Все 4 плитки — одного формата (фото/эмодзи), «лишнее» не созвучно трио: чтобы задачу
    нельзя было решить по типу тайла или на слух, только по смыслу."""
    voiced = [w for w in pool if w["audio_url"] and w["text_tt"].lower() not in CATEGORY_TT]
    random.shuffle(voiced)
    seen: set[str] = set()
    photos: list[dict] = []
    emojis: list[dict] = []
    for w in voiced:
        k = visual_key(w)
        if k in seen:
            continue
        seen.add(k)
        (photos if _has_photo(w) else emojis).append(w)
    group = photos if len(photos) >= 3 else emojis  # трио одного формата
    if len(group) < 3:
        return None
    trio = random.sample(group, 3)
    want_photo = _has_photo(trio[0])
    trio_keys = {visual_key(w) for w in trio}
    odd_cands = [w for w in other_words
                 if w["audio_url"] and _has_photo(w) == want_photo
                 and visual_key(w) not in trio_keys
                 and w["text_tt"].lower() not in CATEGORY_TT
                 and not any(confusable(w["text_tt"], t["text_tt"]) for t in trio)]
    if not odd_cands:
        return None
    odd = random.choice(odd_cands)
    options = [_brief(w) for w in trio] + [_brief(odd)]
    random.shuffle(options)
    return {"type": "odd_one", "word_id": odd["id"], "options": options}


# ---- третья волна мини-игр (остаток отчёта геймдизайнера) ----

def _brief(w: dict) -> dict:
    return {"id": w["id"], "image_url": w["image_url"], "emoji": w["emoji"],
            "audio_url": w["audio_url"], "text_tt": w["text_tt"]}


def _distinct_voiced(pool: list[dict], n: int, exclude_tt: Optional[str] = None) -> Optional[list[dict]]:
    cands = [w for w in pool if w["audio_url"] and w["text_tt"].lower() not in CATEGORY_TT
             and (exclude_tt is None or not confusable(w["text_tt"], exclude_tt))]
    seen: set[str] = set()
    out: list[dict] = []
    random.shuffle(cands)
    for w in cands:
        k = visual_key(w)
        if k in seen:
            continue
        seen.add(k)
        out.append(w)
        if len(out) == n:
            return out
    return None


def ex_windows(pool: list[dict]) -> Optional[dict]:
    """Окошки: 4 ставни открываются и озвучиваются, закрываются — «где X?»."""
    quad = _distinct_voiced(pool, 4)
    if not quad:
        return None
    target = random.choice(quad)
    return {"type": "windows", "word_id": target["id"],
            "items": [_brief(w) for w in quad]}


def ex_flashlight(target: dict, pool: list[dict]) -> Optional[dict]:
    """Фонарик: картинка в темноте, свети пальцем, потом выбери из 3, кто прятался."""
    e = ex_pick_image(target, pool)
    if not e:
        return None
    distractors = [o for o in e["options"] if o["id"] != target["id"]][:2]
    options = distractors + [{"id": target["id"], "image_url": target["image_url"], "emoji": target["emoji"]}]
    random.shuffle(options)
    return {"type": "flashlight", "word_id": target["id"],
            "target": _brief(target), "options": options}


def ex_chain(pool: list[dict]) -> Optional[dict]:
    """Повтори цепочку (Саймон): последовательность из 3 слов, повтори тапами."""
    trio = _distinct_voiced(pool, 3)
    if not trio:
        return None
    chain: list[int] = []
    while len(chain) < 3:
        c = random.randrange(3)
        if chain and chain[-1] == c:
            continue
        chain.append(c)
    return {"type": "chain", "word_id": trio[chain[0]]["id"],
            "items": [_brief(w) for w in trio], "chain": chain}


def ex_build_sentence(target: dict, pool: list[dict]) -> Optional[dict]:
    """Собери предложение из слов-плиток (с ловушками)."""
    from ..tts import cached_tts_url
    if not target.get("sentence_tt") or not target.get("sentence_audio_url"):
        return None
    tokens = sentence_tokens(target["sentence_tt"])
    if not 2 <= len(tokens) <= 5:
        return None
    lower_tokens = {t.lower() for t in tokens}
    audio_by_tt = {p["text_tt"].lower(): p["audio_url"] for p in pool if p["audio_url"]}

    def token_audio(tok: str) -> Optional[str]:
        return audio_by_tt.get(tok.lower()) or cached_tts_url(tok.lower())

    correct = [{"text": t, "audio_url": token_audio(t)} for t in tokens]
    if any(c["audio_url"] is None for c in correct):
        return None  # плитка обязана звучать по тапу — немой конструктор бесполезен нечитающему
    # ловушки: 1-2 однословных слова темы, не из предложения и не созвучные с целью
    cands = [p for p in pool
             if " " not in p["text_tt"] and p["audio_url"]
             and p["text_tt"].lower() not in lower_tokens
             and not confusable(p["text_tt"], target["text_tt"])]
    random.shuffle(cands)
    traps = [{"text": p["text_tt"], "audio_url": p["audio_url"]} for p in cands[:2]]
    if not traps:
        return None
    tiles = correct + traps
    random.shuffle(tiles)
    return {
        "type": "build_sentence",
        "word_id": target["id"],
        "image_url": target["image_url"],
        "emoji": target["emoji"],
        "audio_url": target["sentence_audio_url"],
        "sentence_ru": target["sentence_ru"],
        "tokens": tokens,
        "tiles": tiles,
    }


# ---- вопросы и отрицания: «Бу песиме?» / «Бу песи түгел» (формы: app/qneg.py) ----

def _qneg_ready(target: dict) -> bool:
    """Слово годится и его вопрос/отрицание предозвучены (tools/gen_qneg_tts.py)."""
    from ..qneg import qneg_eligible, question_phrase
    from ..tts import cached_tts_url
    return (bool(target["audio_url"]) and target["text_tt"].lower() not in CATEGORY_TT
            and qneg_eligible(target["text_tt"])
            and cached_tts_url(question_phrase(target["text_tt"])) is not None)


def ex_question(target: dict, pool: list[dict]) -> Optional[dict]:
    """Ответь на вопрос: звучит «Бу песиме?», картинка совпадает или нет — Әйе/Юк.
    При несовпадении ребёнок слышит поправку: «Бу песи түгел» + имя показанного."""
    from ..qneg import AYE, YUK, negation_phrase, question_phrase
    from ..tts import cached_tts_url
    if not _qneg_ready(target):
        return None
    q_url = cached_tts_url(question_phrase(target["text_tt"]))
    aye, yuk = cached_tts_url(AYE), cached_tts_url(YUK)
    if not q_url or not aye or not yuk:
        return None
    is_match = random.random() < 0.5
    shown = target
    if not is_match:
        safe_pool = [p for p in pool
                     if p["text_tt"].lower() not in CATEGORY_TT and p["audio_url"]
                     and not confusable(p["text_tt"], target["text_tt"])]
        others = distinct_visual_sample(target, safe_pool, 1)
        if not others:
            is_match = True
        else:
            shown = others[0]
    return {
        "type": "question",
        "word_id": target["id"],
        "text_tt": question_phrase(target["text_tt"]),
        "audio_url": q_url,
        "is_match": is_match,
        "shown": {"id": shown["id"], "image_url": shown["image_url"], "emoji": shown["emoji"]},
        "aye_audio": aye,
        "yuk_audio": yuk,
        "neg_audio": cached_tts_url(negation_phrase(target["text_tt"])),
        "shown_audio": shown["audio_url"],  # поправка: «Бу X түгел» + кто на самом деле
    }


def ex_build_qneg(target: dict, pool: list[dict]) -> Optional[dict]:
    """Собери вопрос или отрицание из плиток: «Бу песиме?» / «Бу песи түгел».
    Ловушка — обычная форма слова («песи» рядом с «песиме»): учит замечать частицу."""
    from ..qneg import BU, TUGEL, negation_phrase, question_phrase, question_word
    from ..tts import cached_tts_url
    if not _qneg_ready(target):
        return None
    bu, tugel = cached_tts_url(BU), cached_tts_url(TUGEL)
    qw = cached_tts_url(question_word(target["text_tt"]))
    word_lower = target["text_tt"].lower()
    plain = target["audio_url"]
    if not bu or not tugel or not qw:
        return None
    if random.random() < 0.5:
        # вопрос: Бу песиме? (картинка совпадает — спрашиваем про неё)
        phrase = question_phrase(target["text_tt"])
        tokens = ["Бу", question_word(target["text_tt"])]
        tiles = [{"text": "Бу", "audio_url": bu},
                 {"text": question_word(target["text_tt"]), "audio_url": qw},
                 {"text": word_lower, "audio_url": plain}]  # ловушка: слово без частицы
        shown = target
        sentence_ru = f"Это {target['text_ru']}?"
    else:
        # отрицание: Бу песи түгел — на картинке ДРУГОЕ слово
        safe_pool = [p for p in pool
                     if p["text_tt"].lower() not in CATEGORY_TT and p["audio_url"]
                     and not confusable(p["text_tt"], target["text_tt"])]
        others = distinct_visual_sample(target, safe_pool, 1)
        if not others:
            return None
        shown = others[0]
        phrase = negation_phrase(target["text_tt"])
        tokens = ["Бу", word_lower, TUGEL]
        tiles = [{"text": "Бу", "audio_url": bu},
                 {"text": word_lower, "audio_url": plain},
                 {"text": TUGEL, "audio_url": tugel},
                 {"text": question_word(target["text_tt"]), "audio_url": qw}]  # ловушка
        sentence_ru = f"Это не {target['text_ru']}."
    full = cached_tts_url(phrase)
    if not full:
        return None
    random.shuffle(tiles)
    return {
        "type": "build_sentence",
        "word_id": target["id"],
        "image_url": shown["image_url"],
        "emoji": shown["emoji"],
        "audio_url": full,
        "sentence_ru": sentence_ru,
        "tokens": tokens,
        "tiles": tiles,
    }


def _distinct_visual_pick(words: list[dict], n: int, seen: set[str]) -> Optional[list[dict]]:
    shuffled = list(words)
    random.shuffle(shuffled)
    out: list[dict] = []
    for w in shuffled:
        k = visual_key(w)
        if k in seen:
            continue
        seen.add(k)
        out.append(w)
        if len(out) == n:
            return out
    return None


def ex_sort_baskets(theme_a: Theme, words_a: list[dict], theme_b: Theme, words_b: list[dict]) -> Optional[dict]:
    seen: set[str] = set()
    pick_a = _distinct_visual_pick(words_a, 2, seen)
    pick_b = _distinct_visual_pick(words_b, 2, seen)
    if not pick_a or not pick_b:
        return None
    items = [
        {"word_id": w["id"], "text_tt": w["text_tt"], "audio_url": w["audio_url"],
         "image_url": w["image_url"], "emoji": w["emoji"], "basket": t.id}
        for t, ws in ((theme_a, pick_a), (theme_b, pick_b)) for w in ws
    ]
    random.shuffle(items)
    return {
        "type": "sort_baskets",
        "baskets": [
            {"id": theme_a.id, "title_ru": theme_a.title_ru, "icon_emoji": theme_a.icon_emoji or "📦"},
            {"id": theme_b.id, "title_ru": theme_b.title_ru, "icon_emoji": theme_b.icon_emoji or "📦"},
        ],
        "items": items,
    }


def _no_three_in_a_row(items: list[dict]) -> list[dict]:
    """Разбавить последовательность: не больше двух одинаковых типов подряд."""
    result = list(items)
    for i in range(2, len(result)):
        if result[i]["type"] == result[i - 1]["type"] == result[i - 2]["type"]:
            for j in range(i + 1, len(result)):
                if result[j]["type"] != result[i]["type"]:
                    result[i], result[j] = result[j], result[i]
                    break
    return result


def build_exercises(new_words: list[dict], pool: list[dict], review_words: list[dict],
                    sort_payload: Optional[dict] = None, phrase_mode: bool = False,
                    allow_build: bool = False, sentences_ok: bool = False,
                    late_unit: bool = False, feed_ok: bool = False,
                    qneg_ok: bool = False) -> list[dict]:
    """Урок: чередование «карточка → сразу практика» + разнообразное закрепление.
    phrase_mode: тема из фраз — только карточки, звучание и повторение за диктором.
    allow_build: «собери слово» — только с 3-го урока юнита (для начала это слишком сложно)."""
    items: list[dict] = []

    if phrase_mode:
        for w in new_words:
            items.append(ex_card(w))
        practice: list[dict] = []
        for w in new_words:
            e = ex_pick_word_audio(w, pool)
            if e:
                practice.append(e)
        for w in new_words:
            if w["audio_url"]:
                practice.append(ex_repeat_after(w))
    else:
        # подача с немедленным закреплением: мини-игра подачи → закрепление на это же слово
        # формат подачи ротируется (карточка/коробка/тень) — разнообразие с урока 1;
        # закрепление со 2-го урока чаще становится игрой («пузыри», «покорми Акбая»)
        start_fmt = random.randrange(len(PRESENTERS))
        for i, w in enumerate(new_words):
            presenter = PRESENTERS[(start_fmt + i) % len(PRESENTERS)]
            items.append(presenter(w))
            e = None
            if sentences_ok:
                r = random.random()
                if r < 0.35:
                    e = ex_bubbles(w, pool)
                elif feed_ok and r < 0.6:  # «покорми Акбая» — только на съедобных темах
                    e = ex_feed(w, pool)
            if not e:
                e = ex_pick_image(w, pool)
            if e:
                items.append(e)
        practice = []
        yn_candidates = [w for w in new_words]
        random.shuffle(yn_candidates)
        for w in yn_candidates[:1]:
            e = ex_yes_no(w, pool)
            if e and sentences_ok and w.get("sentence_audio_url") and random.random() < 0.5:
                e = with_sentence_audio(e, w)  # «Бу — эт» вместо одиночного слова
            if e:
                practice.append(e)
        e = ex_memory(new_words if len(new_words) >= 3 else pool)
        if e:
            practice.append(e)
        pwa_candidates = [w for w in new_words]
        random.shuffle(pwa_candidates)
        for w in pwa_candidates[:1]:
            e = ex_pick_word_audio(w, pool)
            if e:
                practice.append(e)
        # вопрос «Бу X-мы?» с ответом Әйе/Юк — грамматика со 2-го урока предметных тем
        if qneg_ok and sentences_ok:
            for w in random.sample(new_words, len(new_words)):
                e = ex_question(w, pool)
                if e:
                    practice.append(e)
                    break
        if allow_build:
            built = None
            if qneg_ok and random.random() < 0.35:
                # конструктор вопроса/отрицания вместо обычного предложения
                for w in random.sample(new_words, len(new_words)):
                    built = ex_build_qneg(w, pool)
                    if built:
                        break
            if not built and sentences_ok and random.random() < 0.5:
                for w in random.sample(new_words, len(new_words)):
                    built = ex_build_sentence(w, pool)
                    if built:
                        break
            if not built:
                for w in random.sample(new_words, len(new_words)):
                    built = ex_build_word(w)
                    if built:
                        break
            if built:
                practice.append(built)
        # один «бонусный» формат за урок из доступных по уровню — разнообразие без раздувания длины
        extra_gens = []
        known_pool = new_words + review_words  # партнёр-антоним — только из знакомых ребёнку слов
        for w in new_words:
            if w["text_tt"].lower() in OPPOSITES_TT:
                extra_gens.append(lambda w=w: ex_opposite(w, pool, known_pool))
                break
        if sentences_ok:
            extra_gens.append(lambda: ex_windows(pool))
        if allow_build:
            extra_gens.append(lambda: ex_who_ran(pool))
            extra_gens.append(lambda: ex_flashlight(random.choice(new_words), pool))
        if late_unit:
            extra_gens.append(lambda: ex_chain(pool))
            extra_gens.append(lambda: ex_moles(random.choice(new_words), pool))  # «норки» не только в боссе
        random.shuffle(extra_gens)
        # два бонусных игровых формата за урок (было один): больше интерактива по просьбе владельца
        added = 0
        for gen in extra_gens:
            if added >= 2:
                break
            e = gen()
            if e:
                practice.append(e)
                added += 1
        voiced_new = [w for w in new_words if w["audio_url"]]
        random.shuffle(voiced_new)
        for i, w in enumerate(voiced_new[:2]):  # продукция: два «повтори за диктором»
            if late_unit and i == 1 and w.get("sentence_audio_url"):
                s = dict(w)
                s["text_tt"] = w["sentence_tt"]
                s["audio_url"] = w["sentence_audio_url"]
                s["text_ru"] = w["sentence_ru"] or w["text_ru"]
                e = ex_repeat_after(s)
                e["sentence_mode"] = True
                practice.append(e)
            else:
                practice.append(ex_repeat_after(w))
        if sort_payload:
            practice.append(sort_payload)

    # повторение прошлых слов вперемешку (максимум 2 в юнит-уроке — основной канал повторения это задание дня)
    for w in review_words:
        if w.get("phrase"):
            if w["audio_url"]:
                e = ex_repeat_after(w)
            else:
                continue
        else:
            e = ex_pick_image(w, pool + review_words) or ex_yes_no(w, pool + review_words)
        if e:
            e["review"] = True
            practice.append(e)

    random.shuffle(practice)
    return items + _no_three_in_a_row(practice)


# ---------- вспомогательные выборки ----------

async def due_review_words(db: AsyncSession, user: User, limit: int, exclude_theme: Optional[int] = None) -> list[dict]:
    q = (
        select(Word, Theme.title_ru)
        .join(UserProgress, UserProgress.word_id == Word.id)
        .join(Theme, Theme.id == Word.theme_id)
        .where(
            UserProgress.user_id == user.id,
            UserProgress.strength > 0,
            UserProgress.due_at.is_not(None),
            UserProgress.due_at <= now_utc(),
        )
        .order_by(UserProgress.due_at)
        .limit(limit * 2)
    )
    rows = (await db.execute(q)).all()
    result = []
    for w, theme_title in rows:
        if exclude_theme is not None and w.theme_id == exclude_theme:
            continue
        dto = word_dto(w)
        dto["phrase"] = theme_title in PHRASE_THEMES
        result.append(dto)
    return result[:limit]


async def unit_progress_map(db: AsyncSession, user: User) -> dict[int, UnitProgress]:
    rows = (await db.execute(select(UnitProgress).where(UnitProgress.user_id == user.id))).scalars().all()
    return {r.theme_id: r for r in rows}


async def unlocked_theme_ids(db: AsyncSession, user: User) -> set[int]:
    """Пройденные юниты + первый непройденный (защита от прыжков по прямым URL)."""
    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    unlocked: set[int] = set()
    prev_done = True
    for t in units:
        p = progress.get(t.id)
        completed = bool(p and p.completed_at)
        if completed or prev_done:
            unlocked.add(t.id)
        prev_done = completed
    return unlocked


async def compute_streak(db: AsyncSession, user: User) -> int:
    rows = (await db.execute(
        select(DailyLesson.date).where(DailyLesson.user_id == user.id, DailyLesson.completed_at.is_not(None))
    )).all()
    done = {r[0] for r in rows}
    today = (now_utc() + KAZAN_UTC_OFFSET).date()
    streak = 0
    day = today
    if today.isoformat() not in done:
        day = today - timedelta(days=1)  # серия ещё жива, если вчера выполнено
    while day.isoformat() in done:
        streak += 1
        day -= timedelta(days=1)
    return streak


# ---------- endpoints ----------

@router.get("/path")
async def learning_path(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    counts = await word_counts_by_theme(db)
    result = []
    prev_done = True  # первый юнит открыт всегда
    for t in units:
        word_count = counts.get(t.id, 0)
        total = lessons_total_for(word_count)
        p = progress.get(t.id)
        stars = p.stars if p else 0
        lessons_done = p.lessons_done if p else 0
        completed = bool(p and p.completed_at)
        if completed:
            state = "done"
        elif prev_done:
            state = "current"
        else:
            state = "locked"
        result.append({
            "theme_id": t.id,
            "title_ru": t.title_ru,
            "title_tt": t.title_tt,
            "icon_emoji": t.icon_emoji or "📚",
            "word_count": word_count,
            "lessons_total": total,
            "lessons_done": min(lessons_done, total),
            "stars": stars,
            "state": state,
        })
        prev_done = completed
    streak = await compute_streak(db, user)
    stickers = (await db.execute(select(UserSticker).where(UserSticker.user_id == user.id))).scalars().all()
    return {"units": result, "streak": streak, "stickers": [s.sticker for s in stickers],
            "is_admin": user.is_admin}


@router.get("/unit/{theme_id}/{lesson_no}")
async def unit_lesson(theme_id: int, lesson_no: int,
                      db: Annotated[AsyncSession, Depends(get_db)],
                      user: Annotated[User, Depends(get_current_user)]):
    theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    # админ проверяет любой урок с карты — все замки и лимиты для него выключены
    if not user.is_admin and theme_id not in await unlocked_theme_ids(db, user):
        raise HTTPException(status_code=403, detail="Этот юнит ещё закрыт")
    words = await unit_words(db, theme_id)
    if not words:
        raise HTTPException(status_code=400, detail="В теме нет слов")
    total = lessons_total_for(len(words))
    lesson_no = max(1, min(lesson_no, total))

    # уроки внутри юнита идут по порядку — босс нельзя открыть первым
    up = (await db.execute(select(UnitProgress).where(
        UnitProgress.user_id == user.id, UnitProgress.theme_id == theme_id
    ))).scalar_one_or_none()
    lessons_done = ((up.lessons_done if up else 0) or 0)
    if not user.is_admin and lesson_no > lessons_done + 1:
        raise HTTPException(status_code=403, detail="Сначала пройди предыдущие уроки")

    # дневной лимит новых слов: очередь повторений не должна расти лавинообразно
    if not user.is_admin and lesson_no == lessons_done + 1:  # первое прохождение этого урока
        kazan_day_start = (now_utc() + KAZAN_UTC_OFFSET).replace(hour=0, minute=0, second=0, microsecond=0) - KAZAN_UTC_OFFSET
        new_today = (await db.execute(
            select(func.count(UserProgress.id)).where(
                UserProgress.user_id == user.id,
                UserProgress.first_seen_at.is_not(None),
                UserProgress.first_seen_at >= kazan_day_start,
            )
        )).scalar_one()
        if new_today >= NEW_WORDS_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="На сегодня хватит новых слов! 🌟 Сделай задание дня или повтори пройденные уроки, а завтра продолжим",
            )

    pool = [word_dto(w) for w in words]
    is_boss = lesson_no == total
    phrase_mode = theme.title_ru in PHRASE_THEMES

    if is_boss:
        # босс: по одному слову из каждого урока + добор случайными до BOSS_QUESTIONS
        sample: list[dict] = []
        for i in range(0, len(pool), NEW_WORDS_PER_LESSON):
            chunk = pool[i:i + NEW_WORDS_PER_LESSON]
            if chunk:
                sample.append(random.choice(chunk))
        seen_ids = {w["id"] for w in sample}
        extra = [w for w in pool if w["id"] not in seen_ids]
        random.shuffle(extra)
        sample += extra[:max(0, BOSS_QUESTIONS - len(sample))]
        random.shuffle(sample)
        sample = sample[:BOSS_QUESTIONS]
        items: list[dict] = []
        for i, w in enumerate(sample):
            if phrase_mode:
                e = ex_pick_word_audio(w, pool)
            else:
                kind = i % 4
                if kind == 0:
                    e = ex_pick_image(w, pool)
                    # в боссе часть заданий звучит предложением — понимание речи, не только слова
                    if e and w.get("sentence_audio_url") and random.random() < 0.4:
                        e = with_sentence_audio(e, w)
                elif kind == 1:
                    e = ex_yes_no(w, pool)
                    if e and w.get("sentence_audio_url") and random.random() < 0.4:
                        e = with_sentence_audio(e, w)
                elif kind == 2:
                    e = ex_pick_word_audio(w, pool)
                else:
                    e = ex_build_sentence(w, pool) or ex_build_word(w) or ex_pick_image(w, pool)
            if e:
                items.append(e)
        if not phrase_mode:
            m = ex_memory(pool)
            if m:
                items.append(m)
            if random.random() < 0.6:  # «норки» — финальный тест на внимание
                e = ex_moles(random.choice(pool), pool)
                if e:
                    items.append(e)
            if random.random() < 0.4:  # «цепочка» — слуховая память
                e = ex_chain(pool)
                if e:
                    items.append(e)
        random.shuffle(items)
        items = _no_three_in_a_row(items)
    else:
        start = (lesson_no - 1) * NEW_WORDS_PER_LESSON
        new_words = pool[start:start + NEW_WORDS_PER_LESSON]
        if not new_words:
            new_words = pool[-NEW_WORDS_PER_LESSON:]
        review = await due_review_words(db, user, 3, exclude_theme=theme_id)

        sort_payload = None
        if not phrase_mode:
            units = await get_ordered_units(db)
            prev_units = [
                u for u in units
                if u.order_index < theme.order_index
                and u.title_ru not in PHRASE_THEMES
                and frozenset({u.title_ru, theme.title_ru}) not in SORT_INCOMPATIBLE
            ]
            if prev_units and random.random() < 0.7:
                other = random.choice(prev_units)
                other_words = [word_dto(w) for w in await unit_words(db, other.id)]
                # «что лишнее?» — только на темах-категориях (иначе «лишнее» неопределимо); иначе сортировка
                if theme.title_ru in ODD_ONE_CATEGORY_THEMES and random.random() < 0.4:
                    sort_payload = ex_odd_one(pool, other_words)
                if not sort_payload:
                    sort_payload = ex_sort_baskets(theme, pool, other, other_words)

        items = build_exercises(new_words, pool, review, sort_payload,
                                phrase_mode=phrase_mode, allow_build=lesson_no >= 3,
                                sentences_ok=lesson_no >= 2,
                                late_unit=(theme.order_index or 0) >= 14,
                                feed_ok=theme.title_ru in EDIBLE_THEMES,
                                qneg_ok=theme.title_ru in QNEG_THEMES)

    if len(items) < 3:
        # страховка: без озвучки/картинок упражнения могли не собраться — даём карточки
        pad = random.sample(pool, min(4, len(pool)))
        items = [ex_card(w) for w in pad] + items

    return {
        "theme": {"id": theme.id, "title_ru": theme.title_ru, "icon_emoji": theme.icon_emoji},
        "lesson_no": lesson_no,
        "lessons_total": total,
        "is_boss": is_boss,
        "items": items,
    }


async def edible_theme_ids(db: AsyncSession) -> set:
    """id тем с едой — где «Покорми Акбая» уместно (для смешанной тренировки)."""
    rows = (await db.execute(select(Theme.id).where(Theme.title_ru.in_(EDIBLE_THEMES)))).all()
    return {r[0] for r in rows}


def _practice_items(words: list[dict], pool: list[dict], limit: int = 10,
                    feed_theme_ids: Optional[set] = None) -> list[dict]:
    """Практика без карточек — для тренировки/трудных слов."""
    random.shuffle(words)
    items: list[dict] = []
    for w in words[:limit]:
        gens = [lambda: ex_pick_image(w, pool), lambda: ex_yes_no(w, pool),
                lambda: ex_pick_word_audio(w, pool), lambda: ex_bubbles(w, pool),
                lambda: ex_question(w, pool)]  # сработает только для слов с озвученным вопросом
        if feed_theme_ids and w.get("theme_id") in feed_theme_ids:  # «покорми» — только съедобное
            gens.append(lambda: ex_feed(w, pool))
        random.shuffle(gens)
        for g in gens:
            e = g()
            if e:
                items.append(e)
                break
    m = ex_memory(pool)
    if m and items:
        items.append(m)
    random.shuffle(items)
    return _no_three_in_a_row(items)


@router.get("/review/mistakes")
async def review_mistakes(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Тренировка трудных слов (по ошибкам ребёнка)."""
    mistakes = (await db.execute(
        select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.count > 0)
    )).scalars().all()
    word_ids = [m.word_id for m in mistakes]
    if not word_ids:
        return {"title": "Трудные слова", "icon": "💪", "items": [], "empty": True}
    words = (await db.execute(select(Word).where(Word.id.in_(word_ids)))).scalars().all()
    dtos = [word_dto(w) for w in words]
    # пул дистракторов — из тем этих слов
    theme_ids = {w.theme_id for w in words}
    pool_words = (await db.execute(select(Word).where(Word.theme_id.in_(theme_ids)))).scalars().all()
    pool = [word_dto(w) for w in pool_words]
    return {"title": "Трудные слова", "icon": "💪",
            "items": _practice_items(dtos, pool, limit=8, feed_theme_ids=await edible_theme_ids(db)),
            "empty": False}


@router.get("/review/{theme_id}")
async def review_theme(
    theme_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    """Свободная тренировка по пройденной теме (без влияния на карту)."""
    theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    if not user.is_admin and theme_id not in await unlocked_theme_ids(db, user):
        raise HTTPException(status_code=403, detail="Этот юнит ещё закрыт")
    words = await unit_words(db, theme_id)
    pool = [word_dto(w) for w in words]
    if theme.title_ru in PHRASE_THEMES:
        items = []
        voiced = [w for w in pool if w["audio_url"]]
        random.shuffle(voiced)
        for w in voiced[:6]:
            e = ex_pick_word_audio(w, pool)
            if e:
                items.append(e)
        items = _no_three_in_a_row(items)
    else:
        feed_ids = await edible_theme_ids(db) if theme.title_ru in EDIBLE_THEMES else None
        items = _practice_items(list(pool), pool, limit=8, feed_theme_ids=feed_ids)
    return {"title": theme.title_ru, "icon": theme.icon_emoji or "💪", "items": items, "empty": not items}


@router.get("/daily")
async def daily_lesson(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    date = today_str()
    existing = (await db.execute(
        select(DailyLesson).where(DailyLesson.user_id == user.id, DailyLesson.date == date)
    )).scalar_one_or_none()
    if existing and existing.completed_at:
        return {"completed": True, "stars": existing.stars, "date": date,
                "streak": await compute_streak(db, user)}
    if existing and existing.items_json:
        return {"completed": False, "date": date, "items": json.loads(existing.items_json)}

    # новое задание дня: повторение (главный канал SRS) + немного нового из текущего юнита
    review = await due_review_words(db, user, DAILY_REVIEW_LIMIT)

    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    current_unit: Optional[Theme] = None
    prev_done = True
    for t in units:
        p = progress.get(t.id)
        completed = bool(p and p.completed_at)
        if prev_done and not completed:
            current_unit = t
            break
        prev_done = completed
    if current_unit is None:
        current_unit = units[0] if units else None
    if current_unit is None:
        raise HTTPException(status_code=400, detail="Нет тем")

    pool = [word_dto(w) for w in await unit_words(db, current_unit.id)]
    seen_ids = {
        r[0] for r in (await db.execute(
            select(UserProgress.word_id).where(UserProgress.user_id == user.id)
        )).all()
    }
    fresh = [w for w in pool if w["id"] not in seen_ids][:3]

    items = build_exercises(fresh, pool, review, phrase_mode=current_unit.title_ru in PHRASE_THEMES,
                            sentences_ok=True, feed_ok=current_unit.title_ru in EDIBLE_THEMES,
                            qneg_ok=current_unit.title_ru in QNEG_THEMES)
    if not items:
        raise HTTPException(status_code=400, detail="Не удалось собрать задание")

    if existing:
        existing.items_json = json.dumps(items, ensure_ascii=False)
    else:
        db.add(DailyLesson(user_id=user.id, date=date, items_json=json.dumps(items, ensure_ascii=False)))
    await db.commit()
    return {"completed": False, "date": date, "items": items}


class LessonAnswer(BaseModel):
    word_id: int
    is_correct: bool
    exercise_type: Optional[str] = None


@router.post("/answer")
async def lesson_answer(answer: LessonAnswer,
                        db: Annotated[AsyncSession, Depends(get_db)],
                        user: Annotated[User, Depends(get_current_user)]):
    word_row = (await db.execute(select(Word).where(Word.id == answer.word_id))).scalar_one_or_none()
    if word_row is None:
        raise HTTPException(status_code=404, detail="Слово не найдено")
    progress = (await db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id, UserProgress.word_id == answer.word_id)
    )).scalar_one_or_none()
    if not progress:
        # новое слово: оно должно быть из открытого юнита (защита от накрутки прогресса)
        if not user.is_admin and word_row.theme_id not in await unlocked_theme_ids(db, user):
            raise HTTPException(status_code=403, detail="Это слово из закрытого юнита")
        progress = UserProgress(user_id=user.id, word_id=answer.word_id, learned=False, strength=0,
                                first_seen_at=now_utc())
        db.add(progress)
    progress.seen_count = (progress.seen_count or 0) + 1
    progress.last_seen_at = now_utc()
    if answer.is_correct:
        progress.correct_count = (progress.correct_count or 0) + 1
        # интервал растёт только если слово было «к повторению» (или новое) —
        # иначе 3-4 верных ответа внутри одного урока раздували strength за день
        was_due = progress.due_at is None or progress.due_at <= now_utc()
        if was_due or (progress.strength or 0) == 0:
            progress.strength = min(MAX_STRENGTH, (progress.strength or 0) + 1)
            progress.due_at = now_utc() + timedelta(days=SRS_INTERVALS_DAYS[progress.strength])
        progress.learned = True
    else:
        progress.strength = 1 if (progress.strength or 0) > 1 else (progress.strength or 0)
        progress.due_at = now_utc() + timedelta(days=SRS_INTERVALS_DAYS[progress.strength or 0])

    # зеркалим старый счётчик ошибок, чтобы страница «работа над ошибками» жила
    mistake = (await db.execute(
        select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.word_id == answer.word_id)
    )).scalar_one_or_none()
    if answer.is_correct:
        if mistake:
            mistake.count = 0
    else:
        if not mistake:
            mistake = UserMistake(user_id=user.id, word_id=answer.word_id, count=0)
            db.add(mistake)
        mistake.count += 1
    await db.commit()
    return {"ok": True, "strength": progress.strength}


class LessonComplete(BaseModel):
    kind: str  # "unit" | "daily"
    theme_id: Optional[int] = None
    lesson_no: Optional[int] = None
    correct: int = 0
    total: int = 0


def stars_for(correct: int, total: int) -> int:
    if total <= 0:
        return 1
    ratio = correct / total
    if ratio >= 0.85:  # 5-леткам 90% недостижимо без слёз
        return 3
    if ratio >= 0.65:
        return 2
    return 1


@router.post("/complete")
async def lesson_complete(payload: LessonComplete,
                          db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[User, Depends(get_current_user)]):
    stars = stars_for(payload.correct, payload.total)
    sticker: Optional[str] = None

    if payload.kind == "unit":
        if not payload.theme_id or not payload.lesson_no:
            raise HTTPException(status_code=400, detail="Нужны theme_id и lesson_no")
        theme = (await db.execute(select(Theme).where(Theme.id == payload.theme_id))).scalar_one_or_none()
        if not theme:
            raise HTTPException(status_code=404, detail="Тема не найдена")
        if not user.is_admin and theme.id not in await unlocked_theme_ids(db, user):
            raise HTTPException(status_code=403, detail="Этот юнит ещё закрыт")
        words = await unit_words(db, theme.id)
        total_lessons = lessons_total_for(len(words))
        p = (await db.execute(select(UnitProgress).where(
            UnitProgress.user_id == user.id, UnitProgress.theme_id == theme.id
        ))).scalar_one_or_none()
        if not p:
            p = UnitProgress(user_id=user.id, theme_id=theme.id, stars=0, lessons_done=0)
            db.add(p)
        lesson_no = min(payload.lesson_no, total_lessons)
        if not user.is_admin and lesson_no > (p.lessons_done or 0) + 1:
            raise HTTPException(status_code=400, detail="Этот урок ещё не открыт")
        # дневной лимит новых слов действует и на закрытие урока — иначе 429 обходится одним POST
        if not user.is_admin and lesson_no == (p.lessons_done or 0) + 1 and lesson_no < total_lessons:
            kazan_day_start = (now_utc() + KAZAN_UTC_OFFSET).replace(hour=0, minute=0, second=0, microsecond=0) - KAZAN_UTC_OFFSET
            new_today = (await db.execute(
                select(func.count(UserProgress.id)).where(
                    UserProgress.user_id == user.id,
                    UserProgress.first_seen_at.is_not(None),
                    UserProgress.first_seen_at >= kazan_day_start,
                )
            )).scalar_one()
            if new_today > NEW_WORDS_DAILY_LIMIT + NEW_WORDS_PER_LESSON:
                raise HTTPException(status_code=429, detail="На сегодня хватит новых слов! 🌟 Приходи завтра")
        p.lessons_done = max(p.lessons_done or 0, lesson_no)
        # копим звёзды за каждый урок (лучший результат)
        lr = (await db.execute(select(LessonResult).where(
            LessonResult.user_id == user.id, LessonResult.theme_id == theme.id,
            LessonResult.lesson_no == lesson_no,
        ))).scalar_one_or_none()
        if not lr:
            db.add(LessonResult(user_id=user.id, theme_id=theme.id, lesson_no=lesson_no, stars=stars))
        else:
            lr.stars = max(lr.stars or 0, stars)
        if lesson_no >= total_lessons:  # босс пройден
            p.stars = max(p.stars or 0, stars)
            if not p.completed_at:
                p.completed_at = now_utc()
                sticker = theme.icon_emoji or "🏅"
    elif payload.kind == "daily":
        date = today_str()
        d = (await db.execute(select(DailyLesson).where(
            DailyLesson.user_id == user.id, DailyLesson.date == date
        ))).scalar_one_or_none()
        if not d:
            d = DailyLesson(user_id=user.id, date=date)
            db.add(d)
        if not d.completed_at:
            d.completed_at = now_utc()
            d.stars = stars
    else:
        raise HTTPException(status_code=400, detail="kind должен быть unit или daily")

    await db.commit()
    streak = await compute_streak(db, user)
    if payload.kind == "daily" and streak in STREAK_STICKERS:
        sticker = STREAK_STICKERS[streak]

    if sticker:
        exists = (await db.execute(select(UserSticker).where(
            UserSticker.user_id == user.id, UserSticker.sticker == sticker
        ))).scalar_one_or_none()
        if exists:
            sticker_awarded = None
        else:
            db.add(UserSticker(user_id=user.id, sticker=sticker))
            await db.commit()
            sticker_awarded = sticker
    else:
        sticker_awarded = None

    return {"stars": stars, "sticker": sticker_awarded, "streak": streak}


@router.get("/home")
async def home_summary(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    date = today_str()
    d = (await db.execute(select(DailyLesson).where(
        DailyLesson.user_id == user.id, DailyLesson.date == date
    ))).scalar_one_or_none()
    daily_done = bool(d and d.completed_at)

    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    current = None
    prev_done = True
    for t in units:
        p = progress.get(t.id)
        completed = bool(p and p.completed_at)
        if prev_done and not completed:
            lessons_done = p.lessons_done if p else 0
            counts = await word_counts_by_theme(db)
            total = lessons_total_for(counts.get(t.id, 0))
            current = {
                "theme_id": t.id, "title_ru": t.title_ru, "icon_emoji": t.icon_emoji or "📚",
                "next_lesson": min(lessons_done + 1, total),
                "lessons_total": total,
            }
            break
        prev_done = completed

    stickers = (await db.execute(select(UserSticker).where(UserSticker.user_id == user.id))).scalars().all()
    lesson_stars = (await db.execute(
        select(func.coalesce(func.sum(LessonResult.stars), 0)).where(LessonResult.user_id == user.id)
    )).scalar_one()
    daily_stars = (await db.execute(
        select(func.coalesce(func.sum(DailyLesson.stars), 0)).where(
            DailyLesson.user_id == user.id, DailyLesson.completed_at.is_not(None))
    )).scalar_one()
    learned = (await db.execute(
        select(func.count(UserProgress.id)).where(UserProgress.user_id == user.id, UserProgress.strength >= 2)
    )).scalar_one()

    return {
        "username": user.username,
        "daily_done": daily_done,
        "streak": await compute_streak(db, user),
        "stickers": [s.sticker for s in stickers],
        "total_stars": int(lesson_stars) + int(daily_stars),
        "learned_words": learned,
        "current_unit": current,
    }
