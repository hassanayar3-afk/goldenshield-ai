"""Inspect and merge Cursor composer/chat keys between workspace state DBs."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

APPDATA = Path.home() / "AppData" / "Roaming" / "Cursor" / "User"
WS = APPDATA / "workspaceStorage"
GS = APPDATA / "globalStorage" / "state.vscdb"

# goldenshield parent (where long chats were)
SRC = WS / "3c251e5d08ab2c8bad79cbbee22868af" / "state.vscdb"
# GoldenShield_AI current
DST = WS / "0c2eed867f41dcf1d99c4c425e74ded6" / "state.vscdb"
EMPTY = WS / "empty-window" / "state.vscdb"

INTERESTING = (
    "composer",
    "chat",
    "aichat",
    "agent",
    "bubble",
    "history",
    "panel",
    "tab",
    "conversation",
    "anysphere",
)


def list_keys(db: Path) -> list[str]:
    if not db.is_file():
        print(f"MISSING {db}")
        return []
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    print(f"\n== {db} tables={tables}")
    keys: list[str] = []
    for t in tables:
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})")]
        if "key" in cols:
            keys = [r[0] for r in cur.execute(f"SELECT key FROM {t}")]
            print(f"  {t}: {len(keys)} keys")
            for k in keys:
                low = k.lower()
                if any(s in low for s in INTERESTING):
                    print(f"  KEY {k[:180]}")
    con.close()
    return keys


def dump_itemtable(db: Path) -> dict[str, bytes]:
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    data: dict[str, bytes] = {}
    for t in tables:
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})")]
        if cols[:2] == ["key", "value"] or ("key" in cols and "value" in cols):
            for k, v in cur.execute(f"SELECT key, value FROM {t}"):
                data[str(k)] = v
    con.close()
    return data


def merge_interesting(src: Path, dst: Path) -> int:
    if not src.is_file() or not dst.is_file():
        print("merge skip: missing db")
        return 0
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = dst.with_suffix(f".vscdb.bak_{stamp}")
    shutil.copy2(dst, backup)
    print(f"BACKUP {backup}")

    src_data = dump_itemtable(src)
    dst_data = dump_itemtable(dst)

    # also pull from empty-window if richer
    if EMPTY.is_file():
        empty_data = dump_itemtable(EMPTY)
        for k, v in empty_data.items():
            if k not in src_data or (isinstance(v, (bytes, str)) and len(v or b"") > len(src_data.get(k) or b"")):
                # only interesting keys from empty
                if any(s in k.lower() for s in INTERESTING):
                    src_data.setdefault(k, v)

    to_write: dict[str, bytes] = {}
    for k, v in src_data.items():
        low = k.lower()
        if not any(s in low for s in INTERESTING):
            continue
        if k not in dst_data:
            to_write[k] = v
        elif dst_data[k] != v and len(v or b"") >= len(dst_data[k] or b""):
            to_write[k] = v

    if not to_write:
        print("Nothing to merge")
        return 0

    con = sqlite3.connect(str(dst))
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    target = "ItemTable" if "ItemTable" in tables else tables[0]
    n = 0
    for k, v in to_write.items():
        cur.execute(f"INSERT OR REPLACE INTO {target} (key, value) VALUES (?, ?)", (k, v))
        n += 1
        print(f"MERGED {k[:160]}")
    con.commit()
    con.close()
    print(f"Merged {n} keys into {dst}")
    return n


def main() -> None:
    for p in (SRC, DST, EMPTY, GS):
        list_keys(p)
    print("\n--- MERGE parent -> GoldenShield_AI ---")
    merge_interesting(SRC, DST)
    print("DONE")


if __name__ == "__main__":
    main()
