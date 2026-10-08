"""Zentrales Logging-Setup des Backends.

Ersetzt die frueheren verstreuten ``print(..., flush=True)``-Aufrufe durch das
Standard-``logging``: einheitliches Format mit Zeitstempel, Level und Modulname,
sodass sich ``docker compose logs backend`` gezielt filtern laesst, z. B.:

    docker compose logs backend | findstr "yousplit.lists"
    docker compose logs backend | findstr "ERROR WARNING"

Das Log-Level ist per Environment-Variable ``LOG_LEVEL`` steuerbar
(Default ``INFO``).
"""

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Konfiguriert den Root-Logger (stdout → Docker-Log).

    Idempotent: Bei ``uvicorn --reload`` wird ``main`` im Worker-Prozess erneut
    importiert — ``force=True`` verhindert doppelte Handler (und damit doppelte
    Log-Zeilen). Die eigenen Logger von uvicorn bleiben unberuehrt.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    # httpx loggt jeden Request auf INFO — das wuerde bei den Wechselkurs-
    # Abfragen nur rauschen.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
