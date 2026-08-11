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
PHRASE_THEMES = {"Привет и пока", "Давай знакомиться", "Вежливые слова",
                 "Чей? Кому? У кого?",   # падежные формы местоимений — абстракции без картинок
                 "Кто? Что? Какой?",     # вопросительные слова — то же самое
                 "Вежливые фразы"}       # ситуативные формулы: по картинке не различить

# Темы, где «картинка» слова — условный значок (🔼 у «өстендә»). Картиночные
# форматы учат тут стрелку вместо слова, а сама стрелка лезет дистрактором к
# чужим словам, поэтому такие темы работают только сценой и голосом.
ICON_ONLY_THEMES = {"Кайда? Где что лежит"}

# Дневной лимит НОВЫХ слов = 7 уроков по 4 слова (просьба владельца 2026-07-17;
# было 10 — методист предупреждал, что очередь повторений растёт лавинообразно).
NEW_WORDS_DAILY_LIMIT = 7 * NEW_WORDS_PER_LESSON  # 28

# Пары тем с пересекающейся семантикой — сортировка по корзинам между ними неоднозначна.
# темы, которые вообще нельзя сортировать по корзинам: их «предметы» — абстракции
SORT_EXCLUDED_THEMES = {
    "Нинди? Какой предмет", "Кто? Что? Какой?", "Чей? Кому? У кого?",
    "Вежливые фразы", "Время и сезоны",
}

