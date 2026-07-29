"""عرض تقارير الصفقات الخاسرة المحفوظة."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from operations.loss_trade_report import (  # noqa: E402
    find_reports_for_symbol,
    format_losing_trade_report_telegram,
    format_losing_trades_digest,
    load_losing_trade_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="عرض تقارير الصفقات الخاسرة")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--symbol", type=str, default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.symbol:
        rows = find_reports_for_symbol(args.symbol, limit=args.limit)
    else:
        rows = load_losing_trade_reports(limit=args.limit)

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if args.symbol and rows:
        print("\n\n────────\n\n".join(format_losing_trade_report_telegram(r) for r in rows))
    else:
        print(format_losing_trades_digest(rows, limit=args.limit))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
