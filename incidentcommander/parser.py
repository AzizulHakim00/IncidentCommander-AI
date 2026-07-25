from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

LEVELS = ("TRACE", "DEBUG", "INFO", "NOTICE", "WARN", "WARNING", "ERROR", "CRITICAL", "FATAL")


@dataclass(frozen=True)
class LogEvent:
    line_number: int
    source: str
    raw: str
    timestamp: datetime | None
    level: str
    service: str
    message: str
    request_id: str | None = None
    trace_id: str | None = None
    host: str | None = None
    dependency: str | None = None
    duration_ms: float | None = None
    status_code: int | None = None


_TIMESTAMP_PATTERNS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
)
LEVEL_RE = re.compile(r"\b(" + "|".join(LEVELS) + r")\b", re.I)
TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[,.]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)")
BRACKET_RE = re.compile(r"\[([\w.-]+)\]")
KV_PATTERNS = {
    "service": re.compile(r"(?:service|app|component|logger)[=:]\s*[\"']?([\w.-]+)", re.I),
    "request_id": re.compile(r"(?:request[_-]?id|req[_-]?id|correlation[_-]?id)[=:]\s*[\"']?([\w.-]+)", re.I),
    "trace_id": re.compile(r"(?:trace[_-]?id|traceid)[=:]\s*[\"']?([\w.-]+)", re.I),
    "host": re.compile(r"(?:host|hostname|node)[=:]\s*[\"']?([\w.-]+)", re.I),
    "dependency": re.compile(r"(?:dependency|upstream|downstream)[=:]\s*[\"']?([\w.-]+)", re.I),
    "duration": re.compile(r"(?:duration|latency|elapsed)(?:_ms)?[=:]\s*([0-9]+(?:\.[0-9]+)?)(?:\s*(ms|s)\b)?(?=\s|$|[,;])", re.I),
    "status": re.compile(r"(?:status|status_code|http_status)[=:]\s*(\d{3})\b", re.I),
}


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    variants = (text,) if text.endswith("Z") else (text, text.replace(" ", "T", 1))
    for candidate in variants:
        for fmt in _TIMESTAMP_PATTERNS:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalise_level(value: object) -> str:
    level = str(value or "INFO").upper()
    return "WARN" if level == "WARNING" else level if level in LEVELS else "INFO"


def _first(mapping: dict, *keys: str, default=None):
    lowered = {str(k).lower(): v for k, v in mapping.items()}
    for key in keys:
        if key.lower() in lowered and lowered[key.lower()] not in (None, ""):
            return lowered[key.lower()]
    return default


def _json_event(obj: dict, line_number: int, source: str, raw: str) -> LogEvent:
    message = str(_first(obj, "message", "msg", "log", "event", default=raw))
    duration = _first(obj, "duration_ms", "latency_ms", "elapsed_ms")
    status = _first(obj, "status_code", "http_status", "status")
    try:
        duration_ms = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_ms = None
    try:
        status_code = int(status) if status is not None and str(status).isdigit() else None
    except (TypeError, ValueError):
        status_code = None
    return LogEvent(
        line_number=line_number,
        source=source,
        raw=raw,
        timestamp=_parse_timestamp(_first(obj, "timestamp", "time", "@timestamp", "datetime")),
        level=_normalise_level(_first(obj, "level", "severity", "loglevel")),
        service=str(_first(obj, "service", "app", "component", "logger", default="unknown")),
        message=message,
        request_id=_first(obj, "request_id", "requestid", "req_id", "correlation_id"),
        trace_id=_first(obj, "trace_id", "traceid"),
        host=_first(obj, "host", "hostname", "node"),
        dependency=_first(obj, "dependency", "upstream", "downstream"),
        duration_ms=duration_ms,
        status_code=status_code,
    )


def _text_event(raw: str, line_number: int, source: str) -> LogEvent:
    ts_match = TS_RE.search(raw)
    timestamp = _parse_timestamp(ts_match.group(1)) if ts_match else None
    level_match = LEVEL_RE.search(raw)
    level = _normalise_level(level_match.group(1) if level_match else "INFO")
    values: dict[str, object] = {}
    for key, pattern in KV_PATTERNS.items():
        match = pattern.search(raw)
        values[key] = match.groups() if match else None
    service_groups = values["service"]
    if service_groups:
        service = service_groups[0]
    else:
        brackets = BRACKET_RE.findall(raw)
        service = brackets[-1] if brackets else "unknown"
    duration_ms = None
    if values["duration"]:
        number, unit = values["duration"]
        duration_ms = float(number) * (1000 if unit and unit.lower() == "s" else 1)
    status_code = int(values["status"][0]) if values["status"] else None
    message = raw[ts_match.end():].lstrip(" -") if ts_match else raw
    return LogEvent(
        line_number=line_number,
        source=source,
        raw=raw,
        timestamp=timestamp,
        level=level,
        service=service,
        message=message,
        request_id=values["request_id"][0] if values["request_id"] else None,
        trace_id=values["trace_id"][0] if values["trace_id"] else None,
        host=values["host"][0] if values["host"] else None,
        dependency=values["dependency"][0] if values["dependency"] else None,
        duration_ms=duration_ms,
        status_code=status_code,
    )


def _parse_csv(text: str, source: str) -> list[LogEvent] | None:
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except csv.Error:
        return None
    if not rows or not any(k and k.lower() in {"message", "msg", "log", "event"} for k in rows[0]):
        return None
    return [_json_event(row, idx, source, json.dumps(row, default=str)) for idx, row in enumerate(rows, 2)]


def parse_lines(lines: Iterable[str], source: str = "uploaded.log") -> list[LogEvent]:
    events: list[LogEvent] = []
    for number, raw_line in enumerate(lines, 1):
        raw = raw_line.rstrip("\n")
        if not raw.strip():
            continue
        stripped = raw.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict):
                    events.append(_json_event(obj, number, source, raw))
                    continue
            except json.JSONDecodeError:
                pass
        events.append(_text_event(raw, number, source))
    return events


def parse_text(text: str, source: str = "uploaded.log") -> list[LogEvent]:
    if source.lower().endswith(".csv"):
        csv_events = _parse_csv(text, source)
        if csv_events is not None:
            return csv_events
    return parse_lines(text.splitlines(), source=source)


def parse_sources(sources: list[tuple[str, str]]) -> list[LogEvent]:
    events: list[LogEvent] = []
    for source_name, text in sources:
        events.extend(parse_text(text, source=source_name))
    return events
