import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.models import Item, utc_now_iso

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS items (
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
    is_deleted INTEGER DEFAULT 0,
    is_dirty INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_items_type ON items (item_type);
CREATE INDEX IF NOT EXISTS idx_items_updated ON items (updated_at);
CREATE INDEX IF NOT EXISTS idx_items_dirty ON items (is_dirty);
CREATE INDEX IF NOT EXISTS idx_items_deleted ON items (is_deleted);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

class Storage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.executescript(SCHEMA_SQL)
            finally:
                conn.close()

    def save_item(self, item: Item, mark_dirty: bool = True) -> Item:
        """Insert or update a local item. By default marks as dirty."""
        if mark_dirty:
            item.mark_updated()
        
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO items (
                            id, item_type, title, content, status, tags, 
                            is_pinned, color, created_at, updated_at, is_deleted, is_dirty
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            item_type=excluded.item_type,
                            title=excluded.title,
                            content=excluded.content,
                            status=excluded.status,
                            tags=excluded.tags,
                            is_pinned=excluded.is_pinned,
                            color=excluded.color,
                            created_at=excluded.created_at,
                            updated_at=excluded.updated_at,
                            is_deleted=excluded.is_deleted,
                            is_dirty=excluded.is_dirty
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
                            1 if item.is_deleted else 0,
                            1 if item.is_dirty else 0
                        )
                    )
            finally:
                conn.close()
        return item

    def get_item(self, item_id: str) -> Optional[Item]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_item(row)
            finally:
                conn.close()
        return None

    def get_items(
        self,
        item_type: Optional[str] = None,
        include_deleted: bool = False,
        tag: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Item]:
        clauses = []
        params = []

        if not include_deleted:
            clauses.append("is_deleted = 0")
        if item_type and item_type != "all":
            clauses.append("item_type = ?")
            params.append(item_type)
        if search:
            clauses.append("(title LIKE ? OR content LIKE ? OR tags LIKE ?)")
            wildcard = f"%{search}%"
            params.extend([wildcard, wildcard, wildcard])

        query = "SELECT * FROM items"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        
        # Order by pinned first, then newest updated
        query += " ORDER BY is_pinned DESC, updated_at DESC"

        items = []
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(query, params)
                for row in cursor.fetchall():
                    item = self._row_to_item(row)
                    if tag:
                        if tag.lower() in [t.lower() for t in item.tag_list()]:
                            items.append(item)
                    else:
                        items.append(item)
            finally:
                conn.close()
        return items

    def soft_delete_item(self, item_id: str) -> bool:
        item = self.get_item(item_id)
        if not item:
            return False
        item.is_deleted = True
        item.mark_updated()
        self.save_item(item, mark_dirty=True)
        return True

    def restore_item(self, item_id: str) -> bool:
        item = self.get_item(item_id)
        if not item:
            return False
        item.is_deleted = False
        item.mark_updated()
        self.save_item(item, mark_dirty=True)
        return True

    def hard_delete_item(self, item_id: str) -> bool:
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            finally:
                conn.close()
        return True

    def get_all_tags(self) -> List[str]:
        items = self.get_items(include_deleted=False)
        tag_set = set()
        for item in items:
            for tag in item.tag_list():
                tag_set.add(tag)
        return sorted(list(tag_set))

    def get_dirty_items(self) -> List[Item]:
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute("SELECT * FROM items WHERE is_dirty = 1")
                return [self._row_to_item(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def mark_clean(self, item_ids: List[str]) -> None:
        if not item_ids:
            return
        placeholders = ",".join("?" for _ in item_ids)
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        f"UPDATE items SET is_dirty = 0 WHERE id IN ({placeholders})",
                        item_ids
                    )
            finally:
                conn.close()

    def apply_remote_item(self, remote_item: Item) -> bool:
        """
        Applies an incoming remote item using Last-Write-Wins.
        Returns True if item was updated locally, False if skipped.
        """
        local = self.get_item(remote_item.id)
        if local is None:
            # New item from server
            remote_item.is_dirty = False
            self._save_raw(remote_item)
            return True

        # If remote is newer or equal
        if remote_item.updated_at >= local.updated_at:
            remote_item.is_dirty = False
            self._save_raw(remote_item)
            return True
        elif not local.is_dirty:
            # If local wasn't dirty, accept remote anyway
            remote_item.is_dirty = False
            self._save_raw(remote_item)
            return True
        else:
            # Local item is dirty and newer; keep local so it pushes to server
            return False

    def _save_raw(self, item: Item) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO items (
                            id, item_type, title, content, status, tags, 
                            is_pinned, color, created_at, updated_at, is_deleted, is_dirty
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            item_type=excluded.item_type,
                            title=excluded.title,
                            content=excluded.content,
                            status=excluded.status,
                            tags=excluded.tags,
                            is_pinned=excluded.is_pinned,
                            color=excluded.color,
                            created_at=excluded.created_at,
                            updated_at=excluded.updated_at,
                            is_deleted=excluded.is_deleted,
                            is_dirty=excluded.is_dirty
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
                            1 if item.is_deleted else 0,
                            item.is_dirty
                        )
                    )
            finally:
                conn.close()

    def get_meta(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            conn = self._get_connection()
            try:
                cur = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,))
                row = cur.fetchone()
                return row["value"] if row else default
            finally:
                conn.close()

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO metadata (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, value)
                    )
            finally:
                conn.close()

    def _row_to_item(self, row: sqlite3.Row) -> Item:
        return Item(
            id=row["id"],
            item_type=row["item_type"],
            title=row["title"] or "",
            content=row["content"] or "",
            status=row["status"] or "pending",
            tags=row["tags"] or "",
            is_pinned=bool(row["is_pinned"]),
            color=row["color"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_deleted=bool(row["is_deleted"]),
            is_dirty=bool(row["is_dirty"])
        )
