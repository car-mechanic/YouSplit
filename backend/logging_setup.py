"""Zentrales Logging-Setup des Backends.

Ersetzt die frueheren verstreuten ``print(..., flush=True)``-Aufrufe durch das
Standard-``logging``: einheitliches Format mit Zeitstempel, Level und Modulname,
sodass sich ``docker compose logs backend`` gezielt filtern laesst, z. B.:

    docker compose logs backend | findstr "yousplit.receipts"
    docker compose logs backend | findstr "ERROR WARNING"

Das Log-Level ist per Environment-Variable ``LOG_LEVEL`` steuerbar
(Default ``INFO``; ``DEBUG`` zeigt z. B. auch rohe Modell-Antworten).
"""

import logging
import os
import sys

LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class _SkipJobPollingFilter(logging.Filter):
    """Blendet erfolgreiche Status-Abfragen (``GET .../receipt-jobs``) im
    uvicorn-Access-Log aus — das Frontend pollt alle paar Sekunden, das wuerde
    die eigentlich interessanten Zeilen im Docker-Log verdraengen."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn.access: args = (client, method, path, http_version, status)
        if isinstance(args, tuple) and len(args) == 5:
            _, method, path, _, status_code = args
            if (
                method == "GET"
                and str(path).endswith("/receipt-jobs")
                and status_code == 200
            ):
                return False
        return True


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
    # httpx loggt jeden Request auf INFO — das wuerde bei Status-Polling und
    # Ollama-Aufrufen nur rauschen.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _SkipJobPollingFilter) for f in access_logger.filters):
        access_logger.addFilter(_SkipJobPollingFilter())
