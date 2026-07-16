import io
import time
import zipfile
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_admin
from ..database import get_db
from ..models import Theme, Word
from ..tts import synthesize_to_file

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/theme_create")
async def theme_create(
    title_ru: str = Form(...),
    description: Optional[str] = Form(None),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    existing = (await db.execute(select(Theme).where(Theme.title_ru == title_ru))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Тема с таким названием уже существует")
    theme = Theme(title_ru=title_ru, description=description)
    db.add(theme)
    await db.commit()
    await db.refresh(theme)
    return {"id": theme.id, "title_ru": theme.title_ru}


@router.post("/upload_zip")
async def upload_zip(
    theme_title_ru: str,
    file: UploadFile = File(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    if not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Ожидается ZIP архив")

    data = await file.read()
    zf = zipfile.ZipFile(io.BytesIO(data))

    # CSV format: text_ru,text_tt,image_path,audio_path
    # media files should be placed in the zip and referenced by relative path
    csv_name = None
    for name in zf.namelist():
        if name.lower().endswith('.csv'):
            csv_name = name
            break
    if not csv_name:
        raise HTTPException(status_code=400, detail="В архиве отсутствует CSV файл")

    # Ensure theme exists
    theme = (await db.execute(select(Theme).where(Theme.title_ru == theme_title_ru))).scalar_one_or_none()
    if not theme:
        theme = Theme(title_ru=theme_title_ru)
        db.add(theme)
        await db.flush()

    # Extract media to static if paths start with media/
    # We will stream out needed files into /static/uploads/
    from pathlib import Path
    from ..config import STATIC_DIR

    upload_root = Path(STATIC_DIR) / 'uploads'
    upload_root.mkdir(parents=True, exist_ok=True)

    def save_member(member_path: str) -> str:
        try:
            member = zf.getinfo(member_path)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Файл {member_path} отсутствует в ZIP")
        target = upload_root / member.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('wb') as f:
            f.write(zf.read(member))
        return '/static/uploads/' + member.filename.replace('\\', '/').replace('..', '')

    import csv
    reader = csv.reader(io.TextIOWrapper(zf.open(csv_name), encoding='utf-8'))

    added = 0
    updated = 0
    skipped = 0
    for row in reader:
        if not row or row[0].startswith('#'):
            continue
        try:
            text_ru, text_tt, image_path, audio_path = (row + ['','','',''])[:4]
        except Exception:
            raise HTTPException(status_code=400, detail="Неверный формат CSV (ожидается 4 колонки)")

        image_url = None
        audio_url = None
        if image_path:
            image_url = save_member(image_path)
        if audio_path:
            audio_url = save_member(audio_path)

        existing = (await db.execute(select(Word).where(Word.theme_id == theme.id, Word.text_tt == text_tt.strip()))).scalar_one_or_none()
        if existing:
            existing.text_ru = text_ru.strip() or existing.text_ru
            existing.image_url = image_url or existing.image_url
            existing.audio_url = audio_url or existing.audio_url
            updated += 1
        else:
            db.add(Word(theme_id=theme.id, text_tt=text_tt.strip(), text_ru=text_ru.strip(), image_url=image_url, audio_url=audio_url))
            added += 1
    await db.commit()

    return {"added": added, "updated": updated, "skipped": skipped, "theme_id": theme.id}


@router.post("/words_csv")
async def words_csv(
    file: UploadFile = File(...),
    theme_id: Optional[int] = Form(None),
    theme_title_ru: Optional[str] = Form(None),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    if not file.filename.lower().endswith('.csv'):
        raise HTTPException(status_code=400, detail="Ожидается CSV файл")

    # Resolve theme
    theme = None
    if theme_id is not None:
        theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
    elif theme_title_ru:
        theme = (await db.execute(select(Theme).where(Theme.title_ru == theme_title_ru))).scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Тема не найдена")

    data = await file.read()
    import csv
    reader = csv.reader(io.StringIO(data.decode('utf-8')))
    added = 0
    updated = 0
    skipped = 0
    for row in reader:
        if not row or row[0].startswith('#'):
            continue
        # CSV format: text_ru,text_tt,image_url,audio_url
        try:
            text_ru, text_tt, image_url, audio_url = (row + ['','','',''])[:4]
        except Exception:
            raise HTTPException(status_code=400, detail="Неверный формат CSV (ожидается 4 колонки)")

        existing = (await db.execute(select(Word).where(Word.theme_id == theme.id, Word.text_tt == text_tt.strip()))).scalar_one_or_none()
        if existing:
            existing.text_ru = text_ru.strip() or existing.text_ru
            existing.image_url = (image_url or None) or existing.image_url
            existing.audio_url = (audio_url or None) or existing.audio_url
            updated += 1
        else:
            db.add(Word(theme_id=theme.id, text_tt=text_tt.strip(), text_ru=text_ru.strip(), image_url=(image_url or None), audio_url=(audio_url or None)))
            added += 1
    await db.commit()
    return {"added": added, "updated": updated, "skipped": skipped, "theme_id": theme.id}


@router.post("/words_json")
async def words_json(
    payload: dict = Body(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    theme_id = payload.get('theme_id')
    theme_title_ru = payload.get('theme_title_ru')
    words = payload.get('words', [])

    theme = None
    if theme_id is not None:
        theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
    elif theme_title_ru:
        theme = (await db.execute(select(Theme).where(Theme.title_ru == theme_title_ru))).scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Тема не найдена")

    added = 0
    updated = 0
    skipped = 0
    for item in words:
      text_ru = (item.get('text_ru') or '').strip()
      text_tt = (item.get('text_tt') or '').strip()
      image_url = item.get('image_url') or None
      audio_url = item.get('audio_url') or None
      if not text_ru or not text_tt:
          skipped += 1
          continue
      existing = (await db.execute(select(Word).where(Word.theme_id == theme.id, Word.text_tt == text_tt))).scalar_one_or_none()
      if existing:
          existing.text_ru = text_ru or existing.text_ru
          existing.image_url = image_url or existing.image_url
          existing.audio_url = audio_url or existing.audio_url
          updated += 1
      else:
          db.add(Word(theme_id=theme.id, text_tt=text_tt, text_ru=text_ru, image_url=image_url, audio_url=audio_url))
          added += 1
    await db.commit()
    return {"added": added, "updated": updated, "skipped": skipped, "theme_id": theme.id}


@router.post("/import_units")
async def import_units(
    payload: dict = Body(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    """Bulk import of learning-path units.

    payload = {"units": [{"title_ru", "title_tt", "icon_emoji", "order_index",
                          "words": [{"text_ru", "text_tt", "emoji"}]}]}
    """
    def norm(s: str) -> str:
        return s.strip().lower().replace('ё', 'е')

    units = payload.get('units', [])
    skip_existing_global = bool(payload.get('skip_existing_global'))
    existing_tt: set[str] = set()
    existing_ru: set[str] = set()
    if skip_existing_global:
        rows = (await db.execute(select(Word.text_tt, Word.text_ru))).all()
        existing_tt = {norm(tt) for tt, _ in rows}
        existing_ru = {norm(ru) for _, ru in rows}
    themes_added = 0
    added = 0
    updated = 0
    skipped_global = 0
    for unit in units:
        title_ru = (unit.get('title_ru') or '').strip()
        if not title_ru:
            continue
        theme = (await db.execute(select(Theme).where(Theme.title_ru == title_ru))).scalar_one_or_none()
        if not theme:
            theme = Theme(title_ru=title_ru)
            db.add(theme)
            themes_added += 1
        theme.title_tt = unit.get('title_tt') or theme.title_tt
        theme.icon_emoji = unit.get('icon_emoji') or theme.icon_emoji
        if unit.get('order_index') is not None:
            theme.order_index = unit['order_index']
        theme.description = unit.get('description') or theme.description
        await db.flush()

        for item in unit.get('words', []):
            text_ru = (item.get('text_ru') or '').strip()
            text_tt = (item.get('text_tt') or '').strip()
            if not text_ru or not text_tt:
                continue
            existing = (await db.execute(select(Word).where(Word.theme_id == theme.id, Word.text_tt == text_tt))).scalar_one_or_none()
            if existing:
                existing.text_ru = text_ru
                existing.emoji = item.get('emoji') or existing.emoji
                updated += 1
            elif skip_existing_global and (norm(text_tt) in existing_tt or norm(text_ru) in existing_ru):
                skipped_global += 1
            else:
                db.add(Word(theme_id=theme.id, text_tt=text_tt, text_ru=text_ru, emoji=item.get('emoji')))
                existing_tt.add(norm(text_tt))
                existing_ru.add(norm(text_ru))
                added += 1
    await db.commit()
    return {"themes_added": themes_added, "words_added": added, "words_updated": updated, "skipped_global": skipped_global}


@router.post("/tts_word/{word_id}")
async def tts_word(
    word_id: int,
    voice: str = "alsu",
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    if voice not in ("alsu", "almaz"):
        raise HTTPException(status_code=400, detail="voice: alsu или almaz")
    word = (await db.execute(select(Word).where(Word.id == word_id))).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Слово не найдено")
    try:
        word.tts_url = await synthesize_to_file(word.text_tt, speaker=voice)
        word.audio_url = None  # свежая озвучка главнее старой записи
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка TTS: {e}")
    await db.commit()
    return {"word_id": word.id, "tts_url": word.tts_url}


@router.post("/word_audio/{word_id}")
async def word_audio(
    word_id: int,
    file: UploadFile = File(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    """Загрузка собственной записи слова (заменяет и запись, и TTS)."""
    word = (await db.execute(select(Word).where(Word.id == word_id))).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Слово не найдено")
    ext = (file.filename or 'a.wav').rsplit('.', 1)[-1].lower()
    if ext not in ('wav', 'mp3', 'ogg', 'webm', 'm4a'):
        raise HTTPException(status_code=400, detail="Ожидается аудио (wav/mp3/ogg/webm/m4a)")
    from pathlib import Path
    from ..config import STATIC_DIR
    target_dir = Path(STATIC_DIR) / 'voice' / 'uploads'
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"word_{word.id}.{ext}"
    target.write_bytes(await file.read())
    word.audio_url = f"/static/voice/uploads/{target.name}?v={int(time.time())}"  # cache-bust при перезаписи
    await db.commit()
    return {"word_id": word.id, "audio_url": word.audio_url}


@router.post("/tts_all")
async def tts_all(
    limit: int = 500,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    """Synthesize speech for every word that has neither recorded audio nor cached TTS."""
    words = (await db.execute(
        select(Word).where(Word.audio_url.is_(None), Word.tts_url.is_(None)).limit(limit)
    )).scalars().all()
    done = 0
    errors: list[str] = []
    for w in words:
        try:
            w.tts_url = await synthesize_to_file(w.text_tt)
            done += 1
            await db.commit()
        except Exception as e:
            errors.append(f"{w.text_tt}: {e}")
            if len(errors) >= 5:
                break
    return {"done": done, "remaining_errors": errors}


@router.post("/import_sentences")
async def import_sentences(
    payload: dict = Body(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    """Массовая загрузка предложений: {"items": [{"id", "sentence_tt", "sentence_ru"}]}."""
    done, skipped = 0, 0
    for item in payload.get("items", []):
        word = (await db.execute(select(Word).where(Word.id == item.get("id")))).scalar_one_or_none()
        if not word:
            skipped += 1
            continue
        st = (item.get("sentence_tt") or "").strip() or None
        if st and len(st) > 200:
            skipped += 1
            continue
        word.sentence_tt = st
        word.sentence_ru = (item.get("sentence_ru") or "").strip() or None
        word.sentence_audio_url = None  # переозвучить
        done += 1
    await db.commit()
    return {"done": done, "skipped": skipped}


@router.post("/sentence/{word_id}")
async def set_sentence(
    word_id: int,
    payload: dict = Body(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    word = (await db.execute(select(Word).where(Word.id == word_id))).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Слово не найдено")
    st = (payload.get("sentence_tt") or "").strip() or None
    if st and len(st) > 200:
        raise HTTPException(status_code=400, detail="Предложение слишком длинное (максимум 200 символов)")
    word.sentence_tt = st
    word.sentence_ru = ((payload.get("sentence_ru") or "").strip() or None)
    if word.sentence_ru and len(word.sentence_ru) > 200:
        raise HTTPException(status_code=400, detail="Перевод слишком длинный (максимум 200 символов)")
    word.sentence_audio_url = None
    if word.sentence_tt:
        try:
            word.sentence_audio_url = await synthesize_to_file(word.sentence_tt)
            # плитки конструктора должны звучать — озвучиваем каждый токен
            import re as _re
            for tok in _re.split(r"[^\wәөүҗңһӘӨҮҖҢҺ-]+", word.sentence_tt):
                if tok:
                    try:
                        await synthesize_to_file(tok.lower())
                    except Exception:
                        pass
        except Exception:
            pass  # озвучится через tts_sentences_all
    await db.commit()
    return {"word_id": word.id, "sentence_tt": word.sentence_tt,
            "sentence_ru": word.sentence_ru, "sentence_audio_url": word.sentence_audio_url}


@router.post("/tts_sentence/{word_id}")
async def tts_sentence(
    word_id: int,
    voice: str = "alsu",
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    if voice not in ("alsu", "almaz"):
        raise HTTPException(status_code=400, detail="voice: alsu или almaz")
    word = (await db.execute(select(Word).where(Word.id == word_id))).scalar_one_or_none()
    if not word or not word.sentence_tt:
        raise HTTPException(status_code=404, detail="Нет слова или предложения")
    try:
        word.sentence_audio_url = await synthesize_to_file(word.sentence_tt, speaker=voice)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка TTS: {e}")
    await db.commit()
    return {"word_id": word.id, "sentence_audio_url": word.sentence_audio_url}


@router.post("/tts_sentences_all")
async def tts_sentences_all(
    limit: int = 500,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    words = (await db.execute(
        select(Word).where(Word.sentence_tt.is_not(None), Word.sentence_audio_url.is_(None)).limit(limit)
    )).scalars().all()
    done, errors = 0, []
    for w in words:
        try:
            w.sentence_audio_url = await synthesize_to_file(w.sentence_tt)
            done += 1
            await db.commit()
        except Exception as e:
            errors.append(f"{w.text_tt}: {e}")
            if len(errors) >= 5:
                break
    return {"done": done, "remaining_errors": errors}


@router.post("/tts_tokens")
async def tts_tokens(
    payload: dict = Body(...),
    admin = Depends(get_current_admin),
):
    """Озвучка отдельных токенов (служебные слова для конструктора предложений)."""
    done, errors = 0, []
    for tok in payload.get("tokens", [])[:200]:
        tok = (tok or "").strip().lower()
        if not tok:
            continue
        try:
            await synthesize_to_file(tok)
            done += 1
        except Exception as e:
            errors.append(f"{tok}: {e}")
    return {"done": done, "errors": errors}


@router.post("/word_flag/{word_id}")
async def word_flag(
    word_id: int,
    flagged: bool = True,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    """Пометка «картинка неадекватная» — для последующей ручной замены/перегенерации."""
    word = (await db.execute(select(Word).where(Word.id == word_id))).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Слово не найдено")
    word.image_flag = 1 if flagged else 0
    await db.commit()
    return {"word_id": word.id, "image_flag": word.image_flag}


@router.post("/word_image/{word_id}")
async def word_image(
    word_id: int,
    file: UploadFile = File(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    admin = Depends(get_current_admin),
):
    word = (await db.execute(select(Word).where(Word.id == word_id))).scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="Слово не найдено")
    ext = (file.filename or 'img.png').rsplit('.', 1)[-1].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'webp', 'svg'):
        raise HTTPException(status_code=400, detail="Ожидается изображение (png/jpg/webp/svg)")

    from pathlib import Path
    from ..config import STATIC_DIR
    target_dir = Path(STATIC_DIR) / 'image' / 'uploads'
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"word_{word.id}.{ext}"
    target.write_bytes(await file.read())
    word.image_url = f"/static/image/uploads/{target.name}?v={int(time.time())}"  # cache-bust при перезаписи
    await db.commit()
    return {"word_id": word.id, "image_url": word.image_url}
