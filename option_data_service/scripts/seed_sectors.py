"""Seed the sectors table with the 11 canonical GICS sectors. Safe to re-run.

Does not set benchmark_symbol_id - wiring each sector to a tracking index/ETF ticker (e.g.
'XLK' for Information Technology) is a separate ingestion step once you've decided which
symbol should back each one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Sector

# code, name, display_order - order matches GICS's own sector numbering (10-60).
SECTORS = [
    ("energy", "Energy", 10),
    ("materials", "Materials", 15),
    ("industrials", "Industrials", 20),
    ("consumer_discretionary", "Consumer Discretionary", 25),
    ("consumer_staples", "Consumer Staples", 30),
    ("health_care", "Health Care", 35),
    ("financials", "Financials", 40),
    ("information_technology", "Information Technology", 45),
    ("communication_services", "Communication Services", 50),
    ("utilities", "Utilities", 55),
    ("real_estate", "Real Estate", 60),
]


def main():
    db = SessionLocal()
    try:
        for code, name, display_order in SECTORS:
            sector = db.query(Sector).filter(Sector.code == code).first()
            if sector:
                sector.name = name
                sector.display_order = display_order
            else:
                db.add(Sector(code=code, name=name, display_order=display_order))
        db.commit()
        print(f"Seeded {len(SECTORS)} sectors")
    finally:
        db.close()


if __name__ == "__main__":
    main()
