"""نسخ composerHeaders + مفاتيح المحادثات من مجلد goldenshield إلى GoldenShield_AI."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

WS = Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "workspaceStorage"
SRC = WS / "3c251e5d08ab2c8bad79cbbee22868af" / "state.vscdb"  # goldenshield
DST = WS / "0c2eed867f41dcf1d99c4c425e74ded6" / "state.vscdb"  # GoldenShield_AI
GS = Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(f".vscdb.bak_{stamp}")
    shutil.copy2(path, bak)
    print("BACKUP", bak)
    return bak


def table_rows(con: sqlite3.Connection, table: str) -> list[tuple]:
    cur = con.cursor()
    names = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    if table not in names:
        return []
    cols = [c[1] for c in cur.execute(f"PRAGMA table_info({table})")]
    print(f"TABLE {table} cols={cols}")
    return list(cur.execute(f"SELECT * FROM {table}"))


def merge_composer_headers(src: Path, dst: Path) -> int:
    backup(dst)
    s = sqlite3.connect(str(src))
    d = sqlite3.connect(str(dst))
    s_rows = table_rows(s, "composerHeaders")
    d_rows = table_rows(d, "composerHeaders")
    print(f"SRC headers={len(s_rows)} DST headers={len(d_rows)}")

    # discover schema
    d_cur = d.cursor()
    cols = [c[1] for c in d_cur.execute("PRAGMA table_info(composerHeaders)")]
    if not cols:
        print("No composerHeaders on destination")
        s.close()
        d.close()
        return 0

    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    n = 0
    # assume first column is primary key / composer id
    existing = {r[0] for r in d_rows}
    for row in s_rows:
        key = row[0]
        if key in existing:
            d_cur.execute(
                f"UPDATE composerHeaders SET {', '.join(f'{c}=?' for c in cols[1:])} WHERE {cols[0]}=?",
                (*row[1:], key),
            )
        else:
            d_cur.execute(
                f"INSERT INTO composerHeaders ({col_list}) VALUES ({placeholders})",
                row,
            )
        n += 1
        print("HEADER", str(key)[:80])

    # also merge interesting ItemTable + cursorDiskKV keys from src
    for table in ("ItemTable", "cursorDiskKV"):
        names = [r[0] for r in d_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if table not in names:
            continue
        s_cur = s.cursor()
        if table not in [r[0] for r in s_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
            continue
        for k, v in s_cur.execute(f"SELECT key, value FROM {table}"):
            low = str(k).lower()
            if not any(x in low for x in ("composer", "aichat", "agent", "chat", "backgroundcomposer")):
                continue
            d_cur.execute(f"INSERT OR REPLACE INTO {table} (key, value) VALUES (?, ?)", (k, v))
            n += 1
            print("KV", table, str(k)[:100])

    d.commit()
    s.close()
    d.close()
    print("MERGED_ROWS", n)
    return n


def print_header_counts() -> None:
    for label, path in (("SRC", SRC), ("DST", DST), ("GLOBAL", GS)):
        if not path.is_file():
            print(label, "missing")
            continue
        con = sqlite3.connect(str(path))
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        count = 0
        if "composerHeaders" in names:
            count = con.execute("SELECT COUNT(*) FROM composerHeaders").fetchone()[0]
        print(label, path.name, "composerHeaders=", count, "tables=", names)
        con.close()


if __name__ == "__main__":
    print_header_counts()
    merge_composer_headers(SRC, DST)
    print("--- after ---")
    print_header_counts()