SORT_INCOMPATIBLE = {
    frozenset({"Животные: дома и во дворе", "Животные: в лесу и зоопарке"}),
    frozenset({"Животные: дома и во дворе", "Птицы, рыбки, букашки"}),
    frozenset({"Животные: в лесу и зоопарке", "Птицы, рыбки, букашки"}),
    frozenset({"Здоровье", "Профессии"}),
    frozenset({"Здоровье", "Моё тело"}),
    frozenset({"Игрушки", "Вещи в доме"}),
    frozenset({"В городе", "В деревне"}),
    frozenset({"В магазине", "Продукты и напитки"}),
    frozenset({"В магазине", "Одежда и обувь"}),
    frozenset({"В магазине", "Игрушки"}),
    frozenset({"В магазине", "Вещи в доме"}),
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
    # новые юниты: пары, различающиеся одной буквой или общим финалем
    frozenset({"кайда?", "кая?"}),
    frozenset({"ничә?", "ничек?"}),
    frozenset({"дару", "даруханә"}),
    frozenset({"хастаханә", "даруханә"}),
    frozenset({"очучы", "очкыч"}),
    frozenset({"тамак", "тавык"}),
    frozenset({"кибет", "киштә"}),
    frozenset({"сатучы", "сатып алучы"}),
    frozenset({"йөткерә", "төчкерә"}),
    # падежные формы местоимений: мин/син-ряды различаются одной буквой на слух
    frozenset({"мине", "сине"}),
    frozenset({"миңа", "сиңа"}),
    frozenset({"миннән", "синнән"}),
    frozenset({"миндә", "синдә"}),
    frozenset({"минем", "синең"}),
    frozenset({"аны", "аңа"}),
    frozenset({"аннан", "анда"}),
    frozenset({"мин", "мине"}),
    frozenset({"син", "сине"}),
    frozenset({"тел", "теш"}),
    frozenset({"иртә", "иртәгә"}),
    frozenset({"каймак", "коймак"}),
    frozenset({"укытучы", "укучы"}),
    frozenset({"каләм", "карандаш"}),
    frozenset({"кабак", "ташкабак"}),
    frozenset({"сау бул", "сау булыгыз"}),
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
    cands = [
        p for p in pool
        if p["id"] != target["id"] and p["audio_url"] and not confusable(p["text_tt"], target["text_tt"])
    ]
    if not target["audio_url"]:
        return None
    # дистракторы не должны быть созвучны и МЕЖДУ СОБОЙ (мине/сине рядом — лишний шум)
    random.shuffle(cands)
    distractors: list[dict] = []
    for p in cands:
        if all(not confusable(p["text_tt"], d["text_tt"]) for d in distractors):
            distractors.append(p)
            if len(distractors) == 2:
                break
    if len(distractors) < 2:
        return None
    options = distractors + [target]
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


def ex_who_ran(pool: list[dict], animate: bool = True) -> Optional[dict]:
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
    # татарский вопрос вслух: «Кем юк?» о живом, «Нәрсә юк?» о предметах —
    # заодно ребёнок слышит конструкцию отсутствия (юк) и вопросительное слово
    from ..tts import cached_tts_url
    yuk_audio = cached_tts_url(f"{missing['text_tt']} юк.")
    if not yuk_audio:
        return None  # без фразы отсутствия формат теряет главное — конструкцию «юк»
    # одушевлённость определяем по самому пропавшему слову, а не по теме:
    # в «Семья и наш дом» лежат и люди, и комнаты
    animate_word = animate and missing["text_tt"].lower() not in INANIMATE_WORDS
    ask_tt = "Кем юк?" if animate_word else "Нәрсә юк?"
    return {
        "type": "who_ran",
        "word_id": missing["id"],
        "shown": [brief(w) for w in trio],
        "missing_id": missing["id"],
        "options": options,
        "ask_tt": ask_tt,
        "ask_audio": cached_tts_url(ask_tt),
        # ответ целиком: «Песи юк» — ребёнок слышит готовую фразу отсутствия
        "yuk_audio": yuk_audio,
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
    # признаки предметов (юнит «Нинди?»)
    "калын": "нечкә", "нечкә": "калын",
    "яңа": "иске", "иске": "яңа",
    "чиста": "пычрак", "пычрак": "чиста",
    "авыр": "җиңел", "җиңел": "авыр",
    "йомшак": "каты", "каты": "йомшак",
    "юеш": "коры", "коры": "юеш",
    "җылы": "салкын",  # односторонне: из «салкын» ведём к «кайнар» (пара выше)
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
# Темы про живое — там спрашиваем «Кем юк?» (кто), в остальных «Нәрсә юк?» (что)
ANIMATE_THEMES = {
    "Животные: дома и во дворе", "Животные: в лесу и зоопарке",
    "Птицы, рыбки, букашки", "Семья и наш дом", "Профессии", "Здоровье",
}

# слова-предметы внутри «одушевлённых» тем (в «Семья и наш дом» есть и комнаты)
INANIMATE_WORDS = {
    "өй", "фатир", "бүлмә", "ванна бүлмәсе", "аш бүлмәсе", "йокы бүлмәсе",
    "кунак бүлмәсе", "балалар бүлмәсе", "ишек", "тәрәзә", "баскыч", "гаилә",
    "оя", "койрык", "канат", "томшык", "тәпи", "җим", "җимлек",
}

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


def ex_alt_question(target: dict, pool: list[dict]) -> Optional[dict]:
    """Альтернативный вопрос «Пәлтә калынмы, нечкәме?» — выбор из двух признаков.
    Работает на парах OPPOSITES_TT: звучит вопрос с обоими вариантами,
    ребёнок жмёт картинку того признака, который верен. Фраза берётся
    только из кэша TTS (предозвучка — tools/gen_alt_tts.py)."""
    from ..qneg import question_particle
    from ..tts import cached_tts_url
    tt = target["text_tt"].lower()
    partner_tt = OPPOSITES_TT.get(tt)
    if not partner_tt or not target["audio_url"]:
        return None
    partner = next((p for p in pool if p["text_tt"].lower() == partner_tt), None)
    if not partner or not partner["audio_url"]:
        return None
    if not _has_photo(target) or not _has_photo(partner):
        return None  # признак должен быть виден на картинке, эмодзи-заглушка не годится
    # порядок в вопросе случаен: иначе верным всегда оказывается названный первым
    first, second = (target, partner) if random.random() < 0.5 else (partner, target)
    f_tt, s_tt = first["text_tt"].lower(), second["text_tt"].lower()
    phrase = f"{f_tt.capitalize()}{question_particle(f_tt)}, {s_tt}{question_particle(s_tt)}?"
    url = cached_tts_url(phrase)
    if not url:
        return None
    options = [_brief(target), _brief(partner)]
    random.shuffle(options)
    return {"type": "alt_question", "word_id": target["id"],
            "text_tt": phrase, "audio_url": url, "options": options,
            # без предмета-якоря вопрос «Чистамы, пычракмы?» не имеет решения:
            # ребёнок должен видеть, ПРО ЧТО спрашивают
            "source": {"id": target["id"], "image_url": target["image_url"],
                       "emoji": target["emoji"]}}


# Чем это делают: действие (3 л. ед. ч.) → инструмент. Послелог «белән» —
# один из самых частотных в детской речи, а задание сводится к выбору картинки.
WITH_WHAT = {
    "яза": "каләм",            # пишет ручкой
    "рәсем ясый": "карандаш",  # рисует карандашом
    "ашый": "кашык",           # ест ложкой
    "кисә": "кайчы",           # режет ножницами
    "ябыштыра": "җилем",       # клеит клеем
    "чистарта": "бетергеч",    # стирает ластиком
}


def ex_plural(target: dict) -> Optional[dict]:
    """«Один или много?»: показываем одну картинку или картинку с тремя предметами,
    ребёнок выбирает из двух озвучек нужную форму (песи / песиләр).
    Формы — из app/forms.py (после М/Н/Ң берут -нар/-нәр, автоматом не вывести).
    Картинка «много» лежит отдельно: static/image/plural/word_{id}.png."""
    import os

    from ..config import STATIC_DIR
    from ..forms import PLURAL_TT
    from ..tts import cached_tts_url
    tt = target["text_tt"].lower()
    plural_tt = PLURAL_TT.get(tt)
    if not plural_tt or not target["audio_url"] or not _has_photo(target):
        return None
    plural_img = os.path.join(STATIC_DIR, "image", "plural", f"word_{target['id']}.png")
    if not os.path.isfile(plural_img):
        return None
    plural_audio = cached_tts_url(plural_tt)
    if not plural_audio:
        return None
    many = random.random() < 0.5
    return {
        "type": "plural",
        "word_id": target["id"],
        "many": many,
        "image_url": (f"/static/image/plural/word_{target['id']}.png" if many
                      else target["image_url"]),
        "options": [
            {"key": "one", "text_tt": tt, "audio_url": target["audio_url"]},
            {"key": "many", "text_tt": plural_tt, "audio_url": plural_audio},
        ],
    }


def ex_negation(target: dict, pool: list[dict]) -> Optional[dict]:
    """«Ул йөзәме?» — на картинке другое действие, верный ответ «Юк, ул йөзми».
    Формы отрицания выверены носителем (app/forms.py), автоматически их
    строить нельзя: основа глагола в 3 л. часто искажена (чыга → чык-)."""
    from ..forms import NEGATIVE_TT
    from ..qneg import question_particle
    from ..tts import cached_tts_url
    verb = target["text_tt"].lower()
    neg = NEGATIVE_TT.get(verb)
    if not neg or not target["audio_url"] or not _has_photo(target):
        return None
    question = f"Ул {verb}{question_particle(verb)}?"
    q_url = cached_tts_url(question)
    yes_url = cached_tts_url(f"Әйе, ул {verb}.")
    no_url = cached_tts_url(f"Юк, ул {neg}.")
    if not q_url or not yes_url or not no_url:
        return None
    # половина заданий — про эту же картинку (Әйе), половина — про чужое действие (Юк)
    is_match = random.random() < 0.5
    shown = target
    if not is_match:
        others = [p for p in pool
                  if p["id"] != target["id"] and _has_photo(p)
                  and p["text_tt"].lower() in NEGATIVE_TT
                  and not confusable(p["text_tt"], target["text_tt"])]
        if not others:
            is_match = True
        else:
            shown = random.choice(others)
    return {
        "type": "negation",
        "word_id": target["id"],
        "text_tt": question,
        "audio_url": q_url,
        "is_match": is_match,
        "shown": {"id": shown["id"], "image_url": shown["image_url"], "emoji": shown["emoji"]},
        "yes_tt": f"Әйе, ул {verb}.", "yes_audio": yes_url,
        "no_tt": f"Юк, ул {neg}.", "no_audio": no_url,
    }


def ex_with_what(pool: list[dict], all_words: list[dict]) -> Optional[dict]:
    """«Нәрсә белән яза?» — выбери инструмент. Вопрос берётся из кэша TTS
    (предозвучка — tools/gen_withwhat_tts.py), ответ звучит как «Каләм белән»."""
    from ..tts import cached_tts_url
    by_tt = {w["text_tt"].lower(): w for w in all_words}
    pairs = [(verb, tool) for verb, tool in WITH_WHAT.items()
             if tool in by_tt and _has_photo(by_tt[tool])]
    random.shuffle(pairs)
    for verb, tool_tt in pairs:
        question = f"Нәрсә белән {verb}?"
        q_url = cached_tts_url(question)
        answer_url = cached_tts_url(f"{tool_tt.capitalize()} белән.")
        if not q_url or not answer_url:
            continue
        target = by_tt[tool_tt]
        others = [by_tt[t] for v, t in WITH_WHAT.items()
                  if t != tool_tt and t in by_tt and _has_photo(by_tt[t])]
        if len(others) < 2:
            continue
        options = random.sample(others, 2) + [target]
        random.shuffle(options)
        return {
            "type": "with_what",
            "word_id": target["id"],
            "text_tt": question,
            "audio_url": q_url,
            "answer_audio": answer_url,
            "options": [{"id": o["id"], "image_url": o["image_url"], "emoji": o["emoji"]} for o in options],
        }
    return None


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


def _basket(bid: int, title_ru: str, title_tt: Optional[str], icon: str) -> dict:
    """Подпись корзины: татарское имя главное, русское — мелким для взрослого.
    Озвучка татарская из кэша TTS; если фразы в кэше нет, фронт проговорит
    русское название браузерным синтезом, как было раньше."""
    from ..tts import cached_tts_url
    ru = title_ru
    if title_tt and ru.startswith(title_tt):
        # у новых тем название уже содержит татарскую часть («Кәеф ничек? Настроения»),
        # иначе подпись задваивалась бы сама с собой
        ru = ru[len(title_tt):].lstrip(' .—-') or title_ru
    return {"id": bid, "title_ru": ru, "title_tt": title_tt or None,
            "icon_emoji": icon, "audio_url": cached_tts_url(title_tt) if title_tt else None}


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
            _basket(theme_a.id, theme_a.title_ru, theme_a.title_tt, theme_a.icon_emoji or "📦"),
            _basket(theme_b.id, theme_b.title_ru, theme_b.title_tt, theme_b.icon_emoji or "📦"),
        ],
        "items": items,
    }


