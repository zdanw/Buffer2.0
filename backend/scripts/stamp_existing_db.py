"""
将已有本地 SQLite（此前由 create_all 建表）标记为 Alembic head，避免重复建表。

用法（在 backend 目录）:
  python -m scripts.stamp_existing_db
"""
from bebcare.db.migrate import stamp_head


def main() -> None:
    stamp_head()
    print("Stamped existing database to alembic head (001_initial).")


if __name__ == "__main__":
    main()
