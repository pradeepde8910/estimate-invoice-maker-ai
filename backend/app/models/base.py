from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Note: In V2, we strictly use PostgreSQL for production.
# All money columns MUST use NUMERIC(12,2) instead of Float.
# Example:
# from sqlalchemy import Column, Numeric
# amount = Column(Numeric(12, 2), nullable=False, default=0.00)
