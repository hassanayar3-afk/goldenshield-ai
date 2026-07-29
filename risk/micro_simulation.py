"""محاكاة استباقية لآخر N صفقات مشابهة — طبقة مضافة (افتراضي: معطّل)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MicroSimResult:
    allowed: bool
    reason: str
    sample_size: int = 0
    win_rate: float | None = None


def run_micro_simulation(symbol: str, *, side: str = "buy") -> MicroSimResult:
    """يفحص آخر صفقات مشابهة من قاعدة البيانات؛ نقص البيانات = تمرير آمن."""
    try:
        settings = get_settings()
        if not bool(getattr(settings, "micro_simulation_enabled", False)):
            return MicroSimResult(True, "Micro-Simulation معطّل — تمرير")

        lookback = int(getattr(settings, "micro_simulation_lookback", 10) or 10)
        min_wr = float(getattr(settings, "micro_simulation_min_winrate", 0.50) or 0.50)

        rows = _load_recent_closed(symbol, limit=lookback)
        if len(rows) < max(3, lookback // 2):
            return MicroSimResult(
                True,
                f"Micro-Sim: بيانات غير كافية ({len(rows)}) — تمرير آمن",
                sample_size=len(rows),
            )

        wins = sum(1 for pnl in rows if pnl >= 0)
        wr = wins / len(rows)
        if wr < min_wr:
            return MicroSimResult(
                False,
                f"Micro-Sim: نجاح تاريخي {wr:.0%} < {min_wr:.0%} لـ {symbol} (n={len(rows)})",
                sample_size=len(rows),
                win_rate=wr,
            )
        return MicroSimResult(
            True,
            f"Micro-Sim OK {wr:.0%} (n={len(rows)})",
            sample_size=len(rows),
            win_rate=wr,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("run_micro_simulation(%s) فشل: %s", symbol, exc)
        return MicroSimResult(True, f"Micro-Sim خطأ — تمرير آمن: {exc}")


def _load_recent_closed(symbol: str, *, limit: int) -> list[float]:
    try:
        from config.settings import get_settings
        from database.connection import get_connection

        settings = get_settings()
        db = get_connection(settings.db_path)
        # محاولة مرنة لأسماء أعمدة شائعة
        cur = db.execute(
            """
            SELECT pnl FROM trades
            WHERE symbol = ? AND status IN ('closed', 'CLOSED', 'done')
            ORDER BY id DESC LIMIT ?
            """,
            (symbol, limit),
        )
        rows = cur.fetchall()
        out: list[float] = []
        for row in rows:
            try:
                out.append(float(row[0] if not isinstance(row, dict) else row.get("pnl", 0)))
            except (TypeError, ValueError, IndexError, KeyError):
                continue
        return out
    except Exception:
        # جدول غير متوافق — تمرير فارغ
        return []