# Сводные сортировки: повторяют лексику сразу нескольких пройденных тем.
# Ключ — название корзины, значение — темы, из которых берём предметы.
SORT_SCENARIOS = [
    {
        "title": "🎒 Собери портфель",
        "baskets": [
            {"id": 1, "title_ru": "В портфель", "title_tt": "Букчага", "icon_emoji": "🎒",
             "themes": ["Школа и урок", "Пенал и рюкзак"]},
            {"id": 2, "title_ru": "Не нужно", "title_tt": "Кирәкми", "icon_emoji": "🚫",
             "themes": ["Продукты и напитки", "Игрушки", "Фрукты/ягоды"]},
        ],
    },
    {
        "title": "🛒 Разложи по магазинам",
        "baskets": [
            # ашамлык / кием / уенчык ребёнок к этому моменту уже проходил
            {"id": 1, "title_ru": "Еда", "title_tt": "Ашамлыклар", "icon_emoji": "🥖",
             "themes": ["Продукты и напитки", "Фрукты/ягоды", "Овощи"]},
            {"id": 2, "title_ru": "Одежда", "title_tt": "Кием", "icon_emoji": "👗",
             "themes": ["Одежда и обувь"]},
            {"id": 3, "title_ru": "Игрушки", "title_tt": "Уенчыклар", "icon_emoji": "🧸",
             "themes": ["Игрушки"]},
        ],
    },
]


# Одежда по погоде: сюжет «Марат собирается гулять» из книги «Мин татар».
# Ребёнок одевает персонажа, после каждой вещи звучит «Марат нәрсә кия? — Марат X кия».
DRESS_SCENES = [
    {"key": "winter", "title_ru": "На улице зима — что наденем?", "emoji": "❄️",
     "right": ["бүрек", "пальто", "итекләр", "бияләйләр", "шарф", "свитер", "куртка"],
     "wrong": ["шорты", "футболка", "чүәкләр", "пижама"]},
    {"key": "summer", "title_ru": "На улице лето — что наденем?", "emoji": "☀️",
     "right": ["футболка", "шорты", "күлмәк", "итәк", "кроссовки", "туфли"],
     "wrong": ["бүрек", "пальто", "бияләйләр", "шарф", "итекләр"]},
]


# Приметы сезонов — готовые озвученные фразы из книги «Мин татар».
# Ребёнок слушает примету и кладёт её в нужное время года.
SEASON_SIGNS = {
    "яз": [("Кар эри.", "Снег тает."), ("Кошлар кайта.", "Птицы возвращаются."),
           ("Тамчы тама.", "Капает капель.")],
    "җәй": [("Балалар су коена.", "Дети купаются."), ("Чәчәкләр үсә.", "Растут цветы."),
            ("Кояш кыздыра.", "Солнце печёт.")],
    "көз": [("Яфрак коела.", "Падают листья."), ("Яңгыр ява.", "Идёт дождь."),
            ("Урамда пычрак.", "На улице грязно.")],
    "кыш": [("Кар ява.", "Идёт снег."), ("Балалар чанада шуа.", "Дети катаются на санках."),
            ("Кар бабай ясыйлар.", "Лепят снеговика.")],
}
SEASON_ICONS = {"яз": "🌱", "җәй": "☀️", "көз": "🍂", "кыш": "❄️"}


def ex_seasons(season_words: list[dict]) -> Optional[dict]:
    """Альбом времён года: 4 корзины-сезона, в них раскладываются приметы.
    Фразы озвучены заранее (tools/gen_season_tts.py), картинок не требуют —
    ребёнок опирается на слух, поэтому берём максимум по одной примете на сезон."""
    from ..tts import cached_tts_url
    by_tt = {w["text_tt"].lower(): w for w in season_words}
    baskets, items = [], []
    for idx, (season, signs) in enumerate(SEASON_SIGNS.items(), 1):
        w = by_tt.get(season)
        if not w or not w["audio_url"]:
            return None
        phrase, ru = random.choice(signs)
        url = cached_tts_url(phrase)
        if not url:
            return None
        baskets.append(_basket(idx, w["text_ru"], season, SEASON_ICONS[season]))
        items.append({"word_id": w["id"], "text_tt": phrase, "audio_url": url,
                      # нейтральный значок: иконка сезона на плитке выдавала ответ
                      "image_url": None, "emoji": "🔊", "basket": idx})
    random.shuffle(items)
    return {"type": "sort_baskets", "title": "🗓 Альбом времён года",
            "baskets": baskets, "items": items}


