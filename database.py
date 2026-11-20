import os
import json
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

import aiosqlite

try:
    import asyncpg
except ImportError:
    asyncpg = None

logger = logging.getLogger("database")

# Global asyncpg pool reference
_pg_pool: Optional[Any] = None


def get_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_type() -> str:
    """
    Returns 'postgres' if DATABASE_URL is configured in environment,
    otherwise falls back cleanly to 'sqlite'.
    """
    url = os.getenv("DATABASE_URL", "").strip()
    return "postgres" if url else "sqlite"


def get_sqlite_path() -> str:
    """
    Returns the path to the SQLite database file, defaulting to 'aerovault.db'.
    If 'cloud_storage.db' exists from a previous installation and no custom path is set,
    it continues to use 'cloud_storage.db' to preserve data.
    """
    custom = os.getenv("DATABASE_PATH")
    if custom:
        return custom
    if os.path.exists("aerovault.db"):
        return "aerovault.db"
    if os.path.exists("cloud_storage.db"):
        return "cloud_storage.db"
    return "aerovault.db"


async def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        if asyncpg is None:
            raise RuntimeError("asyncpg is required for PostgreSQL. Please install asyncpg.")
        
        raw_url = os.getenv("DATABASE_URL", "").strip()
        if not raw_url:
            raise RuntimeError("DATABASE_URL environment variable is not set.")

        # Normalize postgres:// scheme to postgresql://
        if raw_url.startswith("postgres://"):
            raw_url = "postgresql://" + raw_url[len("postgres://"):]

        logger.info("Connecting to PostgreSQL database via asyncpg...")
        _pg_pool = await asyncpg.create_pool(
            dsn=raw_url,
            min_size=1,
            max_size=10,
            command_timeout=60.0
        )
    return _pg_pool


async def close_db():
    """
    Closes the PostgreSQL connection pool if open.
    """
    global _pg_pool
    if _pg_pool is not None:
        logger.info("Closing PostgreSQL connection pool...")
        await _pg_pool.close()
        _pg_pool = None


def _format_query_for_pg(query: str) -> str:
    """
    Translates standard '?' parameter placeholders into asyncpg positional placeholders ($1, $2, ...).
    """
    parts = query.split("?")
    if len(parts) <= 1:
        return query
    output = []
    for idx, part in enumerate(parts[:-1], start=1):
        output.append(f"{part}${idx}")
    output.append(parts[-1])
    return "".join(output)


# Unified execution and query helpers
async def execute(query: str, params: tuple = ()) -> None:
    if get_db_type() == "postgres":
        pool = await get_pg_pool()
        pg_query = _format_query_for_pg(query)
        async with pool.acquire() as conn:
            await conn.execute(pg_query, *params)
    else:
        db_path = get_sqlite_path()
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute(query, params)
            await conn.commit()


