import io
import zipfile
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_admin
from ..database import get_db
from ..models import Theme, Word

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