# ---------- форматы выше уровня отдельного слова ----------
# До них 94% заданий сводились к «услышал слово — ткни картинку». Здесь ответ
# нельзя дать, узнав предмет: нужно расслышать послелог, форму времени, число
# или связать событие с состоянием.

# Сцена для послелогов: один и тот же кот и одна и та же опора во всех вариантах,
# различается только положение. Ключ — как фронт ставит фигурку (см. rWhere).
# У каждого послелога ДВЕ сцены: на кровати и на коробке. Раньше «эчендә» жил
# на коробке один, дистракторов на той же опоре не набиралось, и слово ни разу
# не попало в задание (0 из 382). Заодно две опоры дают перенос: тот же
# послелог на другом предмете.
PLACE_SCENES = {
    "өстендә": {"pos": "on", "anchors": ["🛏", "📦"]},
    "астында": {"pos": "under", "anchors": ["🛏", "📦"]},
    "эчендә": {"pos": "in", "anchors": ["📦"]},        # в кровати не лежат
    "янында": {"pos": "near", "anchors": ["🛏", "📦"]},
    "артында": {"pos": "behind", "anchors": ["🛏", "📦"]},
    "алдында": {"pos": "front", "anchors": ["🛏", "📦"]},
}
ANCHOR_TT = {"🛏": "карават", "📦": "тартма"}
PLACE_SUBJECT = "🐱"


def ex_where(target: dict, place_pool: list[dict]) -> Optional[dict]:
    """«Кайда песи?» — четыре сцены с одним и тем же котом и одной опорой.
    Предмет всюду один, поэтому угадать по картинке нельзя: решает только
    услышанный послелог. Фраза берётся из кэша TTS (tools/gen_hard_tts.py)."""
    from ..tts import cached_tts_url
    tt = target["text_tt"].lower()
    scene = PLACE_SCENES.get(tt)
    if not scene or not target["audio_url"]:
        return None
    # опору выбираем из тех, на которых наберётся достаточно дистракторов
    for anchor in random.sample(scene["anchors"], len(scene["anchors"])):
        same = [w for w in place_pool
                if w["id"] != target["id"]
                and anchor in PLACE_SCENES.get(w["text_tt"].lower(), {}).get("anchors", [])]
        if len(same) >= 2:
            break
    else:
        return None
    phrase = f"Песи {ANCHOR_TT[anchor]} {tt}."
    url = cached_tts_url(phrase)
    if not url:
        return None
    options = [target] + random.sample(same, min(3, len(same)))
    random.shuffle(options)
    return {
        "type": "where", "word_id": target["id"], "text_tt": phrase, "audio_url": url,
        "subject": PLACE_SUBJECT, "anchor": anchor,
        "options": [{"id": w["id"], "text_tt": w["text_tt"],
                     "pos": PLACE_SCENES[w["text_tt"].lower()]["pos"]} for w in options],
        "answer_id": target["id"],
    }


def ex_past(target: dict) -> Optional[dict]:
    """«Хәзерме, әллә инде?» — звучит глагол в настоящем или прошедшем времени,
    ребёнок выбирает «делает сейчас» или «уже сделал». Никаких новых слов и
    картинок: это чистое различение формы, которого в курсе не было совсем."""
    from ..forms import PAST_TT
    from ..tts import cached_tts_url
    tt = target["text_tt"].lower()
    past_tt = PAST_TT.get(tt)
    if not past_tt or not target["audio_url"] or not _has_photo(target):
        return None
    past_audio = cached_tts_url(past_tt)
    present_audio = cached_tts_url(tt)
    if not past_audio or not present_audio:
        return None  # обе формы обязаны быть из ОДНОГО источника, иначе тембр выдаёт ответ
    is_past = random.random() < 0.5
    return {
        "type": "past", "word_id": target["id"],
        "image_url": target["image_url"], "emoji": target["emoji"],
        "text_tt": past_tt if is_past else tt,
        "audio_url": past_audio if is_past else present_audio,
        "answer": "past" if is_past else "present",
        # «сейчас» и «уже» ребёнок слышит по-русски: кнопки без текста, с иконками
        "options": [{"key": "present"}, {"key": "past"}],
    }


NUMERALS_TT = {2: "ике", 3: "өч", 4: "дүрт", 5: "биш"}
COUNT_MAX = 5  # дальше пяти предметов на экране ребёнок 5–7 лет уже пересчитывает с ошибками


def ex_count(target: dict) -> Optional[dict]:
    """«Ничә алма?» — на экране N одинаковых предметов, выбор из трёх озвучек
    «ике алма / өч алма / дүрт алма». Числа и предметы в курсе жили порознь:
    ребёнок знал «өч», но не связывал его с существительным."""
    from ..tts import cached_tts_url
    tt = target["text_tt"].lower()
    if not _has_photo(target):
        return None
    question = cached_tts_url(f"Ничә {tt}?")
    if not question:
        return None
    variants = []
    for n in range(2, COUNT_MAX + 1):
        url = cached_tts_url(f"{NUMERALS_TT[n]} {tt}")
        if url:
            variants.append({"n": n, "text_tt": f"{NUMERALS_TT[n]} {tt}", "audio_url": url})
    if len(variants) < 3:
        return None
    answer = random.choice(variants)
    others = [v for v in variants if v["n"] != answer["n"]]
    options = [answer] + random.sample(others, 2)
    random.shuffle(options)
    return {
        "type": "count", "word_id": target["id"], "n": answer["n"],
        "image_url": target["image_url"], "emoji": target["emoji"],
        "audio_url": question, "text_tt": f"Ничә {tt}?",
        "options": options, "answer": answer["n"],
    }


MOOD_THEME = "Кәеф ничек? Настроения"
MOOD_LOOKALIKE = {"шат": {"көлә"}, "көлә": {"шат"}}

