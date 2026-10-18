import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
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


def ensure_schema_updates() -> None:
    """Ruestet nachtraeglich ergaenzte Spalten auf bestehenden Datenbanken nach.

    ``Base.metadata.create_all`` legt nur fehlende *Tabellen* an und aendert
    vorhandene nie. Bis Alembic eingefuehrt ist, fuegt diese Funktion neue Spalten
    idempotent per ``ADD COLUMN IF NOT EXISTS`` hinzu (nur PostgreSQL; frische
    Datenbanken haben die Spalten bereits durch ``create_all``).
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        # Der Kassenbon-Scan (Ollama) wurde entfernt (2026-10-08). Die Tabelle
        # der Scan-Jobs haelt nur fluechtigen Status und haengt per Fremdschluessel
        # an den Listen — ohne Modell wuerde sie das Loeschen einer Liste blockieren.
        connection.execute(text("DROP TABLE IF EXISTS receipt_jobs"))
        connection.execute(
            text("ALTER TABLE shared_lists ADD COLUMN IF NOT EXISTS members JSON")
        )
        connection.execute(
            text("ALTER TABLE shared_lists ADD COLUMN IF NOT EXISTS member_users JSON")
        )
