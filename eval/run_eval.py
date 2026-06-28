"""Evaluation harness for the creddy text-to-SQL layer.

Each case in ``eval_dataset.json`` pairs a natural-language question with a
"golden" SQL query and a set of correctness checks. The harness:

  * runs every golden query *through the SQL guard* (proving the guard accepts
    legitimate analytics), then
  * executes it read-only and verifies the result against the checks.

This doubles as a regression baseline: when an LLM generates SQL for one of
these questions, you can compare its output against the golden result here.

Run:  python eval/run_eval.py
Exit code is non-zero if any case fails (handy for CI).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from creddy.config import Settings
from creddy.db import connect
from creddy.sql_guard import validate_and_prepare

DATASET = Path(__file__).with_name("eval_dataset.json")


def _check(check: dict, columns: list[str], rows: list[dict]) -> bool:
    kind = check["type"]
    if kind == "columns":
        return set(check["value"]).issubset(set(columns))
    if kind == "min_rows":
        return len(rows) >= check["value"]
    if kind == "value_between":
        col, low, high = check["column"], check["min"], check["max"]
        for row in rows:
            value = row.get(col)
            if value is None:
                continue
            if not (low <= float(value) <= high):
                return False
        return True
    raise ValueError(f"Unknown check type: {kind}")


def main() -> None:
    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    settings = Settings()
    passed = 0

    with connect(settings, read_only=True) as conn:
        for case in cases:
            try:
                safe_sql = validate_and_prepare(case["sql"], row_limit=settings.query_row_limit)
                cur = conn.execute(safe_sql)
                rows = cur.fetchall()
                columns = [d.name for d in cur.description] if cur.description else []
                ok = all(_check(c, columns, rows) for c in case.get("checks", []))
                detail = "" if ok else "  -> checks failed"
            except Exception as exc:  # noqa: BLE001
                ok = False
                detail = f"  -> error: {exc}"

            status = "PASS" if ok else "FAIL"
            passed += int(ok)
            print(f"[{status}] {case['id']}: {case['question']}{detail}")

    total = len(cases)
    pct = (passed / total * 100) if total else 0.0
    print(f"\n{passed}/{total} passed ({pct:.0f}%)")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
