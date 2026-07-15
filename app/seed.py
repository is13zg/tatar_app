from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Theme, Word


async def seed_if_empty(db: AsyncSession) -> None:
    existing = (await db.execute(select(Theme))).scalars().first()
    if existing:
        return

    theme = Theme(title_ru="Животные", description="Базовые животные")
    db.add(theme)
    await db.flush()

    words = [
        Word(theme_id=theme.id, text_tt="песи", text_ru="кот", image_url="/static/noimg.png"),
        Word(theme_id=theme.id, text_tt="эт", text_ru="собака", image_url="/static/noimg.png"),
        Word(theme_id=theme.id, text_tt="сыер", text_ru="корова", image_url="/static/noimg.png"),
        Word(theme_id=theme.id, text_tt="ат", text_ru="лошадь", image_url="/static/noimg.png"),
    ]
    for w in words:
        db.add(w)
    await db.commit()
