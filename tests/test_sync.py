import os
import sys
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Item, utc_now_iso
from app.storage import Storage
from app.server import app, SERVER_DB_PATH
from app.sync_engine import SyncEngine

class TestCrossSync(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.client_db_path1 = Path(self.temp_dir.name) / "client1.db"
        self.client_db_path2 = Path(self.temp_dir.name) / "client2.db"
        self.server_db_path = Path(self.temp_dir.name) / "server.db"

        # Initialize storages
        self.storage1 = Storage(self.client_db_path1)
        self.storage2 = Storage(self.client_db_path2)

        # Set server db path to temp
        import app.server as server_mod
        server_mod.SERVER_DB_PATH = self.server_db_path
        server_mod.init_server_db()
        self.test_client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_local_storage_crud(self):
        item = Item(
            item_type="note",
            title="Meeting Notes",
            content="# Discussion\n- Point 1\n- Point 2",
            tags="work, project-x"
        )
        self.storage1.save_item(item, mark_dirty=True)

        fetched = self.storage1.get_item(item.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Meeting Notes")
        self.assertTrue(fetched.is_dirty)

        # Check tags
        tags = self.storage1.get_all_tags()
        self.assertIn("work", tags)
        self.assertIn("project-x", tags)

        # Soft delete
        self.storage1.soft_delete_item(item.id)
        active_items = self.storage1.get_items(include_deleted=False)
        self.assertEqual(len(active_items), 0)

        deleted_items = self.storage1.get_items(include_deleted=True)
        self.assertEqual(len(deleted_items), 1)
        self.assertTrue(deleted_items[0].is_deleted)

    def test_server_auth(self):
        # Health check is public
        res = self.test_client.get("/api/health")
        self.assertEqual(res.status_code, 200)

        # Verify auth without token -> 401
        res = self.test_client.post("/api/auth/verify")
        self.assertEqual(res.status_code, 401)

        # Verify auth with wrong token -> 403
        res = self.test_client.post("/api/auth/verify", headers={"Authorization": "Bearer bad-token"})
        self.assertEqual(res.status_code, 403)

        # Verify auth with valid token
        res = self.test_client.post("/api/auth/verify", headers={"Authorization": "Bearer cross-sync-secret-key"})
        self.assertEqual(res.status_code, 200)

    def test_sync_between_two_clients(self):
        """Simulate Client 1 (e.g. Linux) and Client 2 (e.g. Windows) syncing via Server."""
        # 1. Client 1 creates a note and a task
        note1 = Item(item_type="note", title="Cross-Platform Idea", content="Sync between Windows and Linux")
        task1 = Item(item_type="task", title="Deploy sync server", status="pending")
        self.storage1.save_item(note1, mark_dirty=True)
        self.storage1.save_item(task1, mark_dirty=True)

        # 2. Client 1 pushes to Server
        dirty1 = [it.to_dict() for it in self.storage1.get_dirty_items()]
        self.assertEqual(len(dirty1), 2)

        res1 = self.test_client.post(
            "/api/sync",
            headers={"Authorization": "Bearer cross-sync-secret-key"},
            json={"client_id": "linux-laptop", "last_sync_timestamp": None, "items": dirty1}
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        self.assertEqual(data1["pushed_count"], 2)
        server_time_1 = data1["server_time"]

        # Client 1 marks clean
        self.storage1.mark_clean([note1.id, task1.id])
        self.assertEqual(len(self.storage1.get_dirty_items()), 0)

        # 3. Client 2 (Windows PC) syncs for the first time
        res2 = self.test_client.post(
            "/api/sync",
            headers={"Authorization": "Bearer cross-sync-secret-key"},
            json={"client_id": "windows-desktop", "last_sync_timestamp": None, "items": []}
        )
        self.assertEqual(res2.status_code, 200)
        data2 = res2.json()
        self.assertEqual(len(data2["updated_items"]), 2)

        # Client 2 applies updates
        for item_data in data2["updated_items"]:
            self.storage2.apply_remote_item(Item.from_dict(item_data))
        self.storage2.set_meta("last_sync_timestamp", data2["server_time"])

        # Verify Client 2 now has the note and the task!
        c2_items = self.storage2.get_items()
        self.assertEqual(len(c2_items), 2)
        c2_task = next(i for i in c2_items if i.id == task1.id)
        self.assertEqual(c2_task.status, "pending")

        # 4. Client 2 completes the task offline
        c2_task.status = "completed"
        self.storage2.save_item(c2_task, mark_dirty=True)

        # Client 2 syncs change back
        dirty2 = [it.to_dict() for it in self.storage2.get_dirty_items()]
        res3 = self.test_client.post(
            "/api/sync",
            headers={"Authorization": "Bearer cross-sync-secret-key"},
            json={"client_id": "windows-desktop", "last_sync_timestamp": data2["server_time"], "items": dirty2}
        )
        self.assertEqual(res3.status_code, 200)
        self.storage2.mark_clean([c2_task.id])

        # 5. Client 1 syncs and receives the updated task status
        res4 = self.test_client.post(
            "/api/sync",
            headers={"Authorization": "Bearer cross-sync-secret-key"},
            json={"client_id": "linux-laptop", "last_sync_timestamp": server_time_1, "items": []}
        )
        self.assertEqual(res4.status_code, 200)
        data4 = res4.json()
        self.assertEqual(len(data4["updated_items"]), 1)
        self.storage1.apply_remote_item(Item.from_dict(data4["updated_items"][0]))

        # Verify Client 1 now has completed status
        c1_task = self.storage1.get_item(task1.id)
        self.assertEqual(c1_task.status, "completed")
        print("\n✓ Full 2-way sync across 2 simulated machines passed successfully!")

if __name__ == "__main__":
    unittest.main()
