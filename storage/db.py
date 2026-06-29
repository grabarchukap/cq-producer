import logging
from pathlib import Path
import aiosqlite

logger = logging.getLogger(__name__)

_DB_PATH = str(Path(__file__).parent / "posts.db")


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(_DB_PATH) as db:
        # WAL mode: readers never block writers and writers never block readers.
        # Essential for concurrent access — is_allowed() runs on every message.
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id  INTEGER PRIMARY KEY,
                username TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                author_id  TEXT,
                raw_input  TEXT,
                final_post TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
    logger.info("Database ready: %s", _DB_PATH)


async def is_allowed(user_id: int) -> bool:
    async with aiosqlite.connect(_DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,)
        ) as cur:
            return await cur.fetchone() is not None


async def add_user(user_id: int, username: str | None = None) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO whitelist (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.commit()


async def remove_user(user_id: int) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
        await db.commit()


async def list_users() -> list[dict]:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username, added_at FROM whitelist ORDER BY added_at"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def save_post(
    user_id: int, author_id: str, raw_input: str, final_post: str
) -> None:
    """Persist a generated post. Disabled by default — called only when enabled."""
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT INTO posts (user_id, author_id, raw_input, final_post) VALUES (?, ?, ?, ?)",
            (user_id, author_id, raw_input, final_post),
        )
        await db.commit()