async def fetch_one(query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
    if get_db_type() == "postgres":
        pool = await get_pg_pool()
        pg_query = _format_query_for_pg(query)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(pg_query, *params)
            return dict(row) if row else None
    else:
        db_path = get_sqlite_path()
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            async with conn.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None


async def fetch_all(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    if get_db_type() == "postgres":
        pool = await get_pg_pool()
        pg_query = _format_query_for_pg(query)
        async with pool.acquire() as conn:
            rows = await conn.fetch(pg_query, *params)
            return [dict(r) for r in rows]
    else:
        db_path = get_sqlite_path()
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON;")
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]


@asynccontextmanager
async def get_db():
    """
    Context manager for backward compatibility.
    """
    if get_db_type() == "postgres":
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            yield conn
    else:
        db_path = get_sqlite_path()
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON;")
        try:
            yield conn
        finally:
            await conn.close()


async def init_db():
    """
    Initializes tables and indexes for PostgreSQL or SQLite.
    """
    if get_db_type() == "postgres":
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parent_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(parent_id) REFERENCES folders(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    size_bytes BIGINT NOT NULL,
                    mime_type TEXT NOT NULL,
                    folder_id TEXT,
                    chunk_message_ids_json TEXT NOT NULL,
                    is_trashed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(folder_id) REFERENCES folders(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_id, is_trashed);
                CREATE INDEX IF NOT EXISTS idx_files_trashed ON files(is_trashed);
                CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);
            """)
        logger.info("Initialized PostgreSQL database tables and indexes.")
    else:
        db_path = get_sqlite_path()
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    parent_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(parent_id) REFERENCES folders(id) ON DELETE CASCADE
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    size_bytes BIGINT NOT NULL,
                    mime_type TEXT NOT NULL,
                    folder_id TEXT,
                    chunk_message_ids_json TEXT NOT NULL,
                    is_trashed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(folder_id) REFERENCES folders(id) ON DELETE SET NULL
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_folder ON files(folder_id, is_trashed);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_files_trashed ON files(is_trashed);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);")
            await conn.commit()
        logger.info(f"Initialized SQLite database at '{db_path}'.")


# ==========================================
# SETTINGS FUNCTIONS
# ==========================================

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    row = await fetch_one("SELECT value FROM settings WHERE key = ?", (key,))
    if row:
        return row["value"]
    return default


async def set_setting(key: str, value: str):
    await execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value",
        (key, value)
    )


# ==========================================
# FOLDER FUNCTIONS
# ==========================================

async def create_folder(name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
    folder_id = str(uuid.uuid4())
    now = get_iso_now()
    if parent_id in ("", "null", "root", None):
        parent_id = None

    await execute(
        "INSERT INTO folders (id, name, parent_id, created_at) VALUES (?, ?, ?, ?)",
        (folder_id, name.strip(), parent_id, now)
    )

    return {
        "id": folder_id,
        "name": name.strip(),
        "parent_id": parent_id,
        "created_at": now
    }


async def get_folder(folder_id: str) -> Optional[Dict[str, Any]]:
    return await fetch_one("SELECT * FROM folders WHERE id = ?", (folder_id,))


async def list_folders(parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query_parent = None if parent_id in ("", "null", "root", None) else parent_id
    if query_parent is None:
        query = """
            SELECT f.*, 
                   (SELECT COUNT(*) FROM files fi WHERE fi.folder_id = f.id AND fi.is_trashed = 0) as file_count,
                   (SELECT COUNT(*) FROM folders fo WHERE fo.parent_id = f.id) as subfolder_count
            FROM folders f 
            WHERE f.parent_id IS NULL 
            ORDER BY LOWER(f.name) ASC
        """
        params = ()
    else:
        query = """
            SELECT f.*, 
                   (SELECT COUNT(*) FROM files fi WHERE fi.folder_id = f.id AND fi.is_trashed = 0) as file_count,
                   (SELECT COUNT(*) FROM folders fo WHERE fo.parent_id = f.id) as subfolder_count
            FROM folders f 
            WHERE f.parent_id = ? 
            ORDER BY LOWER(f.name) ASC
        """
        params = (query_parent,)

    return await fetch_all(query, params)


async def get_all_folders() -> List[Dict[str, Any]]:
    return await fetch_all("SELECT id, name, parent_id, created_at FROM folders ORDER BY LOWER(name) ASC")


async def get_folder_breadcrumbs(folder_id: Optional[str]) -> List[Dict[str, Any]]:
    if not folder_id or folder_id in ("", "null", "root"):
        return [{"id": None, "name": "My Drive"}]

    breadcrumbs = []
    current_id = folder_id

    while current_id:
        row = await fetch_one("SELECT id, name, parent_id FROM folders WHERE id = ?", (current_id,))
        if not row:
            break
        breadcrumbs.append({"id": row["id"], "name": row["name"]})
        current_id = row["parent_id"]

    breadcrumbs.reverse()
    return [{"id": None, "name": "My Drive"}] + breadcrumbs


async def rename_folder(folder_id: str, new_name: str) -> Optional[Dict[str, Any]]:
    await execute("UPDATE folders SET name = ? WHERE id = ?", (new_name.strip(), folder_id))
    return await get_folder(folder_id)


async def move_folder(folder_id: str, new_parent_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if new_parent_id in ("", "null", "root", None):
        new_parent_id = None
    if folder_id == new_parent_id:
        return None  # Cannot move inside itself

    await execute("UPDATE folders SET parent_id = ? WHERE id = ?", (new_parent_id, folder_id))
    return await get_folder(folder_id)


async def delete_folder_recursive(folder_id: str) -> Dict[str, Any]:
    """
    Permanently delete folder, moving contained files to trash.
    """
    await execute("UPDATE files SET is_trashed = 1 WHERE folder_id = ?", (folder_id,))
    await execute("DELETE FROM folders WHERE id = ?", (folder_id,))
    return {"deleted": folder_id}


# ==========================================
# FILE FUNCTIONS
# ==========================================

async def create_file(
    filename: str,
    size_bytes: int,
    mime_type: str,
    folder_id: Optional[str],
    chunk_message_ids: List[Any],
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    fid = file_id or str(uuid.uuid4())
    now = get_iso_now()
    if folder_id in ("", "null", "root", None):
        folder_id = None

    chunks_json = json.dumps(chunk_message_ids)

    await execute("""
        INSERT INTO files (
            id, filename, size_bytes, mime_type, folder_id, 
            chunk_message_ids_json, is_trashed, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
    """, (fid, filename, size_bytes, mime_type, folder_id, chunks_json, now, now))

    return {
        "id": fid,
        "filename": filename,
        "size_bytes": size_bytes,
        "mime_type": mime_type,
        "folder_id": folder_id,
        "chunk_message_ids": chunk_message_ids,
        "is_trashed": 0,
        "created_at": now,
        "updated_at": now
    }


async def get_file(file_id: str) -> Optional[Dict[str, Any]]:
    row = await fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if not row:
        return None
    res = dict(row)
    try:
        res["chunk_message_ids"] = json.loads(res["chunk_message_ids_json"])
    except Exception:
        res["chunk_message_ids"] = []
    return res


async def list_files(
    folder_id: Optional[str] = None,
    category: Optional[str] = "all",
    search: Optional[str] = None,
    is_trashed: int = 0
) -> List[Dict[str, Any]]:
    conditions = []
    params = []

    if is_trashed == 1 or category == "trash":
        conditions.append("is_trashed = 1")
    else:
        conditions.append("is_trashed = 0")

        if search:
            conditions.append("LOWER(filename) LIKE LOWER(?)")
            params.append(f"%{search.strip()}%")
        elif category == "recent":
            pass
        elif category == "media":
            conditions.append("(mime_type LIKE 'image/%' OR mime_type LIKE 'video/%' OR mime_type LIKE 'audio/%')")
        elif category == "audio":
            conditions.append("(mime_type LIKE 'audio/%' OR filename LIKE '%.mp3' OR filename LIKE '%.wav' OR filename LIKE '%.flac' OR filename LIKE '%.ogg' OR filename LIKE '%.m4a')")
        else:
            if folder_id in ("", "null", "root", None):
                conditions.append("folder_id IS NULL")
            else:
                conditions.append("folder_id = ?")
                params.append(folder_id)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    order_clause = " ORDER BY created_at DESC"

    query = f"SELECT * FROM files{where_clause}{order_clause}"
    if category == "recent" and not search:
        query += " LIMIT 50"

    rows = await fetch_all(query, tuple(params))
    results = []
    for r in rows:
        item = dict(r)
        try:
            item["chunk_message_ids"] = json.loads(item["chunk_message_ids_json"])
        except Exception:
            item["chunk_message_ids"] = []
        results.append(item)
    return results


async def rename_file(file_id: str, new_name: str) -> Optional[Dict[str, Any]]:
    now = get_iso_now()
    await execute("UPDATE files SET filename = ?, updated_at = ? WHERE id = ?", (new_name.strip(), now, file_id))
    return await get_file(file_id)


async def move_file(file_id: str, new_folder_id: Optional[str]) -> Optional[Dict[str, Any]]:
    now = get_iso_now()
    if new_folder_id in ("", "null", "root", None):
        new_folder_id = None
    await execute("UPDATE files SET folder_id = ?, updated_at = ? WHERE id = ?", (new_folder_id, now, file_id))
    return await get_file(file_id)


async def move_file_to_trash(file_id: str) -> Optional[Dict[str, Any]]:
    now = get_iso_now()
    await execute("UPDATE files SET is_trashed = 1, updated_at = ? WHERE id = ?", (now, file_id))
    return await get_file(file_id)


async def restore_file_from_trash(file_id: str) -> Optional[Dict[str, Any]]:
    now = get_iso_now()
    await execute("UPDATE files SET is_trashed = 0, updated_at = ? WHERE id = ?", (now, file_id))
    return await get_file(file_id)


async def delete_file_permanently(file_id: str) -> Optional[Dict[str, Any]]:
    file_record = await get_file(file_id)
    if not file_record:
        return None
    await execute("DELETE FROM files WHERE id = ?", (file_id,))
    return file_record


async def get_all_trashed_files() -> List[Dict[str, Any]]:
    rows = await fetch_all("SELECT * FROM files WHERE is_trashed = 1")
    results = []
    for r in rows:
        item = dict(r)
        try:
            item["chunk_message_ids"] = json.loads(item["chunk_message_ids_json"])
        except Exception:
            item["chunk_message_ids"] = []
        results.append(item)
    return results


async def empty_trash_db() -> List[Dict[str, Any]]:
    trashed = await get_all_trashed_files()
    await execute("DELETE FROM files WHERE is_trashed = 1")
    return trashed


async def get_storage_stats() -> Dict[str, Any]:
    # Active files
    active_row = await fetch_one("""
        SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as total_size 
        FROM files WHERE is_trashed = 0
    """)
    active_count = int(active_row["count"]) if active_row and active_row.get("count") is not None else 0
    active_size = int(active_row["total_size"]) if active_row and active_row.get("total_size") is not None else 0

    # Trashed files
    trash_row = await fetch_one("""
        SELECT COUNT(*) as count, COALESCE(SUM(size_bytes), 0) as total_size 
        FROM files WHERE is_trashed = 1
    """)
    trash_count = int(trash_row["count"]) if trash_row and trash_row.get("count") is not None else 0
    trash_size = int(trash_row["total_size"]) if trash_row and trash_row.get("total_size") is not None else 0

    # Folders count
    folders_row = await fetch_one("SELECT COUNT(*) as count FROM folders")
    folder_count = int(folders_row["count"]) if folders_row and folders_row.get("count") is not None else 0

    # Chunks count
    rows = await fetch_all("SELECT chunk_message_ids_json FROM files")
    total_chunks = 0
    for r in rows:
        try:
            chunks = json.loads(r["chunk_message_ids_json"])
            total_chunks += len(chunks)
        except Exception:
            pass

    return {
        "active_bytes": active_size,
        "active_count": active_count,
        "trash_bytes": trash_size,
        "trash_count": trash_count,
        "folder_count": folder_count,
        "total_chunks": total_chunks
    }