# Считаем только то, что реально лежит кучкой и хорошо читается мелко.
# Каждому нужны предозвученные «Ничә X?» и «ике X … биш X» (tools/gen_count_tts.py).
COUNTABLE_TT = ["алма", "туп", "китап", "күлмәк", "песи", "эт", "кыяр", "йомырка",
                "карандаш", "шакмак", "чәчәк", "балык"]

# Причина → состояние. Все слова причины ребёнок уже проходил, новое здесь
# только само рассуждение: событие произошло — значит, вот такое состояние.
# Только те причины, где следствие единственное. «Друг ушёл» отсюда убрано:
# из него грусть не вытекает — ребёнок с тем же правом выберет «ачулы»
# (поссорились) или «арган». Формат учит выводу, а не угадыванию настроения.
MOOD_CAUSES = {
    "ач": ("Ул ашамады.", "Он не поел."),
    "сусаган": ("Ул су эчмәде.", "Он не пил воду."),
    "арган": ("Ул йокламады.", "Он не спал."),
    "курка": ("Анда зур эт бар.", "Там большая собака."),
}


def ex_why(target: dict, mood_pool: list[dict]) -> Optional[dict]:
    """«Нигә?» — звучит событие («Ул ашамады»), ребёнок выбирает состояние.
    Первое задание курса на связь причины и следствия, а не на называние."""
    from ..tts import cached_tts_url
    tt = target["text_tt"].lower()
    cause = MOOD_CAUSES.get(tt)
    if not cause or not target["audio_url"]:
        return None
    url = cached_tts_url(cause[0])
    if not url:
        return None
    # «шат» 😀 и «көлә» 😄 для дошкольника одно и то же — не даём их друг другу
    # в дистракторы; заодно требуем непохожий эмодзи, как это делает pick_image
    blocked = MOOD_LOOKALIKE.get(tt, set()) | {target["emoji"]}
    others = [w for w in mood_pool
              if w["id"] != target["id"] and w["emoji"]
              and w["text_tt"].lower() not in blocked and w["emoji"] not in blocked]
    if len(others) < 2:
        return None
    options = [target]
    for cand in random.sample(others, len(others)):
        if len(options) == 4:
            break
        # пара «шат/көлә» не должна встретиться и между двумя дистракторами
        if any(cand["text_tt"].lower() in MOOD_LOOKALIKE.get(o["text_tt"].lower(), set())
               or cand["emoji"] == o["emoji"] for o in options):
            continue
        options.append(cand)
    if len(options) < 3:
        return None
    random.shuffle(options)
    return {
        "type": "why", "word_id": target["id"],
        "text_tt": cause[0], "text_ru": cause[1], "audio_url": url,
        "cause_ru": cause[1],   # ключ для INSTR_AUDIO: причина звучит записью, не синтезом
        "options": [_brief(w) for w in options],
        "answer_id": target["id"],
    }


def ex_dress(scene: dict, clothes: list[dict]) -> Optional[dict]:
    """«Одень Марата»: выбери подходящую по погоде одежду. Правильных несколько —
    ребёнок набирает их одну за другой, каждая проговаривается фразой «Марат X кия»."""
    from ..tts import cached_tts_url
    by_tt = {w["text_tt"].lower(): w for w in clothes if w["audio_url"] and _has_photo(w)}
    right = [by_tt[t] for t in scene["right"] if t in by_tt]
    wrong = [by_tt[t] for t in scene["wrong"] if t in by_tt]
    if len(right) < 2 or len(wrong) < 2:
        return None
    random.shuffle(right)
    random.shuffle(wrong)
    picked_right, picked_wrong = right[:3], wrong[:3]
    options = []
    for w in picked_right + picked_wrong:
        options.append({
            "id": w["id"], "image_url": w["image_url"], "emoji": w["emoji"],
            "audio_url": w["audio_url"],
            "right": w in picked_right,
            # готовая фраза-ответ: «Марат чалбар кия»
            "phrase_audio": cached_tts_url(f"Марат {w['text_tt']} кия."),
        })
    random.shuffle(options)
    return {
        "type": "dress",
        "word_id": picked_right[0]["id"],
        "scene": {"title_ru": scene["title_ru"], "emoji": scene["emoji"]},
        "need": len(picked_right),
        "options": options,
    }


