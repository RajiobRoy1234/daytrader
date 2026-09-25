from datetime import date, datetime
from typing import List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import PARTITIONED_TABLES


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


def _month_bounds(when: date) -> Tuple[date, date]:
    start = when.replace(day=1)
    end = date(start.year + 1, 1, 1) if start.month == 12 else date(start.year, start.month + 1, 1)
    return start, end


def partition_name(table: str, period_start: date) -> str:
    return f"{table}_{period_start:%Y_%m}"


def ensure_partition(db: Session, table: str, when: date | datetime) -> str:
    """Create the monthly partition covering `when` for a partitioned table, if missing.
    Safe to call before every insert - CREATE TABLE IF NOT EXISTS is idempotent. `table` must
    be one of PARTITIONED_TABLES; that whitelist check is what makes the f-string DDL below
    safe to build (partition bounds can't be bound params in PARTITION OF ... FOR VALUES)."""
    if table not in PARTITIONED_TABLES:
        raise ValueError(f"{table!r} is not a partitioned table (see models.PARTITIONED_TABLES)")

    start, end = _month_bounds(_as_date(when))
    name = partition_name(table, start)
    db.execute(text(
        f'CREATE TABLE IF NOT EXISTS "{name}" PARTITION OF "{table}" '
        f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"
    ))
    return name


def ensure_partitions_for_range(db: Session, table: str, start: date | datetime, end: date | datetime) -> List[str]:
    """Create every monthly partition needed to cover [start, end], inclusive."""
    created = []
    cursor = _as_date(start)
    end_date = _as_date(end)
    while cursor <= end_date:
        created.append(ensure_partition(db, table, cursor))
        _, cursor = _month_bounds(cursor)
    return created
