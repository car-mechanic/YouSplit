"""Startet YouSplit als Home-Assistant-Add-on.

Ablauf: Add-on-Optionen lesen → PostgreSQL im Container initialisieren und
starten (Daten in /data/postgres, wird von Home Assistant gesichert) → uvicorn
starten → beim Beenden PostgreSQL sauber herunterfahren.
"""

import json
import logging
import os
import subprocess
from pathlib import Path

import uvicorn

OPTIONS_FILE = Path("/data/options.json")
PG_BIN = next(Path("/usr/lib/postgresql").glob("*/bin"))
PG_DATA = Path("/data/postgres")
PG_USER = "yousplit"
PG_DB = "yousplit"

logger = logging.getLogger("yousplit.addon")


def pg(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Führt ein PostgreSQL-Programm als Benutzer ``postgres`` aus."""
    return subprocess.run(
        ["runuser", "-u", "postgres", "--", str(PG_BIN / command), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def start_postgres() -> None:
    PG_DATA.parent.mkdir(parents=True, exist_ok=True)
    if not (PG_DATA / "PG_VERSION").exists():
        logger.info("Initialisiere neue PostgreSQL-Datenbank in %s", PG_DATA)
        PG_DATA.mkdir(exist_ok=True)
        subprocess.run(["chown", "-R", "postgres:postgres", str(PG_DATA)], check=True)
        PG_DATA.chmod(0o700)
        # trust-Login nur lokal: Postgres lauscht nur auf 127.0.0.1 im Container
        pg("initdb", "-D", str(PG_DATA), "-U", PG_USER, "-A", "trust",
           "--encoding=UTF8", "--locale=C.UTF-8")

    pg("pg_ctl", "-D", str(PG_DATA), "-w", "-t", "60", "-l", "/tmp/postgres.log",
       "-o", "-c listen_addresses=127.0.0.1", "start")

    exists = pg("psql", "-h", "127.0.0.1", "-U", PG_USER, "-d", "postgres", "-tAc",
                f"SELECT 1 FROM pg_database WHERE datname='{PG_DB}'")
    if exists.stdout.strip() != "1":
        pg("createdb", "-h", "127.0.0.1", "-U", PG_USER, PG_DB)


def stop_postgres() -> None:
    logger.info("Fahre PostgreSQL herunter")
    subprocess.run(
        ["runuser", "-u", "postgres", "--", str(PG_BIN / "pg_ctl"),
         "-D", str(PG_DATA), "-m", "fast", "-w", "stop"],
        check=False,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    options = {}
    if OPTIONS_FILE.exists():
        options = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))

    log_level = options.get("log_level", "INFO")
    os.environ["LOG_LEVEL"] = log_level
    os.environ.setdefault("DATABASE_URL", f"postgresql://{PG_USER}@127.0.0.1:5432/{PG_DB}")

    start_postgres()
    try:
        # uvicorn fängt SIGTERM ab und kehrt dann hierher zurück
        uvicorn.run("main:app", host="0.0.0.0", port=8099, log_level=log_level.lower())
    finally:
        stop_postgres()


if __name__ == "__main__":
    main()
