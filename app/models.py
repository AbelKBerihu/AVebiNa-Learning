import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Dict, Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Item:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    item_type: str = "note"  # "note" or "task"
    title: str = ""
    content: str = ""
    status: str = "pending"  # For tasks: "pending" or "completed"; For notes: "active"
    tags: str = ""  # Comma-separated list of tags
    is_pinned: bool = False
    color: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    is_deleted: bool = False
    is_dirty: bool = True  # Used locally to track unpushed edits

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["is_pinned"] = bool(d["is_pinned"])
        d["is_deleted"] = bool(d["is_deleted"])
        d["is_dirty"] = bool(d["is_dirty"])
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        # Filter valid fields
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        if "is_pinned" in filtered:
            filtered["is_pinned"] = bool(filtered["is_pinned"])
        if "is_deleted" in filtered:
            filtered["is_deleted"] = bool(filtered["is_deleted"])
        if "is_dirty" in filtered:
            filtered["is_dirty"] = bool(filtered["is_dirty"])
        return cls(**filtered)

    def tag_list(self) -> List[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def mark_updated(self) -> None:
        self.updated_at = utc_now_iso()
        self.is_dirty = True