def ex_sort_groups(scenario: dict, words_by_theme: dict[str, list[dict]]) -> Optional[dict]:
    """Сводная сортировка по смысловым корзинам (не по темам, как sort_baskets):
    «собери портфель», «разложи по магазинам». Повторяет сразу несколько тем."""
    seen: set[str] = set()
    baskets, items = [], []
    per_basket = 2
    for b in scenario["baskets"]:
        pool = [w for t in b["themes"] for w in words_by_theme.get(t, [])
                if w["audio_url"] and _has_photo(w)
                and w["text_tt"].lower() not in CATEGORY_TT]
        picked = _distinct_visual_pick(pool, per_basket, seen)
        if not picked:
            return None
        baskets.append(_basket(b["id"], b["title_ru"], b.get("title_tt"), b["icon_emoji"]))
        items += [{"word_id": w["id"], "text_tt": w["text_tt"], "audio_url": w["audio_url"],
                   "image_url": w["image_url"], "emoji": w["emoji"], "basket": b["id"]}
                  for w in picked]
    random.shuffle(items)
    return {"type": "sort_baskets", "title": scenario["title"], "baskets": baskets, "items": items}


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
                    qneg_ok: bool = False, animate_theme: bool = True,
                    with_what_pool: Optional[list[dict]] = None,
                    verb_pool: Optional[list[dict]] = None,
                    plural_pool: Optional[list[dict]] = None,
                    sort_words: Optional[dict] = None,
                    clothes_pool: Optional[list[dict]] = None,
                    season_pool: Optional[list[dict]] = None,
                    icon_only: bool = False,
                    icon_only_ids: Optional[set] = None,
                    place_pool: Optional[list[dict]] = None,
                    past_pool: Optional[list[dict]] = None,
                    count_pool: Optional[list[dict]] = None,
                    mood_pool: Optional[list[dict]] = None) -> list[dict]:
    """Урок: чередование «карточка → сразу практика» + разнообразное закрепление.
    phrase_mode: тема из фраз — только карточки, звучание и повторение за диктором.
    allow_build: «собери слово» — только с 3-го урока юнита (для начала это слишком сложно)."""
    items: list[dict] = []
    icon_only_ids = icon_only_ids or set()

    if icon_only:
        # Тема, где «картинка» слова — условный значок (🔼 у «өстендә»). Картиночные
        # форматы тут учат стрелку вместо послелога, поэтому их нет совсем:
        # подача — карточка, отработка — сцена «кот и кровать» и голос.
        for w in new_words:
            items.append(ex_card(w))
            e = ex_where(w, place_pool or []) if place_pool else None
            if e:
                items.append(e)
        practice = []
        for w in new_words:
            e = ex_where(w, place_pool or []) if place_pool else None
            if e:
                practice.append(e)
            e = ex_pick_word_audio(w, pool)
            if e:
                practice.append(e)
        for w in new_words:
            if w["audio_url"]:
                practice.append(ex_repeat_after(w))
    elif phrase_mode:
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
            if place_pool and w["text_tt"].lower() in PLACE_SCENES:
                e = ex_where(w, place_pool)          # «Кайда песи?» — ради этого тема и нужна
            elif mood_pool and w["text_tt"].lower() in MOOD_CAUSES:
                e = ex_why(w, mood_pool)             # «Нигә?» — связь события и состояния
            if not e and sentences_ok:
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
        # пар в уроке бывает две (авыр/җиңел и калын/нечкә): берём случайную, иначе
        # первая всегда перехватывала слот и вторая не тренировалась ни разу
        opp_words = [w for w in new_words if w["text_tt"].lower() in OPPOSITES_TT]
        if opp_words:
            w = random.choice(opp_words)
            extra_gens.append(lambda w=w: ex_opposite(w, pool, known_pool))
            extra_gens.append(lambda w=w: ex_alt_question(w, known_pool))  # «калынмы, нечкәме?»
        if sentences_ok:
            extra_gens.append(lambda: ex_windows(pool))
        if allow_build:
            extra_gens.append(lambda: ex_who_ran(pool, animate=animate_theme))
            extra_gens.append(lambda: ex_flashlight(random.choice(new_words), pool))
        if late_unit:
            extra_gens.append(lambda: ex_chain(pool))
            extra_gens.append(lambda: ex_moles(random.choice(new_words), pool))  # «норки» не только в боссе
        if with_what_pool:
            extra_gens.append(lambda: ex_with_what(pool, with_what_pool))  # «Нәрсә белән яза?»
        if verb_pool:
            extra_gens.append(lambda: ex_negation(random.choice(verb_pool), verb_pool))  # «Юк, ул йөзми»
        if plural_pool:
            extra_gens.append(lambda: ex_plural(random.choice(plural_pool)))  # «Один или много?»
        if sort_words and late_unit:
            sc = random.choice(SORT_SCENARIOS)
            extra_gens.append(lambda sc=sc: ex_sort_groups(sc, sort_words))  # портфель / магазины
        if clothes_pool:
            sc = random.choice(DRESS_SCENES)
            extra_gens.append(lambda sc=sc: ex_dress(sc, clothes_pool))  # «одень Марата»
        if season_pool and late_unit:
            extra_gens.append(lambda: ex_seasons(season_pool))  # альбом времён года
        if place_pool:
            extra_gens.append(lambda: ex_where(random.choice(place_pool), place_pool))  # «Кайда песи?»
        if past_pool:
            extra_gens.append(lambda: ex_past(random.choice(past_pool)))  # «хәзерме, инде?»
        if count_pool:
            extra_gens.append(lambda: ex_count(random.choice(count_pool)))  # «Ничә алма?»
        if mood_pool:
            causes = [w for w in mood_pool if w["text_tt"].lower() in MOOD_CAUSES]
            if causes:
                extra_gens.append(lambda: ex_why(random.choice(causes), mood_pool))  # «Нигә ач?»
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
        elif phrase_mode:
            # фразовая тема: её «пул» — абстракции без картинок, картиночные
            # задания там неразрешимы (одно фото среди эмодзи-заглушек)
            e = ex_pick_word_audio(w, pool + review_words)
            if not e and w["audio_url"]:
                e = ex_repeat_after(w)
        elif icon_only or w.get("theme_id") in icon_only_ids:
            # значок-стрелка в чужом задании — конкурирующая ассоциация, только звук
            e = ex_pick_word_audio(w, pool + review_words) or (ex_repeat_after(w) if w["audio_url"] else None)
        else:
            e = ex_pick_image(w, pool + review_words) or ex_yes_no(w, pool + review_words)
        if e:
            e["review"] = True
            if w.get("mistake"):
                e["mistake"] = True  # из очереди «работы над ошибками»
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


async def pending_mistake_words(db: AsyncSession, user: User, limit: int,
                                exclude_ids: Optional[set] = None) -> list[dict]:
    """Очередь «работы над ошибками»: слова с незакрытыми ошибками (UserMistake.count > 0)
    едут за учеником и подмешиваются в следующие уроки, пока он не ответит верно —
    верный ответ в любом упражнении сбрасывает count и слово покидает очередь.
    Самые «трудные» (много ошибок подряд) — первыми."""
    q = (
        select(Word, Theme.title_ru)
        .join(UserMistake, UserMistake.word_id == Word.id)
        .join(Theme, Theme.id == Word.theme_id)
        .where(UserMistake.user_id == user.id, UserMistake.count > 0)
        .order_by(UserMistake.count.desc(), UserMistake.word_id)
        .limit(limit * 3)
    )
    rows = (await db.execute(q)).all()
    result = []
    for w, theme_title in rows:
        if exclude_ids and w.id in exclude_ids:
            continue
        dto = word_dto(w)
        dto["phrase"] = theme_title in PHRASE_THEMES
        dto["mistake"] = True
        result.append(dto)
        if len(result) == limit:
            break
    return result


async def unit_progress_map(db: AsyncSession, user: User) -> dict[int, UnitProgress]:
    rows = (await db.execute(select(UnitProgress).where(UnitProgress.user_id == user.id))).scalars().all()
    return {r.theme_id: r for r in rows}


async def frontier_index(db: AsyncSession, user: User) -> int:
    """Докуда ребёнок дошёл: позиция самого дальнего пройденного юнита (с нуля — ещё нисколько).

    Считаем именно по максимуму, а не по «все предыдущие пройдены»: иначе вставка
    новой темы в начало пути захлопнула бы всё, что ребёнок уже открыл.
    """
    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    reached = 0
    for i, t in enumerate(units, start=1):
        p = progress.get(t.id)
        if p and p.completed_at:
            reached = i
    return reached


