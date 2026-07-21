"""
将本地 SQLite 表数据迁移到 Supabase (PostgreSQL)。

注意：当前本地 bebcare.db 里 product_dimensions 通常为 0 行；
真正有内容的多为 prompt_dimensions / prompt_dimension_compatibilities。
本脚本可按外键顺序迁移这些维度相关表（及可选 products）。

用法（在 backend 目录）:

  # 1) 确认本地行数
  python -m scripts.migrate_sqlite_to_supabase --dry-run

  # 2) 写入 Supabase（Session 模式连接串，端口 5432 + sslmode=require）
  set TARGET_DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-xxx.pooler.supabase.com:5432/postgres?sslmode=require
  python -m scripts.migrate_sqlite_to_supabase

  # 仅迁移指定表（逗号分隔）
  python -m scripts.migrate_sqlite_to_supabase --tables prompt_dimensions,prompt_dimension_compatibilities,product_dimensions
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

# 外键安全顺序：先父后子
DEFAULT_TABLES = [
    "products",
    "prompt_dimensions",
    "prompt_dimension_compatibilities",
    "product_dimensions",
]

JSON_COLUMNS = {
    "prompt_dimensions": {"lighting"},
    "product_dimensions": {"lighting"},
}


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_sqlite_path() -> Path:
    return _backend_dir() / "bebcare.db"


def _normalize_pg_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _parse_sqlite_value(table: str, col: str, value: Any) -> Any:
    if value is None:
        return None
    if col in JSON_COLUMNS.get(table, set()):
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return s
        return value
    if col in ("is_custom", "is_active") and isinstance(value, int):
        return bool(value)
    return value


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def count_sqlite(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def fetch_sqlite_rows(conn: sqlite3.Connection, table: str) -> tuple[list[str], list[tuple]]:
    cur = conn.execute(f'SELECT * FROM "{table}"')
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows


def upsert_postgres(engine, table: str, cols: list[str], rows: list[tuple], pk: str) -> int:
    if not rows:
        return 0

    col_list = ", ".join(_quote_ident(c) for c in cols)
    placeholders = ", ".join(f":{c}" for c in cols)
    updates = ", ".join(
        f"{_quote_ident(c)} = EXCLUDED.{_quote_ident(c)}" for c in cols if c != pk
    )
    sql = (
        f'INSERT INTO {_quote_ident(table)} ({col_list}) VALUES ({placeholders}) '
        f"ON CONFLICT ({_quote_ident(pk)}) DO UPDATE SET {updates}"
    )

    written = 0
    with engine.begin() as conn:
        for row in rows:
            payload = {
                c: _parse_sqlite_value(table, c, v) for c, v in zip(cols, row)
            }
            # lighting 等 JSON：用 CAST，避免驱动类型歧义
            conn.execute(text(sql), payload)
            written += 1
    return written


def table_pk(table: str) -> str:
    return {
        "products": "product_id",
        "prompt_dimensions": "dimension_id",
        "prompt_dimension_compatibilities": "id",
        "product_dimensions": "id",
    }[table]


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate SQLite tables to Supabase Postgres")
    parser.add_argument(
        "--sqlite",
        default=str(_default_sqlite_path()),
        help="本地 SQLite 路径（默认 backend/bebcare.db）",
    )
    parser.add_argument(
        "--tables",
        default=",".join(DEFAULT_TABLES),
        help="要迁移的表，逗号分隔",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只统计本地行数，不写入",
    )
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite 不存在: {sqlite_path}")

    tables = [t.strip() for t in args.tables.split(",") if t.strip()]
    # 按默认顺序排序，忽略未知表
    order = {name: i for i, name in enumerate(DEFAULT_TABLES)}
    tables = sorted(tables, key=lambda t: order.get(t, 999))

    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row

    print(f"Source SQLite: {sqlite_path}")
    for table in tables:
        try:
            n = count_sqlite(src, table)
        except sqlite3.OperationalError as e:
            print(f"  skip {table}: {e}")
            continue
        print(f"  {table}: {n} rows")

    if args.dry_run:
        print("Dry-run only. 未写入 Supabase。")
        src.close()
        return

    target = os.environ.get("TARGET_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not target or target.startswith("sqlite"):
        raise SystemExit(
            "请设置 TARGET_DATABASE_URL 为 Supabase Postgres 连接串（不要用本地 sqlite）。\n"
            "示例: set TARGET_DATABASE_URL=postgresql://postgres....:5432/postgres?sslmode=require"
        )

    engine = create_engine(_normalize_pg_url(target), pool_pre_ping=True)

    for table in tables:
        try:
            cols, rows = fetch_sqlite_rows(src, table)
        except sqlite3.OperationalError as e:
            print(f"SKIP {table}: {e}")
            continue
        if not rows:
            print(f"OK  {table}: 0 rows (nothing to copy)")
            continue
        pk = table_pk(table)
        n = upsert_postgres(engine, table, cols, rows, pk)
        print(f"OK  {table}: upserted {n} rows")

    src.close()
    print("Done.")


if __name__ == "__main__":
    main()
