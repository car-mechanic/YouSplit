"""Startet YouSplit als Home-Assistant-Add-on.

Liest die Add-on-Optionen aus /data/options.json, setzt die SQLite-Datenbank
unter /data (wird von Home Assistant gesichert) und startet uvicorn.
"""

import json
import os
from pathlib import Path

import uvicorn

OPTIONS_FILE = Path("/data/options.json")


def main() -> None:
    options = {}
    if OPTIONS_FILE.exists():
        options = json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))

    log_level = options.get("log_level", "INFO")
    os.environ["LOG_LEVEL"] = log_level
    os.environ.setdefault("DATABASE_URL", "sqlite:////data/yousplit.db")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8099,
        log_level=log_level.lower(),
    )


if __name__ == "__main__":
    main()
