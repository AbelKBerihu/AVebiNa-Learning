import os
import sys
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Server-side Database
SERVER_DB_PATH = Path(os.environ.get("SYNC_SERVER_DB", "server_notes.db"))

def get_db():
    conn = sqlite3.connect(str(SERVER_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_server_db():
    conn = get_db()
    try:
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS server_items (
                id TEXT PRIMARY KEY,
                item_type TEXT NOT NULL,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                tags TEXT DEFAULT '',
                is_pinned INTEGER DEFAULT 0,
                color TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_deleted INTEGER DEFAULT 0
            );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_server_updated ON server_items (updated_at);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_server_type ON server_items (item_type);")
    finally:
        conn.close()

init_server_db()

app = FastAPI(title="CrossSync Notes Server", version="1.0.0")

SERVER_TOKEN = os.environ.get("SYNC_TOKEN", "cross-sync-secret-key")

def verify_token(authorization: Optional[str] = Header(None)):
    if not SERVER_TOKEN:
        return True
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    prefix = "Bearer "
    token = authorization[len(prefix):] if authorization.startswith(prefix) else authorization
    if token != SERVER_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid sync token")
    return True

# Pydantic Schemas
class SyncItemPayload(BaseModel):
    id: str
    item_type: str = "note"
    title: str = ""
    content: str = ""
    status: str = "pending"
    tags: str = ""
    is_pinned: bool = False
    color: str = ""
    created_at: str
    updated_at: str
    is_deleted: bool = False

class SyncRequest(BaseModel):
    client_id: str = "unknown"
    last_sync_timestamp: Optional[str] = None
    items: List[SyncItemPayload] = Field(default_factory=list)

class SyncResponse(BaseModel):
    success: bool
    server_time: str
    pushed_count: int
    updated_items: List[Dict[str, Any]]

@app.get("/", response_class=HTMLResponse)
def index_view():
    conn = get_db()
    try:
        cur = conn.execute("SELECT count(*) as total, sum(CASE WHEN is_deleted=0 THEN 1 ELSE 0 END) as active FROM server_items")
        row = cur.fetchone()
        total = row["total"] or 0
        active = row["active"] or 0
    finally:
        conn.close()

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>CrossSync Notes Server</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }}
            .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 32px; max-width: 600px; width: 100%; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); }}
            h1 {{ color: #38bdf8; margin-top: 0; font-size: 26px; }}
            .status-badge {{ display: inline-block; padding: 6px 14px; border-radius: 9999px; background: #10b981; color: #022c22; font-weight: bold; font-size: 13px; margin-bottom: 20px; }}
            .metric {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #334155; }}
            .label {{ color: #94a3b8; }}
            .val {{ font-weight: 600; color: #f1f5f9; }}
            .code-box {{ background: #090d16; border-radius: 8px; padding: 12px; font-family: monospace; color: #38bdf8; font-size: 13px; margin-top: 15px; word-break: break-all; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="status-badge">● Server Online</span>
            <h1>CrossSync Notes & Tasks Server</h1>
            <p style="color: #94a3b8; line-height: 1.5;">This server synchronizes your notes and to-dos seamlessly across Windows and Linux devices in real-time.</p>
            
            <div class="metric">
                <span class="label">Server Status</span>
                <span class="val" style="color: #34d399;">Ready & Accepting Sync</span>
            </div>
            <div class="metric">
                <span class="label">Active Synchronized Items</span>
                <span class="val">{active}</span>
            </div>
            <div class="metric">
                <span class="label">Total Records (inc. tombstoned)</span>
                <span class="val">{total}</span>
            </div>
            <div class="metric">
                <span class="label">Server Time (UTC)</span>
                <span class="val">{utc_now_iso()}</span>
            </div>

            <p style="color: #94a3b8; margin-top: 24px; font-size: 14px;">Connect your desktop client using this server's IP/Host and your configured token.</p>
            <div class="code-box">API Endpoint: /api/sync</div>
        </div>
    </body>
    </html>
    """

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "cross-sync-notes",
        "version": "1.0.0",
        "server_time": utc_now_iso()
    }

@app.post("/api/auth/verify")
def auth_verify(_: bool = Depends(verify_token)):
    return {"status": "authenticated", "server_time": utc_now_iso()}

@app.post("/api/sync", response_model=SyncResponse)
def sync_data(req: SyncRequest, _: bool = Depends(verify_token)):
    server_time = utc_now_iso()
    pushed_count = 0
    pushed_ids = set()

    conn = get_db()
    try:
        with conn:
            # Step 1: Push client items into server
            for item in req.items:
                cur = conn.execute("SELECT updated_at FROM server_items WHERE id = ?", (item.id,))
                row = cur.fetchone()
                if row is None:
                    # Insert brand new item
                    conn.execute(
                        """
                        INSERT INTO server_items (
                            id, item_type, title, content, status, tags,
                            is_pinned, color, created_at, updated_at, is_deleted
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.id,
                            item.item_type,
                            item.title,
                            item.content,
                            item.status,
                            item.tags,
                            1 if item.is_pinned else 0,
                            item.color,
                            item.created_at,
                            item.updated_at,
                            1 if item.is_deleted else 0
                        )
                    )
                    pushed_count += 1
                    pushed_ids.add(item.id)
                else:
                    # Existing item: Last-Write-Wins comparison
                    existing_updated = row["updated_at"]
                    if item.updated_at >= existing_updated:
                        conn.execute(
                            """
                            UPDATE server_items SET
                                item_type = ?,
                                title = ?,
                                content = ?,
                                status = ?,
                                tags = ?,
                                is_pinned = ?,
                                color = ?,
                                created_at = ?,
                                updated_at = ?,
                                is_deleted = ?
                            WHERE id = ?
                            """,
                            (
                                item.item_type,
                                item.title,
                                item.content,
                                item.status,
                                item.tags,
                                1 if item.is_pinned else 0,
                                item.color,
                                item.created_at,
                                item.updated_at,
                                1 if item.is_deleted else 0,
                                item.id
                            )
                        )
                        pushed_count += 1
                        pushed_ids.add(item.id)

            # Step 2: Pull updates for client
            # Fetch items changed since req.last_sync_timestamp
            if req.last_sync_timestamp:
                cur = conn.execute(
                    "SELECT * FROM server_items WHERE updated_at > ?",
                    (req.last_sync_timestamp,)
                )
            else:
                # First full sync: pull all server items
                cur = conn.execute("SELECT * FROM server_items")

            server_rows = cur.fetchall()
            updated_items = []
            for r in server_rows:
                # If item was just pushed by the client and has identical updated_at, client already has it
                if r["id"] in pushed_ids:
                    continue
                updated_items.append({
                    "id": r["id"],
                    "item_type": r["item_type"],
                    "title": r["title"] or "",
                    "content": r["content"] or "",
                    "status": r["status"] or "pending",
                    "tags": r["tags"] or "",
                    "is_pinned": bool(r["is_pinned"]),
                    "color": r["color"] or "",
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "is_deleted": bool(r["is_deleted"]),
                })
    finally:
        conn.close()

    return SyncResponse(
        success=True,
        server_time=server_time,
        pushed_count=pushed_count,
        updated_items=updated_items
    )