async def unlocked_theme_ids(db: AsyncSession, user: User) -> set[int]:
    """Всё до самого дальнего пройденного юнита плюс следующий (защита от прыжков по URL)."""
    units = await get_ordered_units(db)
    reached = await frontier_index(db, user)
    return {t.id for i, t in enumerate(units, start=1) if i <= reached + 1}


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
    reached = await frontier_index(db, user)
    result = []
    for i, t in enumerate(units, start=1):
        word_count = counts.get(t.id, 0)
        total = lessons_total_for(word_count)
        p = progress.get(t.id)
        stars = p.stars if p else 0
        lessons_done = p.lessons_done if p else 0
        completed = bool(p and p.completed_at)
        if completed:
            state = "done"
        elif i <= reached + 1:
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
        icon_only_boss = theme.title_ru in ICON_ONLY_THEMES
        boss_place_pool = await place_words(db, None) if icon_only_boss else []
        for i, w in enumerate(sample):
            if icon_only_boss:
                # финальная проверка юнита про послелоги обязана спрашивать, ГДЕ кошка,
                # а не какой значок приклеен к слову
                e = ex_where(w, boss_place_pool) or ex_pick_word_audio(w, pool)
            elif phrase_mode:
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
        if not phrase_mode and not icon_only_boss:
            # у темы-значков картиночные добавки тоже отменяются: memory на стрелках
            # это игра «найди пару одинаковых треугольников», к послелогам отношения нет
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
        # работа над ошибками: незакрытые ошибки едут за учеником — до 4 в каждый урок,
        # они важнее планового повторения (его ужимаем, чтобы урок не разбухал)
        mistake_words = await pending_mistake_words(
            db, user, 4, {w["id"] for w in new_words} | {w["id"] for w in review})
        if mistake_words:
            review = review[:2] + mistake_words

        sort_payload = None
        icon_only_theme = theme.title_ru in ICON_ONLY_THEMES
        if not phrase_mode and not icon_only_theme and theme.title_ru not in SORT_EXCLUDED_THEMES:
            units = await get_ordered_units(db)
            prev_units = [
                u for u in units
                if u.order_index < theme.order_index
                and u.title_ru not in PHRASE_THEMES
                and u.title_ru not in ICON_ONLY_THEMES
                and frozenset({u.title_ru, theme.title_ru}) not in SORT_INCOMPATIBLE
                and u.title_ru not in SORT_EXCLUDED_THEMES
            ]
            if prev_units and random.random() < 0.7:
                other = random.choice(prev_units)
                other_words = [word_dto(w) for w in await unit_words(db, other.id)]
                # «что лишнее?» — только на темах-категориях (иначе «лишнее» неопределимо); иначе сортировка
                if theme.title_ru in ODD_ONE_CATEGORY_THEMES and random.random() < 0.4:
                    sort_payload = ex_odd_one(pool, other_words)
                if not sort_payload:
                    sort_payload = ex_sort_baskets(theme, pool, other, other_words)

        # бонусные форматы — только на словах уже пройденных юнитов
        learned = await learned_theme_ids(db, theme.order_index)
        icon_only_ids = {t.id for t in await get_ordered_units(db) if t.title_ru in ICON_ONLY_THEMES}
        items = build_exercises(new_words, pool, review, sort_payload,
                                phrase_mode=phrase_mode, allow_build=lesson_no >= 3,
                                icon_only=theme.title_ru in ICON_ONLY_THEMES,
                                icon_only_ids=icon_only_ids,
                                sentences_ok=lesson_no >= 2,
                                late_unit=(theme.order_index or 0) >= 14,
                                feed_ok=theme.title_ru in EDIBLE_THEMES,
                                qneg_ok=theme.title_ru in QNEG_THEMES,
                                animate_theme=theme.title_ru in ANIMATE_THEMES,
                                with_what_pool=await with_what_words(db, learned),
                                verb_pool=await verb_words(db, learned),
                                plural_pool=await plural_words(db, learned),
                                sort_words=await sort_scenario_words(db),
                                clothes_pool=await clothes_words(db, learned),
                                season_pool=await season_words(db, learned),
                                # послелоги и настроения тренируются и внутри своей темы:
                                # иначе формат существует, но в самом юните ни разу не выпадает
                                place_pool=await place_words(db, learned | {theme.id}),
                                past_pool=await verb_words(db, learned),
                                count_pool=await count_words(db, learned),
                                mood_pool=await mood_words(db, learned | {theme.id}))

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








async def season_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Слова-сезоны (яз, җәй, көз, кыш) — для альбома времён года."""
    rows = (await db.execute(select(Word).where(func.lower(Word.text_tt).in_(list(SEASON_SIGNS))))).scalars().all()
    return [word_dto(w) for w in rows if allowed is None or w.theme_id in allowed]


async def clothes_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Одежда с картинкой — для сюжета «одень по погоде». Только если тема пройдена."""
    rows = (await db.execute(select(Word).join(Theme, Theme.id == Word.theme_id)
                             .where(Theme.title_ru == "Одежда и обувь"))).scalars().all()
    return [word_dto(w) for w in rows if allowed is None or w.theme_id in allowed]


async def sort_scenario_words(db: AsyncSession) -> dict[str, list[dict]]:
    """Слова тех тем, что участвуют в сводных сортировках («портфель», «магазины»)."""
    names = {t for sc in SORT_SCENARIOS for b in sc["baskets"] for t in b["themes"]}
    rows = (await db.execute(select(Word, Theme.title_ru).join(Theme, Theme.id == Word.theme_id)
                             .where(Theme.title_ru.in_(names)))).all()
    out: dict[str, list[dict]] = {}
    for w, title in rows:
        out.setdefault(title, []).append(word_dto(w))
    return out


async def place_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Послелоги места — их сцену фронт рисует сам, картинка в базе не нужна."""
    rows = (await db.execute(select(Word).where(
        func.lower(Word.text_tt).in_(list(PLACE_SCENES))))).scalars().all()
    return [word_dto(w) for w in rows
            if (allowed is None or w.theme_id in allowed) and (w.audio_url or w.tts_url)]


async def mood_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Состояния для «Нигә?» — берём всю тему, а не только слова с причиной:
    остальные нужны как дистракторы."""
    theme = (await db.execute(select(Theme).where(Theme.title_ru == MOOD_THEME))).scalar_one_or_none()
    if not theme or (allowed is not None and theme.id not in allowed):
        return []
    rows = (await db.execute(select(Word).where(Word.theme_id == theme.id))).scalars().all()
    return [word_dto(w) for w in rows if (w.audio_url or w.tts_url)]


