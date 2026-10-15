"""Startet YouSplit als Home-Assistant-Add-on.

Ablauf: Add-on-Optionen lesen → PostgreSQL im Container initialisieren und
starten (Daten in /data/postgres, wird von Home Assistant gesichert) → uvicorn
starten → beim Beenden PostgreSQL sauber herunterfahren.
"""

import json
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

import uvicorn

OPTIONS_FILE = Path("/data/options.json")
PG_BIN = next(Path("/usr/lib/postgresql").glob("*/bin"))
PG_DATA = Path("/data/postgres")
PG_USER = "yousplit"
PG_DB = "yousplit"

logger = logging.getLogger("yousplit.addon")


def pg(command: str, *args: str, capture: bool = False) -> str:
    """Führt ein PostgreSQL-Programm als Benutzer ``postgres`` aus.

    Ohne ``capture`` landet die Ausgabe direkt im Add-on-Log. ``cwd=/tmp``, weil
    der Benutzer ``postgres`` das Arbeitsverzeichnis /app nicht lesen darf.
    """
    result = subprocess.run(
        ["runuser", "-u", "postgres", "--", str(PG_BIN / command), *args],
        check=True,
        cwd="/tmp",
        capture_output=capture,
        text=True,
    )
    return result.stdout if capture else ""


def start_postgres() -> None:
    PG_DATA.mkdir(parents=True, exist_ok=True)
    # Bei jedem Start: Nach einer Backup-Wiederherstellung koennen Besitzer oder
    # Rechte abweichen, dann verweigert Postgres den Start.
    subprocess.run(["chown", "-R", "postgres:postgres", str(PG_DATA)], check=True)
    PG_DATA.chmod(0o700)

    if not (PG_DATA / "PG_VERSION").exists():
        logger.info("Initialisiere neue PostgreSQL-Datenbank in %s", PG_DATA)
        # trust-Login nur lokal: Postgres lauscht nur auf 127.0.0.1 im Container
        pg("initdb", "-D", str(PG_DATA), "-U", PG_USER, "-A", "trust",
           "--encoding=UTF8", "--locale=C.UTF-8")

    # Nach einem harten Stopp bleibt die Lock-Datei liegen. Im frischen Container
    # kann ihre alte PID zufaellig einem anderen Prozess gehoeren — dann haelt
    # Postgres die Datenbank faelschlich fuer belegt. /data gehoert exklusiv
    # diesem Add-on, also laeuft hier sicher kein zweiter Server.
    (PG_DATA / "postmaster.pid").unlink(missing_ok=True)

    pg("pg_ctl", "-D", str(PG_DATA), "-w", "-t", "60",
       "-o", "-c listen_addresses=127.0.0.1", "start")

    exists = pg("psql", "-h", "127.0.0.1", "-U", PG_USER, "-d", "postgres", "-tAc",
                f"SELECT 1 FROM pg_database WHERE datname='{PG_DB}'", capture=True)
    if exists.strip() != "1":
        pg("createdb", "-h", "127.0.0.1", "-U", PG_USER, PG_DB)


def stop_postgres() -> None:
    logger.info("Fahre PostgreSQL herunter")
    try:
        pg("pg_ctl", "-D", str(PG_DATA), "-m", "fast", "-w", "stop")
    except subprocess.CalledProcessError:
        logger.exception("PostgreSQL liess sich nicht sauber stoppen")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    options = {}
    if OPTIONS_FILE.exists():
        options = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))

    log_level = options.get("log_level", "INFO")
    os.environ["LOG_LEVEL"] = log_level
    os.environ.setdefault("DATABASE_URL", f"postgresql://{PG_USER}@127.0.0.1:5432/{PG_DB}")

    # uvicorn loest SIGTERM nach dem eigenen Shutdown erneut aus. Ohne Handler
    # toetet das Python sofort (unter tini, init: true), und der finally-Block
    # mit stop_postgres() laeuft nie. SystemExit dagegen durchlaeuft finally.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    start_postgres()
    try:
        # app_dir: "python /run.py" setzt sys.path auf "/", nicht auf /app
        uvicorn.run("main:app", app_dir="/app", host="0.0.0.0", port=8099,
                    log_level=log_level.lower())
    finally:
        stop_postgres()


if __name__ == "__main__":
    main()
