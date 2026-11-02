import argparse
import sys
from app.config import get_db_path, load_settings
from app.storage import Storage
from app.sync_engine import SyncEngine
from app.models import Item

def run_cli():
    parser = argparse.ArgumentParser(description="CrossSync Notes & Tasks CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List command
    list_p = subparsers.add_parser("list", help="List notes and tasks")
    list_p.add_argument("--type", choices=["note", "task", "all"], default="all", help="Filter by item type")
    list_p.add_argument("--tag", help="Filter by tag")
    list_p.add_argument("--search", help="Search query")
    list_p.add_argument("--all", action="store_true", help="Include deleted items")

    # Add Note command
    add_n = subparsers.add_parser("add-note", help="Add a new note")
    add_n.add_argument("title", help="Note title")
    add_n.add_argument("content", nargs="?", default="", help="Note content (markdown)")
    add_n.add_argument("--tags", default="", help="Comma separated tags")

    # Add Task command
    add_t = subparsers.add_parser("add-task", help="Add a new task")
    add_t.add_argument("title", help="Task title")
    add_t.add_argument("--tags", default="", help="Comma separated tags")

    # Toggle task
    tog = subparsers.add_parser("toggle", help="Toggle task status (pending/completed)")
    tog.add_argument("id", help="Item ID or prefix")

    # Delete command
    rm = subparsers.add_parser("delete", help="Soft-delete an item")
    rm.add_argument("id", help="Item ID or prefix")

    # Sync command
    subparsers.add_parser("sync", help="Trigger immediate sync with server")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    settings = load_settings()
    storage = Storage(get_db_path())
    sync_engine = SyncEngine(
        storage=storage,
        server_url=settings.get("server_url", "http://127.0.0.1:8765"),
        sync_token=settings.get("sync_token", "cross-sync-secret-key")
    )

    if args.command == "list":
        items = storage.get_items(
            item_type=args.type if args.type != "all" else None,
            include_deleted=args.all,
            tag=args.tag,
            search=args.search
        )
        if not items:
            print("No items found.")
            return

        print(f"{'STATUS':<6} {'TYPE':<6} {'ID':<10} {'TITLE':<30} {'TAGS'}")
        print("-" * 65)
        for it in items:
            stat = "✓" if it.status == "completed" else ("○" if it.item_type == "task" else " ")
            short_id = it.id[:8]
            print(f"{stat:<6} {it.item_type:<6} {short_id:<10} {it.title[:28]:<30} {it.tags}")

    elif args.command == "add-note":
        item = Item(
            item_type="note",
            title=args.title,
            content=args.content,
            tags=args.tags
        )
        storage.save_item(item, mark_dirty=True)
        print(f"Created note: '{item.title}' (ID: {item.id[:8]})")
        # Auto-sync
        sync_engine.perform_sync()

    elif args.command == "add-task":
        item = Item(
            item_type="task",
            title=args.title,
            status="pending",
            tags=args.tags
        )
        storage.save_item(item, mark_dirty=True)
        print(f"Created task: '{item.title}' (ID: {item.id[:8]})")
        sync_engine.perform_sync()

    elif args.command == "toggle":
        # Find item by prefix
        items = storage.get_items(include_deleted=True)
        target = next((i for i in items if i.id.startswith(args.id)), None)
        if not target:
            print(f"Item not found: {args.id}")
            return
        if target.item_type != "task":
            print(f"Item {args.id} is a note, not a task.")
            return
        target.status = "pending" if target.status == "completed" else "completed"
        storage.save_item(target, mark_dirty=True)
        print(f"Task '{target.title}' is now: {target.status}")
        sync_engine.perform_sync()

    elif args.command == "delete":
        items = storage.get_items(include_deleted=True)
        target = next((i for i in items if i.id.startswith(args.id)), None)
        if not target:
            print(f"Item not found: {args.id}")
            return
        storage.soft_delete_item(target.id)
        print(f"Deleted: '{target.title}' (ID: {target.id[:8]})")
        sync_engine.perform_sync()

    elif args.command == "sync":
        print(f"Connecting to {sync_engine.server_url}...")
        ok, msg = sync_engine.perform_sync()
        if ok:
            print(f"✓ Success: {msg}")
        else:
            print(f"✗ Failed: {msg}")

if __name__ == "__main__":
    run_cli()
