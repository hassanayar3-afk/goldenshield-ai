"""إعادة ربط محادثات Cursor (composerHeaders) بمسار GoldenShield_AI الحالي."""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

USER = Path.home() / "AppData" / "Roaming" / "Cursor" / "User"
GS = USER / "globalStorage" / "state.vscdb"
WS_ROOT = USER / "workspaceStorage"

# المسارات المستهدفة
TARGET_FOLDER_HINTS = (
    "goldenshield/GoldenShield_AI",
    "goldenshield%2FGoldenShield_AI",
    "Users/acer/goldenshield",
)


def backup(path: Path) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(f".vscdb.bak_{stamp}")
    shutil.copy2(path, bak)
    print("BACKUP", bak)


def workspace_map() -> dict[str, str]:
    """id -> folder uri"""
    out: dict[str, str] = {}
    for d in WS_ROOT.iterdir():
        if not d.is_dir():
            continue
        wj = d / "workspace.json"
        if not wj.is_file():
            continue
        try:
            data = json.loads(wj.read_text(encoding="utf-8"))
            folder = data.get("folder") or data.get("workspace") or ""
            out[d.name] = str(folder)
        except Exception:
            pass
    return out


def main() -> None:
    mapping = workspace_map()
    print("=== workspaceStorage map ===")
    for wid, folder in sorted(mapping.items(), key=lambda x: x[1]):
        print(f"{wid} -> {folder}")

    # حدد workspace ids
    target_ids = [wid for wid, f in mapping.items() if "goldenshield" in f.lower() and "goldenshield_ai" in f.lower()]
    parent_ids = [wid for wid, f in mapping.items() if f.lower().endswith("/goldenshield") or f.lower().endswith("%2fgoldenshield")]
    print("TARGET_IDS", target_ids)
    print("PARENT_IDS", parent_ids)

    if not target_ids:
        # fallback known
        target_ids = ["0c2eed867f41dcf1d99c4c425e74ded6"]
    target = target_ids[0]

    backup(GS)
    con = sqlite3.connect(str(GS))
    cur = con.cursor()

    rows = cur.execute(
        "SELECT composerId, workspaceIdentifier, createdAt, lastUpdatedAt, isArchived, isSubagent, recency, checkpointAt, value FROM composerHeaders"
    ).fetchall() if False else None

    # schema may use workspaceId not workspaceIdentifier
    cols = [c[1] for c in cur.execute("PRAGMA table_info(composerHeaders)")]
    print("COLS", cols)
    rows = cur.execute("SELECT * FROM composerHeaders").fetchall()
    print("TOTAL_HEADERS", len(rows))

    # index columns
    idx = {name: i for i, name in enumerate(cols)}
    ws_col = idx.get("workspaceId")
    id_col = idx.get("composerId", 0)

    counts = Counter()
    samples: dict[str, list[str]] = {}
    for r in rows:
        wid = str(r[ws_col]) if ws_col is not None else "?"
        counts[wid] += 1
        samples.setdefault(wid, [])
        if len(samples[wid]) < 3:
            samples[wid].append(str(r[id_col])[:36])

    print("=== headers by workspaceId ===")
    for wid, n in counts.most_common(20):
        folder = mapping.get(wid, "(unknown/global?)")
        print(f"{n:4d}  {wid}  {folder}")
        print("     samples:", ", ".join(samples.get(wid, [])))

    # أي workspaceIds مرتبطة بـ goldenshield أو فارغة نعيد توجيهها؟
    # أفضل: انسخ صفوف parent إلى target (duplicate with new workspaceId)
    source_ws = set(parent_ids)
    # أيضاً أي id يظهر في mapping لمسار goldenshield بدون AI
    for wid, folder in mapping.items():
        fl = folder.lower()
        if "goldenshield" in fl and "goldenshield_ai" not in fl and "planning" not in fl:
            source_ws.add(wid)

    # إن لم نجد parent في composerHeaders، خذ أكثر workspaceId استخداماً غير target
    if not source_ws:
        for wid, _ in counts.most_common():
            if wid != target:
                source_ws.add(wid)
                break

    print("SOURCE_WS", source_ws)
    print("RETARGET_TO", target)

    # حدّث الصفوف: غيّر workspaceId من المصدر إلى الهدف عند عدم وجود نفس composer في الهدف
    existing_target = {
        str(r[id_col])
        for r in rows
        if ws_col is not None and str(r[ws_col]) == target
    }
    updated = 0
    inserted = 0
    for r in rows:
        cid = str(r[id_col])
        wid = str(r[ws_col]) if ws_col is not None else ""
        if wid not in source_ws:
            continue
        if cid in existing_target:
            continue
        # حدّث صف المصدر ليشير إلى الهدف (أبسط لاستعادة القائمة)
        cur.execute(
            "UPDATE composerHeaders SET workspaceId=? WHERE composerId=? AND workspaceId=?",
            (target, cid, wid),
        )
        updated += 1
        existing_target.add(cid)
        print("RELINK", cid[:36], wid[:12], "->", target[:12])

    # إن كان عدد الهدف ما زال قليلاً: انقل أيضاً المحادثات ذات workspaceId غير معروف إن كان اسمها/مسارها goldenshield في value
    # اختياري محدود
    con.commit()

    after = Counter(
        str(r[ws_col])
        for r in cur.execute("SELECT * FROM composerHeaders").fetchall()
    )
    print("=== AFTER ===")
    for wid, n in after.most_common(15):
        print(f"{n:4d}  {wid}  {mapping.get(wid, '')}")
    print("UPDATED", updated, "INSERTED", inserted)
    con.close()
    print("DONE — أعد تحميل Cursor: Ctrl+Shift+P → Developer: Reload Window")


if __name__ == "__main__":
    main()