NUMBERS_THEME = "Цифры"


async def count_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Предметы, для которых предозвучены связки «ике алма … биш алма».
    Пока не пройдены сами числительные, формат молчит: иначе ребёнок впервые
    слышит «өч» в задании, где надо выбрать между тремя незнакомыми словами."""
    from ..tts import cached_tts_url
    numbers = (await db.execute(select(Theme).where(Theme.title_ru == NUMBERS_THEME))).scalar_one_or_none()
    if not numbers or (allowed is not None and numbers.id not in allowed):
        return []
    rows = (await db.execute(select(Word).where(
        func.lower(Word.text_tt).in_(list(COUNTABLE_TT))))).scalars().all()
    out = []
    for w in rows:
        if allowed is not None and w.theme_id not in allowed:
            continue
        dto = word_dto(w)
        if not _has_photo(dto) or not cached_tts_url(f"Ничә {w.text_tt.lower()}?"):
            continue
        out.append(dto)
    return out


async def plural_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Слова, у которых есть выверенная форма мн. ч. И картинка «много предметов»."""
    import os

    from ..config import STATIC_DIR
    from ..forms import PLURAL_TT
    rows = (await db.execute(select(Word).where(func.lower(Word.text_tt).in_(list(PLURAL_TT))))).scalars().all()
    out = []
    for w in rows:
        if not w.image_url or "noimg" in (w.image_url or ""):
            continue
        if allowed is not None and w.theme_id not in allowed:
            continue
        if os.path.isfile(os.path.join(STATIC_DIR, "image", "plural", f"word_{w.id}.png")):
            out.append(word_dto(w))
    return out


async def learned_theme_ids(db: AsyncSession, up_to_order: Optional[int]) -> set:
    """Темы, пройденные к этому месту пути. Бонусные форматы обязаны брать слова
    только отсюда — иначе в первом же уроке всплывают слова из 20-го юнита."""
    q = select(Theme.id)
    if up_to_order is not None:
        q = q.where(Theme.order_index < up_to_order)
    return {r[0] for r in (await db.execute(q)).all()}


async def verb_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Глаголы с выверенным отрицанием и картинкой — для тренажёра «Юк, ул йөзми»."""
    from ..forms import NEGATIVE_TT
    rows = (await db.execute(select(Word).where(func.lower(Word.text_tt).in_(list(NEGATIVE_TT))))).scalars().all()
    return [word_dto(w) for w in rows
            if w.image_url and "noimg" not in (w.image_url or "")
            and (allowed is None or w.theme_id in allowed)]


async def with_what_words(db: AsyncSession, allowed: Optional[set] = None) -> list[dict]:
    """Слова-инструменты для «Нәрсә белән?» — лежат в разных темах (пенал, кухня)."""
    names = list(WITH_WHAT.values())
    rows = (await db.execute(select(Word).where(func.lower(Word.text_tt).in_(names)))).scalars().all()
    return [word_dto(w) for w in rows if allowed is None or w.theme_id in allowed]


async def edible_theme_ids(db: AsyncSession) -> set:
    """id тем с едой — где «Покорми Акбая» уместно (для смешанной тренировки)."""
    rows = (await db.execute(select(Theme.id).where(Theme.title_ru.in_(EDIBLE_THEMES)))).all()
    return {r[0] for r in rows}


async def phrase_theme_ids(db: AsyncSession) -> set:
    """id фразовых тем (фразы, местоимения, вопросительные слова) — у них нет
    собственных картинок, картиночные задания там неразрешимы: все варианты
    выглядят одинаково (эмодзи-заглушки)."""
    rows = (await db.execute(select(Theme.id).where(Theme.title_ru.in_(PHRASE_THEMES)))).all()
    return {r[0] for r in rows}


def _practice_items(words: list[dict], pool: list[dict], limit: int = 10,
                    feed_theme_ids: Optional[set] = None,
                    phrase_ids: Optional[set] = None) -> list[dict]:
    """Практика без карточек — для тренировки/трудных слов."""
    random.shuffle(words)
    items: list[dict] = []
    for w in words[:limit]:
        if phrase_ids and w.get("theme_id") in phrase_ids:
            # фразовое слово: только на слух — выбор звучания и повтор за диктором
            gens = [lambda: ex_pick_word_audio(w, pool)]
            if w["audio_url"]:
                gens.append(lambda: ex_repeat_after(w))
            random.shuffle(gens)
            for g in gens:
                e = g()
                if e:
                    items.append(e)
                    break
            continue
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
            "items": _practice_items(dtos, pool, limit=8, feed_theme_ids=await edible_theme_ids(db),
                                     phrase_ids=await phrase_theme_ids(db)),
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
        items = _practice_items(list(pool), pool, limit=8, feed_theme_ids=feed_ids,
                                phrase_ids=await phrase_theme_ids(db))
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

    # новое задание дня: повторение (главный канал SRS) + немного нового из текущего юнита;
    # незакрытые ошибки — в приоритете перед плановым повторением
    review = await due_review_words(db, user, DAILY_REVIEW_LIMIT)
    mistake_words = await pending_mistake_words(db, user, 4, {w["id"] for w in review})
    if mistake_words:
        review = mistake_words + review[:max(0, DAILY_REVIEW_LIMIT - len(mistake_words))]

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

    learned = await learned_theme_ids(db, current_unit.order_index)
    items = build_exercises(fresh, pool, review, phrase_mode=current_unit.title_ru in PHRASE_THEMES,
                            sentences_ok=True, feed_ok=current_unit.title_ru in EDIBLE_THEMES,
                            qneg_ok=current_unit.title_ru in QNEG_THEMES,
                            animate_theme=current_unit.title_ru in ANIMATE_THEMES,
                            with_what_pool=await with_what_words(db, learned),
                            verb_pool=await verb_words(db, learned),
                            plural_pool=await plural_words(db, learned),
                            sort_words=await sort_scenario_words(db),
                            clothes_pool=await clothes_words(db, learned),
                            season_pool=await season_words(db, learned))
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
