#!/usr/bin/env python3
import sys
import os
import argparse
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description="CrossSync Central Sync Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--token", default="cross-sync-secret-key", help="Security token required for sync")
    parser.add_argument("--db", default="server_notes.db", help="Path to server SQLite database")
    args = parser.parse_args()

    os.environ["SYNC_TOKEN"] = args.token
    os.environ["SYNC_SERVER_DB"] = args.db

    print("=" * 60)
    print(" ✦ Starting CrossSync Notes Server")
    print(f" • Host: {args.host}:{args.port}")
    print(f" • Token: {args.token}")
    print(f" • Database: {args.db}")
    print(" • Web Status: http://localhost:8765")
    print("=" * 60)

    uvicorn.run("app.server:app", host=args.host, port=args.port, reload=False, log_level="info")

if __name__ == "__main__":
    main()
