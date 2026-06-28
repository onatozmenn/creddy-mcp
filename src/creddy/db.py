"""Database access helpers built on psycopg 3."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from .config import Settings


@contextmanager
def connect(settings: Settings, *, read_only: bool = True) -> Iterator[psycopg.Connection]:
    """Open a connection as a context manager.

    When ``read_only`` is True the *database session itself* is marked read-only.
    This is defense-in-depth: even if a write somehow slipped past the SQL guard,
    Postgres would reject it.
    """
    conn = psycopg.connect(settings.dsn, row_factory=dict_row)
    try:
        if read_only:
            # Must be set before any transaction has started.
            conn.read_only = True
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_sql_script(settings: Settings, script_path: Path) -> None:
    """Execute a multi-statement ``.sql`` file (statements split on ``;``)."""
    raw = Path(script_path).read_text(encoding="utf-8")
    statements = [s.strip() for s in raw.split(";") if s.strip()]
    with connect(settings, read_only=False) as conn:
        with conn.cursor() as cur:
            for statement in statements:
                cur.execute(statement)
