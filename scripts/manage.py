"""Offline operator commands. No public API can upgrade its own plan."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from server.db import connect, initialize


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("login")
    plan.add_argument("plan", choices=("free", "pro"))
    backup = sub.add_parser("backup")
    backup.add_argument("destination")
    args = parser.parse_args()
    initialize()
    if args.command == "plan":
        with connect() as db:
            result = db.execute("UPDATE users SET pro=? WHERE login=?", (int(args.plan == "pro"), args.login))
            if result.rowcount != 1:
                parser.error("User not found; the user must log in first.")
        print(f"Updated {args.login}: {args.plan}")
    else:
        destination = Path(args.destination)
        if destination.exists():
            parser.error("Refusing to overwrite an existing backup.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with connect() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        print(f"Backup saved to {destination}")


if __name__ == "__main__":
    main()
