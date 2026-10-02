import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Fallback = die Zugangsdaten aus der docker-compose.yml
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://yousplit:yousplit@db:5432/yousplit",
)

# SQLAlchemy >= 2.1 waehlt fuer "postgresql://" den Treiber psycopg (v3) statt
# psycopg2 — installiert ist aber psycopg2-binary (requirements.txt). Deshalb den
# Treiber explizit festlegen; funktioniert mit 2.0 und 2.1 (SQLite-URLs bleiben
# unberuehrt).
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg2://", 1
    )

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI-Dependency: liefert eine Session und schließt sie nach dem Request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
