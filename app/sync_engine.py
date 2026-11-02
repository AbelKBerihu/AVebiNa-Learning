import sys
from typing import Optional, Callable, Dict, Any, Tuple
import httpx
from app.storage import Storage
from app.models import Item

class SyncEngine:
    def __init__(
        self,
        storage: Storage,
        server_url: str,
        sync_token: str,
        client_id: str = "desktop-client",
        on_status_change: Optional[Callable[[str, str], None]] = None
    ):
        self.storage = storage
        self.server_url = server_url.rstrip("/")
        self.sync_token = sync_token
        self.client_id = client_id
        self.on_status_change = on_status_change

    def update_config(self, server_url: str, sync_token: str) -> None:
        self.server_url = server_url.rstrip("/")
        self.sync_token = sync_token

    def _notify(self, status: str, message: str) -> None:
        if self.on_status_change:
            self.on_status_change(status, message)

    def test_connection(self) -> Tuple[bool, str]:
        """Tests server connectivity and authentication."""
        try:
            url = f"{self.server_url}/api/auth/verify"
            headers = {"Authorization": f"Bearer {self.sync_token}"}
            with httpx.Client(timeout=4.0) as client:
                res = client.post(url, headers=headers)
                if res.status_code == 200:
                    return True, "Connected successfully"
                elif res.status_code in (401, 403):
                    return False, "Authentication failed: invalid sync token"
                else:
                    return False, f"Server returned error: HTTP {res.status_code}"
        except httpx.ConnectError:
            return False, "Could not connect to server (connection refused or offline)"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"

    def perform_sync(self) -> Tuple[bool, str]:
        """
        Executes a two-way delta sync between local storage and sync server.
        Returns (success: bool, status_message: str).
        """
        self._notify("syncing", "Syncing with server...")
        try:
            dirty_items = self.storage.get_dirty_items()
            dirty_payload = [item.to_dict() for item in dirty_items]
            last_sync_time = self.storage.get_meta("last_sync_timestamp")

            payload = {
                "client_id": self.client_id,
                "last_sync_timestamp": last_sync_time,
                "items": dirty_payload
            }
            headers = {
                "Authorization": f"Bearer {self.sync_token}",
                "Content-Type": "application/json"
            }

            url = f"{self.server_url}/api/sync"
            with httpx.Client(timeout=8.0) as client:
                response = client.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                data = response.json()
                server_time = data.get("server_time")
                pushed_count = data.get("pushed_count", 0)
                updated_items_data = data.get("updated_items", [])

                # Step 1: Mark dirty items that were pushed as clean
                if dirty_items:
                    self.storage.mark_clean([item.id for item in dirty_items])

                # Step 2: Apply incoming updates from server
                pulled_count = 0
                for item_dict in updated_items_data:
                    remote_item = Item.from_dict(item_dict)
                    if self.storage.apply_remote_item(remote_item):
                        pulled_count += 1

                # Step 3: Record new sync timestamp
                if server_time:
                    self.storage.set_meta("last_sync_timestamp", server_time)

                msg = f"Synced: {pushed_count} pushed, {pulled_count} pulled"
                self._notify("synced", msg)
                return True, msg

            elif response.status_code in (401, 403):
                err = "Sync failed: Invalid token / authorization error"
                self._notify("error", err)
                return False, err
            else:
                err = f"Sync failed: Server error HTTP {response.status_code}"
                self._notify("error", err)
                return False, err

        except httpx.ConnectError:
            err = "Offline: Server unreachable"
            self._notify("offline", err)
            return False, err
        except httpx.TimeoutException:
            err = "Sync timed out"
            self._notify("offline", err)
            return False, err
        except Exception as e:
            err = f"Sync error: {str(e)}"
            self._notify("error", err)
            return False, err
