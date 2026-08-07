import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.resolve()))

import config
from db import engine, Base, init_db, SessionLocal, User

def reset_database():
    print("Database Reset Utility")
    print("-" * 30)
    print(f"Target database: {config.DATABASE_URL}")

    is_sqlite = config.DATABASE_URL.startswith("sqlite")
    if not is_sqlite and os.environ.get("RESET_DB_CONFIRM") != "yes-i-am-sure":
        print(
            "Refusing to run: DATABASE_URL does not look like a local sqlite "
            "database, which usually means this is pointed at a shared/"
            "production database. If you really mean to drop all tables "
            "here, re-run with RESET_DB_CONFIRM=yes-i-am-sure set."
        )
        return

    confirmation = input(
        f"This will PERMANENTLY DELETE ALL DATA in {config.DATABASE_URL}. "
        "Type 'reset' to continue: "
    )
    if confirmation.strip().lower() != "reset":
        print("Aborted - no changes made.")
        return

    # 1. Drop all tables
    print("Dropping all existing database tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("Tables dropped successfully.")
    except Exception as e:
        print(f"Error dropping tables: {e}")
        return

    # 2. Recreate all tables
    print("Creating all tables from current SQLAlchemy models...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        return

    # 3. Initialize default records (sync rate cards, etc.)
    print("Seeding default settings and rate card configurations...")
    try:
        init_db()
        print("Defaults seeded successfully.")
    except Exception as e:
        print(f"Error seeding default settings: {e}")
        return

    print("-" * 30)
    print("Database reset completed successfully! You now have a fresh schema.")

if __name__ == "__main__":
    reset_database()
