import os
import mimetypes
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, Union
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

import database
from discord_storage import DiscordStorageEngine, parse_webhook_urls

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app")

storage_engine = DiscordStorageEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database (PostgreSQL via asyncpg or SQLite fallback)
    await database.init_db()

    # Load multi-node webhook URLs: check .env or DB settings
    env_multi = os.getenv("STORAGE_WEBHOOK_URLS", "").strip()
    env_single = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    db_multi = await database.get_setting("STORAGE_WEBHOOK_URLS")
    db_single = await database.get_setting("DISCORD_WEBHOOK_URL")

    active_urls: List[str] = []
    if env_multi:
        active_urls = parse_webhook_urls(env_multi)
    elif db_multi:
        active_urls = parse_webhook_urls(db_multi)
    elif env_single:
        active_urls = parse_webhook_urls(env_single)
    elif db_single:
        active_urls = parse_webhook_urls(db_single)

    if active_urls:
        storage_engine.set_urls(active_urls)
        await database.set_setting("STORAGE_WEBHOOK_URLS", ",".join(active_urls))
        await database.set_setting("DISCORD_WEBHOOK_URL", active_urls[0])

    logger.info(f"Storage Cluster Configured: {storage_engine.is_configured} ({storage_engine.node_count} active storage nodes)")
    logger.info(f"Database Backend: {database.get_db_type()}")
    yield
    await database.close_db()


app = FastAPI(title="Personal Cloud Storage", lifespan=lifespan)

# Enable CORS for Capacitor Android APK and cross-origin clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Pydantic models for request bodies
class CreateFolderRequest(BaseModel):
    name: str
    parent_id: Optional[str] = None

