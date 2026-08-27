import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# V2 defaults to a dedicated staging DB, ideally PostgreSQL for NUMERIC(12,2) support.
# If not provided, it falls back to the V1 copied staging database (SQLite).
#
# Reads DATABASE_URL first, matching app/config.py's resolution (that module
# is the one app/core/database.py — used by most of the app — actually
# reads). V2_DATABASE_URL is kept as a fallback for compatibility, but the
# two env vars naming different things was a real bug: with only
# V2_DATABASE_URL checked here, setting DATABASE_URL alone (e.g. to point
# alembic and the app at Postgres) would leave this module — which alembic's
# env.py imports its migration target from — silently still pointed at
# SQLite, so `alembic upgrade` would migrate the wrong database while the
# running app connected to the right one.
DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("V2_DATABASE_URL", "sqlite:///../pixous_staging.db"))

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
