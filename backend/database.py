# database.py — SQLite database for users, usage tracking, and enhancement jobs.

import aiosqlite
import os

DB_PATH = os.getenv("DB_PATH", "develop.db")


async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                device_id TEXT PRIMARY KEY,
                tier TEXT NOT NULL DEFAULT 'free',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS usage (
                device_id TEXT NOT NULL,
                period TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (device_id, period)
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processing',
                scene_type TEXT,
                style TEXT DEFAULT 'natural',
                image_base64 TEXT,
                image_format TEXT DEFAULT 'png',
                error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_device ON jobs(device_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """)
        await db.commit()


async def get_db():
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def ensure_user(db: aiosqlite.Connection, device_id: str):
    """Create user record if it doesn't exist. Returns tier."""
    row = await db.execute_fetchall(
        "SELECT tier FROM users WHERE device_id = ?", (device_id,)
    )
    if row:
        return row[0][0]

    await db.execute(
        "INSERT INTO users (device_id) VALUES (?)", (device_id,)
    )
    await db.commit()
    return "free"


async def get_usage(db: aiosqlite.Connection, device_id: str, period: str) -> int:
    """Get enhancement count for a device in a given period."""
    row = await db.execute_fetchall(
        "SELECT count FROM usage WHERE device_id = ? AND period = ?",
        (device_id, period),
    )
    return row[0][0] if row else 0


async def increment_usage(db: aiosqlite.Connection, device_id: str, period: str):
    """Increment usage count. Creates the record if it doesn't exist."""
    await db.execute(
        """INSERT INTO usage (device_id, period, count) VALUES (?, ?, 1)
           ON CONFLICT(device_id, period) DO UPDATE SET count = count + 1""",
        (device_id, period),
    )
    await db.commit()


async def create_job(
    db: aiosqlite.Connection,
    job_id: str,
    device_id: str,
    scene_type: str,
    style: str,
):
    """Create a new enhancement job."""
    await db.execute(
        "INSERT INTO jobs (job_id, device_id, scene_type, style) VALUES (?, ?, ?, ?)",
        (job_id, device_id, scene_type, style),
    )
    await db.commit()


async def complete_job(
    db: aiosqlite.Connection,
    job_id: str,
    image_base64: str,
    image_format: str = "png",
):
    """Mark a job as completed with the result image."""
    await db.execute(
        """UPDATE jobs SET status = 'completed', image_base64 = ?, image_format = ?,
           completed_at = datetime('now') WHERE job_id = ?""",
        (image_base64, image_format, job_id),
    )
    await db.commit()


async def fail_job(db: aiosqlite.Connection, job_id: str, error: str):
    """Mark a job as failed."""
    await db.execute(
        """UPDATE jobs SET status = 'failed', error = ?,
           completed_at = datetime('now') WHERE job_id = ?""",
        (error, job_id),
    )
    await db.commit()


async def get_job(db: aiosqlite.Connection, job_id: str) -> dict | None:
    """Get a job by ID."""
    rows = await db.execute_fetchall(
        "SELECT job_id, status, image_base64, image_format, error FROM jobs WHERE job_id = ?",
        (job_id,),
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "job_id": r[0],
        "status": r[1],
        "image_base64": r[2],
        "image_format": r[3],
        "error": r[4],
    }


async def update_user_tier(db: aiosqlite.Connection, device_id: str, tier: str):
    """Update a user's subscription tier."""
    await db.execute(
        "UPDATE users SET tier = ? WHERE device_id = ?", (tier, device_id)
    )
    await db.commit()


async def cleanup_old_jobs(db: aiosqlite.Connection):
    """Delete completed/failed jobs older than 24 hours to free space."""
    await db.execute(
        """DELETE FROM jobs
           WHERE status IN ('completed', 'failed')
           AND created_at < datetime('now', '-1 day')"""
    )
    await db.commit()
