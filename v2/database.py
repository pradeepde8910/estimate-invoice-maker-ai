import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# V2 defaults to a dedicated staging DB, ideally PostgreSQL for NUMERIC(12,2) support.
# If not provided, it falls back to the V1 copied staging database (SQLite).
DATABASE_URL = os.getenv("V2_DATABASE_URL", "sqlite:///../pixous_staging.db")

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
