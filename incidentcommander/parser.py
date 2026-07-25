from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

LEVELS = ("TRACE", "DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL")

@dataclass(frozen=True)
class LogEvent:
    line_number: int
    raw: str
    timestamp: datetime | None
    level: str
    service: str
    message: str

_TIMESTAMP_PATTERNS = [
    "%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
]
LEVEL_RE = re.compile(r"\b(" + "|".join(LEVELS) + r")\b", re.I)
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[,.]\d+)?Z?)")
SERVICE_RE = re.compile(r"(?:service|app|component|logger)[=:]\s*([\w.-]+)", re.I)
BRACKET_RE = re.compile(r"\[([\w.-]+)\]")


def _parse_timestamp(value: str) -> datetime | None:
    value = value.replace(",", ".")
    for fmt in _TIMESTAMP_PATTERNS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_lines(lines: Iterable[str]) -> list[LogEvent]:
    events: list[LogEvent] = []
    for number, raw in enumerate(lines, 1):
        raw = raw.rstrip("\n")
        if not raw.strip():
            continue
        ts_match = TS_RE.search(raw)
        timestamp = _parse_timestamp(ts_match.group(1)) if ts_match else None
        level_match = LEVEL_RE.search(raw)
        level = level_match.group(1).upper() if level_match else "INFO"
        if level == "WARNING":
            level = "WARN"
        service_match = SERVICE_RE.search(raw)
        if service_match:
            service = service_match.group(1)
        else:
            brackets = BRACKET_RE.findall(raw)
            service = brackets[-1] if brackets else "unknown"
        message = raw[ts_match.end():].lstrip(" -") if ts_match else raw
        events.append(LogEvent(number, raw, timestamp, level, service, message))
    return events


def parse_text(text: str) -> list[LogEvent]:
    return parse_lines(text.splitlines())
