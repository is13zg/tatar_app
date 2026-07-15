from sqlalchemy.ext.asyncio import AsyncEngine


async def migrate_sqlite(engine: AsyncEngine) -> None:
    # Add is_admin column to users if missing
    async with engine.begin() as conn:
        res = await conn.exec_driver_sql("PRAGMA table_info(users)")
        cols = [row[1] for row in res.fetchall()]  # row: (cid, name, type, notnull, dflt_value, pk)
        if 'is_admin' not in cols:
            await conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")
