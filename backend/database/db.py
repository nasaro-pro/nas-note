from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from backend.config import settings

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def db_path() -> Path:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "logs").mkdir(exist_ok=True)
    return settings.data_dir / "nas-note.db"


async def connect() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path())
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("PRAGMA journal_mode=WAL")
    return conn


async def init_db() -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = await connect()
    try:
        await conn.executescript(sql)
        try:
            await conn.execute("ALTER TABLE projects ADD COLUMN video_url TEXT")
        except Exception:
            pass
        try:
            await conn.execute("ALTER TABLE analyses ADD COLUMN extracted_info TEXT")
        except Exception:
            pass
        await conn.commit()
    finally:
        await conn.close()


async def fetchone(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    conn = await connect()
    try:
        cur = await conn.execute(sql, params)
        row = await cur.fetchone()
        return dict(row) if row else None
    finally:
        await conn.close()


async def fetchall(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = await connect()
    try:
        cur = await conn.execute(sql, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def execute(sql: str, params: tuple = ()) -> int:
    conn = await connect()
    try:
        cur = await conn.execute(sql, params)
        await conn.commit()
        return cur.lastrowid or 0
    finally:
        await conn.close()


async def execute_many(sql: str, seq: list[tuple]) -> None:
    conn = await connect()
    try:
        await conn.executemany(sql, seq)
        await conn.commit()
    finally:
        await conn.close()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
