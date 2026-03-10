#!/usr/bin/env python3
"""Inspect the macOS Messages source database for alternate content fields."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


PRINTABLE_RE = re.compile(rb"[\x20-\x7E]{4,}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Messages chat.db rows and schema.")
    parser.add_argument(
        "--db-path",
        default=str(Path("~/Library/Messages/chat.db").expanduser()),
        help="Path to Messages chat.db",
    )
    parser.add_argument(
        "--row-ids",
        default="",
        help="Comma-separated message ROWIDs to inspect.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output JSON path.",
    )
    return parser.parse_args()


def open_db(path: str) -> sqlite3.Connection:
    expanded = str(Path(path).expanduser())
    conn = sqlite3.connect(f"file:{expanded}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def printable_strings(blob: bytes | None, *, limit: int = 12) -> list[str]:
    if not blob:
        return []
    values: list[str] = []
    for match in PRINTABLE_RE.findall(blob):
        text = match.decode("utf-8", errors="ignore").strip()
        if not text:
            continue
        if text not in values:
            values.append(text)
        if len(values) >= limit:
            break
    return values


def list_columns(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    return [
        {
            "cid": int(row["cid"]),
            "name": str(row["name"]),
            "type": str(row["type"]),
            "notnull": bool(row["notnull"]),
            "default": row["dflt_value"],
            "pk": bool(row["pk"]),
        }
        for row in conn.execute(f"PRAGMA table_info({table_name})")
    ]


def inspect_rows(conn: sqlite3.Connection, row_ids: list[int]) -> list[dict[str, Any]]:
    if not row_ids:
        return []
    placeholders = ",".join("?" for _ in row_ids)
    rows = conn.execute(
        f"SELECT * FROM message WHERE ROWID IN ({placeholders}) ORDER BY ROWID ASC",
        row_ids,
    ).fetchall()
    inspected: list[dict[str, Any]] = []
    for row in rows:
        non_null_fields: dict[str, Any] = {}
        for key in row.keys():
            value = row[key]
            if value is None:
                continue
            if isinstance(value, bytes):
                non_null_fields[key] = {
                    "type": "blob",
                    "bytes": len(value),
                    "printable_strings": printable_strings(value),
                }
            else:
                text = str(value)
                non_null_fields[key] = text if len(text) <= 240 else text[:237] + "..."
        inspected.append({"row_id": int(row["ROWID"]), "non_null_fields": non_null_fields})
    return inspected


def summarize_non_null_fields(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for key in row.get("non_null_fields", {}):
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def main() -> None:
    args = parse_args()
    row_ids = [int(part) for part in args.row_ids.split(",") if part.strip()]
    conn = open_db(args.db_path)
    try:
        columns = list_columns(conn, "message")
        inspected_rows = inspect_rows(conn, row_ids)
    finally:
        conn.close()

    result = {
        "message_columns": columns,
        "row_count": len(inspected_rows),
        "non_null_field_counts": summarize_non_null_fields(inspected_rows),
        "rows": inspected_rows,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote inspection output to {output_path}")
        return
    print(rendered)


if __name__ == "__main__":
    main()
