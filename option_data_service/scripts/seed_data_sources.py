"""Seed the data_sources table with the vendors this project knows about. Safe to re-run."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.common import get_or_create_data_source

SOURCES = {
    "yahoo": "Yahoo Finance",
    "bloomberg": "Bloomberg",
    "cboe": "Cboe DataShop",
    "schwab": "Charles Schwab",
}


def main():
    db = SessionLocal()
    try:
        for code, name in SOURCES.items():
            get_or_create_data_source(db, code, name)
        db.commit()
        print(f"Seeded data sources: {', '.join(SOURCES)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
