from sqlalchemy.ext.asyncio import AsyncEngine

# table -> {column: DDL type/default}
_COLUMNS: dict[str, dict[str, str]] = {
    "users": {
        "is_admin": "BOOLEAN DEFAULT 0",
    },
    "themes": {
        "title_tt": "VARCHAR(120)",
        "icon_emoji": "VARCHAR(16)",
        "order_index": "INTEGER DEFAULT 0",
        # когда владелец сам прошёл тему руками; NULL = ещё не проверял
        "checked_at": "DATETIME",
        "checked_note": "VARCHAR(200)",
    },
    "words": {
        "emoji": "VARCHAR(16)",
        "tts_url": "VARCHAR(255)",
        "image_flag": "INTEGER DEFAULT 0",
        "sentence_tt": "VARCHAR(255)",
        "sentence_ru": "VARCHAR(255)",
        "sentence_audio_url": "VARCHAR(255)",
        "image_prompt": "TEXT",
    },
    "phrase_images": {
        "audio_url": "VARCHAR(255)",
    },
    "user_progress": {
        "strength": "INTEGER DEFAULT 0",
        "due_at": "DATETIME",
        "seen_count": "INTEGER DEFAULT 0",
        "correct_count": "INTEGER DEFAULT 0",
        "first_seen_at": "DATETIME",
    },
}


async def _relax_phrase_images(conn) -> None:
    """У phrase_images.image_url снимаем NOT NULL.

    Таблица родилась, когда картинка была единственным содержимым строки; теперь
    у фразы может быть только своя озвучка. SQLite не умеет менять ограничение
    столбца, поэтому пересобираем таблицу, перенося данные."""
    res = await conn.exec_driver_sql("PRAGMA table_info(phrase_images)")
    cols = res.fetchall()
    if not cols:
        return
    img = [c for c in cols if c[1] == "image_url"]
    if not img or not img[0][3]:      # notnull == 0 — уже всё в порядке
        return
    await conn.exec_driver_sql("ALTER TABLE phrase_images RENAME TO phrase_images_old")
    await conn.exec_driver_sql(
        "CREATE TABLE phrase_images ("
        " id INTEGER PRIMARY KEY,"
        " phrase VARCHAR(255) NOT NULL UNIQUE,"
        " image_url VARCHAR(255),"
        " audio_url VARCHAR(255),"
        " updated_at DATETIME)")
    old = [c[1] for c in cols]
    shared = [c for c in ("phrase", "image_url", "audio_url", "updated_at") if c in old]
    await conn.exec_driver_sql(
        "INSERT INTO phrase_images (%s) SELECT %s FROM phrase_images_old"
        % (", ".join(shared), ", ".join(shared)))
    await conn.exec_driver_sql("DROP TABLE phrase_images_old")
    await conn.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_phrase_images_phrase ON phrase_images (phrase)")


async def migrate_sqlite(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for table, columns in _COLUMNS.items():
            res = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
            existing = [row[1] for row in res.fetchall()]  # row: (cid, name, type, notnull, dflt_value, pk)
            if not existing:
                continue  # table doesn't exist yet, create_all handles it
            for col, ddl in columns.items():
                if col not in existing:
                    await conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        await _relax_phrase_images(conn)
