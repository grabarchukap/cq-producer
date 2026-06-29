import json
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                username   TEXT,
                answers    TEXT,
                status     TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notifiers (
                user_id  INTEGER PRIMARY KEY,
                username TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
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


async def save_case(
    user_id: int, username: str | None, answers: list[dict]
) -> int:
    """Persist case interview answers with status=pending (awaiting export)."""
    async with aiosqlite.connect(_DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO cases (user_id, username, answers) VALUES (?, ?, ?)",
            (user_id, username, json.dumps(answers, ensure_ascii=False)),
        )
        await db.commit()
        return cur.lastrowid


async def delete_case(case_id: int) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        await db.commit()


async def update_case_status(case_id: int, status: str) -> None:
    """Update case export status: 'pending' | 'done' | 'failed'."""
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "UPDATE cases SET status = ? WHERE id = ?", (status, case_id)
        )
        await db.commit()


async def get_pending_cases() -> list[dict]:
    """Return all cases with status='pending'."""
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, user_id, username, answers, created_at FROM cases WHERE status = 'pending' ORDER BY created_at"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def add_notifier(user_id: int, username: str | None = None) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO notifiers (user_id, username) VALUES (?, ?)",
            (user_id, username),
        )
        await db.commit()


async def remove_notifier(user_id: int) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute("DELETE FROM notifiers WHERE user_id = ?", (user_id,))
        await db.commit()


async def list_notifiers() -> list[dict]:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, username FROM notifiers ORDER BY added_at"
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
