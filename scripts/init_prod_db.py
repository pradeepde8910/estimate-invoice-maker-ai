"""
Production database schema initializer — DevOps entry point.

Creates any missing tables from the current SQLAlchemy models (db.py) and
seeds the rate card. Safe to re-run: it never drops or truncates existing
tables or data (unlike scripts/reset_db.py, which is destructive and
dev-only — never run that against production).

Usage:
    DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/init_prod_db.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.resolve()))

from db import engine, Base, init_db


def init_production_db():
    print("Production Database Schema Init")
    print("-" * 30)
    print(f"Target: {engine.url.render_as_string(hide_password=True)}")

    print("Creating any missing tables (existing tables/data are left untouched)...")
    Base.metadata.create_all(bind=engine)
    print("Schema up to date.")

    print("Seeding default rate card (only if empty)...")
    init_db()

    print("-" * 30)
    print("Production database is ready.")


if __name__ == "__main__":
    init_production_db()
