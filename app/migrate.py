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
    },
    "words": {
        "emoji": "VARCHAR(16)",
        "tts_url": "VARCHAR(255)",
        "image_flag": "INTEGER DEFAULT 0",
    },
    "user_progress": {
        "strength": "INTEGER DEFAULT 0",
        "due_at": "DATETIME",
        "seen_count": "INTEGER DEFAULT 0",
        "correct_count": "INTEGER DEFAULT 0",
        "first_seen_at": "DATETIME",
    },
}


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