class UpdateFolderRequest(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None

class UpdateFileRequest(BaseModel):
    filename: Optional[str] = None
    folder_id: Optional[str] = None

class UpdateSettingsRequest(BaseModel):
    storage_nodes: Optional[List[str]] = None
    storage_webhook_urls: Optional[str] = None
    discord_webhook_url: Optional[str] = None

class TestWebhookRequest(BaseModel):
    url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    test_all: Optional[bool] = False


# ==========================================
# SYSTEM / INFO ROUTES
# ==========================================

@app.get("/api/info")
async def get_system_info():
    stats = await database.get_storage_stats()
    nodes = [
        {"id": i, "name": f"Storage Node {i}", "active": True}
        for i in range(1, storage_engine.node_count + 1)
    ]
    return {
        "webhook_configured": storage_engine.is_configured,
        "node_count": storage_engine.node_count,
        "nodes": nodes,
        "webhook_url": storage_engine.get_primary_url(),
        "database_backend": database.get_db_type(),
        "stats": stats
    }


# ==========================================
# SETTINGS ROUTES
# ==========================================

@app.get("/api/settings")
async def get_settings():
    urls = storage_engine.get_urls()
    nodes = [
        {"id": i, "name": f"Storage Node {i}", "url": u}
        for i, u in enumerate(urls, 1)
    ]
    return {
        "storage_nodes": nodes,
        "storage_webhook_urls": ",".join(urls),
        "discord_webhook_url": storage_engine.get_primary_url(),
        "node_count": len(urls),
        "is_configured": storage_engine.is_configured
    }


@app.post("/api/settings")
async def update_settings(payload: UpdateSettingsRequest):
    candidate_urls: List[str] = []
    if payload.storage_nodes:
        candidate_urls = parse_webhook_urls(payload.storage_nodes)
    elif payload.storage_webhook_urls:
        candidate_urls = parse_webhook_urls(payload.storage_webhook_urls)
    elif payload.discord_webhook_url:
        candidate_urls = parse_webhook_urls(payload.discord_webhook_url)

    storage_engine.set_urls(candidate_urls)
    joined_urls = ",".join(candidate_urls)
    primary_url = candidate_urls[0] if candidate_urls else ""

    await database.set_setting("STORAGE_WEBHOOK_URLS", joined_urls)
    await database.set_setting("DISCORD_WEBHOOK_URL", primary_url)

    # Persist to .env file
    env_path = ".env"
    try:
        if os.path.exists(env_path):
            set_key(env_path, "STORAGE_WEBHOOK_URLS", joined_urls)
            if primary_url:
                set_key(env_path, "DISCORD_WEBHOOK_URL", primary_url)
    except Exception as e:
        logger.warning(f"Could not update .env file: {e}")

    nodes = [
        {"id": i, "name": f"Storage Node {i}", "url": u}
        for i, u in enumerate(candidate_urls, 1)
    ]

    return {
        "message": f"Storage cluster configured successfully with {len(candidate_urls)} active nodes.",
        "is_configured": storage_engine.is_configured,
        "node_count": len(candidate_urls),
        "storage_nodes": nodes,
        "storage_webhook_urls": joined_urls,
        "discord_webhook_url": primary_url
    }


@app.post("/api/settings/test")
async def test_webhook_route(payload: TestWebhookRequest):
    if payload.test_all:
        node_results = await storage_engine.test_all_nodes()
        total = len(node_results)
        passed = sum(1 for n in node_results if n["success"])
        return {
            "success": passed > 0 and (passed == total),
            "message": f"{passed}/{total} storage nodes operational",
            "nodes": node_results
        }

    url_to_test = payload.url or payload.discord_webhook_url or storage_engine.get_primary_url()
    success, message, metadata = await storage_engine.test_connection(url_to_test)
    return {
        "success": success,
        "message": message,
        "metadata": metadata
    }


# ==========================================
# FOLDER ROUTES
# ==========================================

@app.get("/api/folders")
async def get_folders(parent_id: Optional[str] = Query(None)):
    folders = await database.list_folders(parent_id)
    return {"folders": folders}


@app.get("/api/folders/tree")
async def get_folders_tree():
    folders = await database.get_all_folders()
    return {"folders": folders}


@app.get("/api/folders/{folder_id}/breadcrumbs")
async def get_breadcrumbs(folder_id: str):
    breadcrumbs = await database.get_folder_breadcrumbs(folder_id)
    return {"breadcrumbs": breadcrumbs}


@app.post("/api/folders")
async def create_new_folder(payload: CreateFolderRequest):
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Folder name is required")
    folder = await database.create_folder(payload.name, payload.parent_id)
    return folder


@app.patch("/api/folders/{folder_id}")
async def update_folder(folder_id: str, payload: UpdateFolderRequest):
    folder = await database.get_folder(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if payload.name is not None and payload.name.strip():
        folder = await database.rename_folder(folder_id, payload.name)

    if payload.parent_id is not None:
        folder = await database.move_folder(folder_id, payload.parent_id)

    return folder


@app.delete("/api/folders/{folder_id}")
async def delete_folder(folder_id: str):
    folder = await database.get_folder(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    result = await database.delete_folder_recursive(folder_id)
    return {"message": "Folder deleted successfully", "folder_id": folder_id}


# ==========================================
# FILE ROUTES
# ==========================================

@app.get("/api/files")
async def list_files_route(
    folder_id: Optional[str] = Query(None),
    category: Optional[str] = Query("all"),
    search: Optional[str] = Query(None)
):
    files = await database.list_files(
        folder_id=folder_id,
        category=category,
        search=search,
        is_trashed=1 if category == "trash" else 0
    )
    return {"files": files}


@app.post("/api/upload")
async def upload_file_route(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None)
):
    try:
        content = await file.read()
        filename = file.filename or "unnamed_file"
        size_bytes = len(content)

        mime_type = file.content_type
        if not mime_type or mime_type == "application/octet-stream":
            guessed_type, _ = mimetypes.guess_type(filename)
            mime_type = guessed_type or "application/octet-stream"

        # Upload sequentially in 19MB chunks through storage engine
        chunk_message_ids, actual_size = await storage_engine.upload_file_stream(
            filename=filename,
            file_bytes=content,
            mime_type=mime_type
        )

        # Store in database
        saved_file = await database.create_file(
            filename=filename,
            size_bytes=actual_size,
            mime_type=mime_type,
            folder_id=folder_id,
            chunk_message_ids=chunk_message_ids
        )

        return {
            "success": True,
            "file": saved_file,
            "chunks_count": len(chunk_message_ids),
            "node_count": storage_engine.node_count,
            "storage_backend": "discord" if storage_engine.is_configured else "fallback"
        }
    except Exception as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/files/{file_id}")
async def get_file_metadata(file_id: str):
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    return file_record


@app.patch("/api/files/{file_id}")
async def update_file(file_id: str, payload: UpdateFileRequest):
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    if payload.filename is not None and payload.filename.strip():
        file_record = await database.rename_file(file_id, payload.filename)

    if payload.folder_id is not None:
        file_record = await database.move_file(file_id, payload.folder_id)

    return file_record


@app.post("/api/files/{file_id}/trash")
async def move_to_trash(file_id: str):
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    updated = await database.move_file_to_trash(file_id)
    return {"message": "Moved to trash", "file": updated}


@app.post("/api/files/{file_id}/restore")
async def restore_file(file_id: str):
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    updated = await database.restore_file_from_trash(file_id)
    return {"message": "Restored file", "file": updated}


@app.delete("/api/files/{file_id}")
async def delete_file_permanently(file_id: str):
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    chunk_ids = file_record.get("chunk_message_ids", [])
    # Call Discord to delete the chunk messages permanently
    await storage_engine.delete_chunk_messages(chunk_ids)

    # Delete from database
    await database.delete_file_permanently(file_id)
    return {"message": "File permanently deleted", "file_id": file_id}


@app.delete("/api/trash/empty")
async def empty_trash_route():
    trashed_files = await database.get_all_trashed_files()
    total_chunks = []
    for f in trashed_files:
        total_chunks.extend(f.get("chunk_message_ids", []))

    # Delete all chunk messages from Discord
    if total_chunks:
        await storage_engine.delete_chunk_messages(total_chunks)

    # Empty from DB
    await database.empty_trash_db()
    return {"message": "Trash emptied successfully", "count": len(trashed_files)}


# ==========================================
# STREAMING, DOWNLOAD & SHARE LINK ROUTES
# ==========================================

def get_stream_headers(filename: str, mime_type: str, size_bytes: int, inline: bool = True) -> dict:
    disposition_type = "inline" if inline else "attachment"
    # Clean filename for header
    safe_filename = filename.replace('"', '\\"')
    return {
        "Content-Type": mime_type,
        "Content-Length": str(size_bytes),
        "Content-Disposition": f'{disposition_type}; filename="{safe_filename}"',
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600"
    }


@app.get("/api/files/{file_id}/stream")
async def stream_file(file_id: str):
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    chunk_ids = file_record.get("chunk_message_ids", [])
    if not chunk_ids:
        raise HTTPException(status_code=404, detail="File has no storage chunks")

    headers = get_stream_headers(
        filename=file_record["filename"],
        mime_type=file_record["mime_type"],
        size_bytes=file_record["size_bytes"],
        inline=True
    )

    return StreamingResponse(
        storage_engine.stream_file_chunks(chunk_ids),
        media_type=file_record["mime_type"],
        headers=headers
    )


@app.get("/api/files/{file_id}/download")
async def download_file(file_id: str):
    file_record = await database.get_file(file_id)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    chunk_ids = file_record.get("chunk_message_ids", [])
    if not chunk_ids:
        raise HTTPException(status_code=404, detail="File has no storage chunks")

    headers = get_stream_headers(
        filename=file_record["filename"],
        mime_type=file_record["mime_type"],
        size_bytes=file_record["size_bytes"],
        inline=False
    )

    return StreamingResponse(
        storage_engine.stream_file_chunks(chunk_ids),
        media_type=file_record["mime_type"],
        headers=headers
    )


@app.get("/api/share/{file_id}")
async def public_share_link(file_id: str, download: bool = False):
    """
    Direct public share endpoint for instant streaming or downloading.
    """
    file_record = await database.get_file(file_id)
    if not file_record or file_record.get("is_trashed"):
        raise HTTPException(status_code=404, detail="Shared file not found or has been moved to trash")

    chunk_ids = file_record.get("chunk_message_ids", [])
    if not chunk_ids:
        raise HTTPException(status_code=404, detail="File data unavailable")

    headers = get_stream_headers(
        filename=file_record["filename"],
        mime_type=file_record["mime_type"],
        size_bytes=file_record["size_bytes"],
        inline=not download
    )

    return StreamingResponse(
        storage_engine.stream_file_chunks(chunk_ids),
        media_type=file_record["mime_type"],
        headers=headers
    )


# ==========================================
# STATIC FILES & ROOT
# ==========================================

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def serve_index():
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Personal Cloud Storage API is running. Place static/index.html to view UI."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app:app", host=host, port=port, reload=False)
