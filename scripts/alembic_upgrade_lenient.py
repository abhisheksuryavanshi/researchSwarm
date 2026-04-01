#!/usr/bin/env python3
"""Run ``alembic upgrade head``; exit 0 on benign MySQL duplicate/already-exists errors.

Intended for local setup reruns when the DB is in a messy state. Do not use in production
pipelines where migration failures must be strict.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# MySQL: table exists, duplicate column, duplicate key name
_IGNORE_MYSQL_ERRNOS = frozenset({1050, 1060, 1061})


def _mysql_errno(exc: BaseException | None) -> int | None:
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        args = getattr(cur, "args", ())
        if args and isinstance(args[0], int) and 1000 <= args[0] < 6000:
            return int(args[0])
        nxt = cur.__cause__
        if nxt is None and hasattr(cur, "orig"):
            nxt = cur.orig  # type: ignore[assignment]
        cur = nxt
    return None


def main() -> int:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)

    from alembic.config import Config
    from sqlalchemy.exc import OperationalError

    from alembic import command

    cfg = Config(str(ROOT / "alembic.ini"))
    try:
        command.upgrade(cfg, "head")
    except OperationalError as e:
        errno = _mysql_errno(e)
        if errno in _IGNORE_MYSQL_ERRNOS:
            print(
                f"⚠️  Ignoring MySQL error {errno} (already exists / duplicate); "
                "continuing local setup.",
                file=sys.stderr,
            )
            print(str(e), file=sys.stderr)
            return 0
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
