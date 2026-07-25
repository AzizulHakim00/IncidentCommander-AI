from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    source_name TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    severity TEXT NOT NULL,
    health_score INTEGER NOT NULL,
    root_cause TEXT NOT NULL,
    services TEXT NOT NULL,
    event_count INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
)
"""


def initialise(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(SCHEMA)


def save_incident(path: str | Path, result: dict, source_name: str, notes: str = "") -> int:
    initialise(path)
    summary = result["summary"]
    root_cause = result["root_causes"][0]["cause"] if result["root_causes"] else "Unknown"
    services = sorted(result["frame"]["service"].astype(str).unique().tolist())
    with sqlite3.connect(path) as connection:
        cursor = connection.execute(
            """INSERT INTO incidents(created_at, source_name, fingerprint, severity, health_score, root_cause, services, event_count, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now(timezone.utc).isoformat(), source_name, summary["fingerprint"], summary["severity"], summary["health_score"], root_cause, json.dumps(services), summary["total_events"], notes),
        )
        return int(cursor.lastrowid)


def list_incidents(path: str | Path) -> pd.DataFrame:
    initialise(path)
    with sqlite3.connect(path) as connection:
        return pd.read_sql_query("SELECT * FROM incidents ORDER BY id DESC", connection)


def similar_incidents(path: str | Path, result: dict, limit: int = 5) -> pd.DataFrame:
    history = list_incidents(path)
    if history.empty:
        return history
    summary = result["summary"]
    root = result["root_causes"][0]["cause"] if result["root_causes"] else "Unknown"
    services = set(result["frame"]["service"].astype(str).unique())

    def score(row) -> float:
        row_services = set(json.loads(row["services"]))
        union = services | row_services
        service_score = len(services & row_services) / len(union) if union else 0
        return round(0.5 * (row["root_cause"] == root) + 0.3 * service_score + 0.2 * (row["severity"] == summary["severity"]), 3)

    history["similarity"] = history.apply(score, axis=1)
    return history.sort_values(["similarity", "id"], ascending=False).head(limit)
