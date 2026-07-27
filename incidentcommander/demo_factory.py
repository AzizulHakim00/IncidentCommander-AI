from __future__ import annotations

import csv
import io
import json
import random
from datetime import datetime, timedelta, timezone


SCENARIOS = {
    "Database Meltdown": {
        "severity": "SEV-1",
        "story": "PostgreSQL connection-pool exhaustion cascades through orders, payments, and gateway services.",
        "accent": "#ff6476",
        "icon": "🗄️",
        "format": "log",
    },
    "Payment Cascade": {
        "severity": "SEV-2",
        "story": "A bank API outage triggers retries, rate limits, and checkout failures across the payment path.",
        "accent": "#ffd166",
        "icon": "💳",
        "format": "jsonl",
    },
    "Memory Storm": {
        "severity": "SEV-1",
        "story": "Worker and search nodes enter a memory-pressure loop, causing restarts and queue backlog.",
        "accent": "#a06dff",
        "icon": "🧠",
        "format": "log",
    },
    "Auth Attack": {
        "severity": "SEV-2",
        "story": "A coordinated credential attack creates authorization failures and rate-limit pressure.",
        "accent": "#39dcff",
        "icon": "🛡️",
        "format": "csv",
    },
}


def _request_id(prefix: int, index: int) -> str:
    return f"req-{prefix + index:05d}"


def _trace_id(prefix: int, index: int) -> str:
    return f"tr-{prefix + index:05d}"


def _database_meltdown(seed: int = 42) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    start = datetime(2026, 7, 27, 2, 0, tzinfo=timezone.utc)
    services = ["gateway", "orders", "payments", "inventory", "notification"]
    dependency = {
        "gateway": "orders",
        "orders": "postgres",
        "payments": "postgres",
        "inventory": "redis",
        "notification": "smtp",
    }
    lines: list[str] = []
    for index in range(260):
        timestamp = start + timedelta(seconds=index * 2)
        service = rng.choice(services)
        level, status, duration, message = "INFO", 200, max(25, int(rng.gauss(95, 30))), "request completed"
        if index > 80 and service in {"orders", "payments"}:
            progress = (index - 80) / 180
            duration = int(250 + 1200 * progress + rng.randint(0, 500))
            status = rng.choice([500, 502, 503, 504])
            level = "ERROR" if rng.random() < 0.75 else "WARN"
            message = rng.choice([
                "SQLSTATE connection refused database pool exhausted",
                "upstream timeout waiting for postgres",
                "too many connections database dependency failed",
                "deadlock detected retry budget exhausted",
            ])
        elif index > 150 and service == "gateway" and rng.random() < 0.65:
            level, status, duration = "WARN", 503, rng.randint(900, 1800)
            message = "upstream orders circuit breaker open"
        lines.append(
            f"{timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')} {level} [{service}] {message} "
            f"service={service} dependency={dependency[service]} request_id={_request_id(0, index)} "
            f"trace_id={_trace_id(0, index // 3)} host={service}-0{1 + index % 3} "
            f"duration_ms={duration} status={status}"
        )
    return [("database_meltdown.log", "\n".join(lines))]


def _payment_cascade(seed: int = 42) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    start = datetime(2026, 7, 27, 2, 0, tzinfo=timezone.utc)
    services = ["checkout", "payments", "fraud", "ledger", "gateway"]
    dependency = {
        "checkout": "payments",
        "payments": "bank-api",
        "fraud": "risk-api",
        "ledger": "postgres",
        "gateway": "checkout",
    }
    rows: list[dict] = []
    for index in range(220):
        timestamp = start + timedelta(seconds=index * 3)
        service = rng.choice(services)
        level, status = "INFO", 200
        duration, message = max(15, int(rng.gauss(80, 25))), "transaction processed"
        if index > 60 and service in {"payments", "checkout", "gateway"}:
            level = rng.choice(["WARN", "ERROR", "ERROR"])
            status = rng.choice([429, 502, 503, 504])
            duration = rng.randint(400, 2500)
            message = rng.choice([
                "bank API 503 service unavailable",
                "payment authorization upstream timeout",
                "rate limit exceeded too many requests",
                "circuit breaker opened after dependency failures",
            ])
        rows.append({
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "level": level,
            "service": service,
            "message": message,
            "request_id": _request_id(3000, index),
            "trace_id": _trace_id(900, index // 2),
            "host": f"{service}-{1 + index % 4}",
            "dependency": dependency[service],
            "duration_ms": duration,
            "status_code": status,
        })
    return [("payment_cascade.jsonl", "\n".join(json.dumps(row) for row in rows))]


def _memory_storm(seed: int = 42) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    start = datetime(2026, 7, 27, 2, 0, tzinfo=timezone.utc)
    services = ["api", "worker", "search", "cache", "scheduler"]
    dependency = {
        "api": "search",
        "worker": "redis",
        "search": "elasticsearch",
        "cache": "redis",
        "scheduler": "worker",
    }
    lines: list[str] = []
    for index in range(240):
        timestamp = start + timedelta(seconds=index * 2)
        service = rng.choice(services)
        level, status, duration, message = "INFO", 200, rng.randint(30, 160), "operation completed"
        if index > 100 and service in {"worker", "search"}:
            level = rng.choice(["WARN", "ERROR", "CRITICAL"])
            status, duration = 500, rng.randint(700, 3500)
            message = rng.choice([
                "OutOfMemory heap space resource exhausted",
                "cannot allocate memory killed process",
                "GC overhead limit exceeded queue backlog",
                "worker restart after memory pressure",
            ])
        lines.append(
            f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} {level} [{service}] {message} "
            f"service={service} dependency={dependency[service]} request_id={_request_id(6000, index)} "
            f"trace_id={_trace_id(1900, index // 4)} host=node-{1 + index % 5} "
            f"duration_ms={duration} status={status}"
        )
    return [("memory_storm.log", "\n".join(lines))]


def _auth_attack(seed: int = 42) -> list[tuple[str, str]]:
    rng = random.Random(seed)
    start = datetime(2026, 7, 27, 2, 0, tzinfo=timezone.utc)
    services = ["auth", "gateway", "profile", "admin-api"]
    dependency = {
        "auth": "identity-provider",
        "gateway": "auth",
        "profile": "postgres",
        "admin-api": "auth",
    }
    rows: list[dict] = []
    for index in range(260):
        timestamp = start + timedelta(seconds=index)
        service = rng.choice(services)
        level, status, duration, message = "INFO", 200, rng.randint(20, 140), "request accepted"
        if index > 40 and service in {"auth", "gateway", "admin-api"} and rng.random() < 0.72:
            level = rng.choice(["WARN", "ERROR"])
            status = rng.choice([401, 403, 429])
            duration = rng.randint(90, 450)
            message = rng.choice([
                "invalid token authentication failed",
                "unauthorized access denied",
                "rate limit triggered suspicious client",
                "JWT signature verification failed",
            ])
        rows.append({
            "timestamp": timestamp.isoformat().replace("+00:00", "Z"),
            "level": level,
            "service": service,
            "message": message,
            "request_id": _request_id(9000, index),
            "trace_id": _trace_id(3000, index // 3),
            "host": f"edge-{1 + index % 3}",
            "dependency": dependency[service],
            "duration_ms": duration,
            "status_code": status,
        })
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return [("auth_attack.csv", output.getvalue())]


_BUILDERS = {
    "Database Meltdown": _database_meltdown,
    "Payment Cascade": _payment_cascade,
    "Memory Storm": _memory_storm,
    "Auth Attack": _auth_attack,
}


def build_scenario(name: str) -> list[tuple[str, str]]:
    if name not in _BUILDERS:
        raise KeyError(f"Unknown scenario: {name}")
    return _BUILDERS[name]()


def architecture_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#071021"/><stop offset="1" stop-color="#02050c"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<rect width="1200" height="680" rx="36" fill="url(#bg)"/><g opacity=".18" stroke="#5a87ff"><path d="M0 90H1200M0 180H1200M0 270H1200M0 360H1200M0 450H1200M0 540H1200M0 630H1200"/><path d="M100 0V680M200 0V680M300 0V680M400 0V680M500 0V680M600 0V680M700 0V680M800 0V680M900 0V680M1000 0V680M1100 0V680"/></g>
<text x="70" y="90" fill="#f7f9ff" font-size="42" font-family="Arial" font-weight="700">IncidentCommander AI</text><text x="70" y="130" fill="#9aa9c7" font-size="20" font-family="Arial">Autonomous incident intelligence workspace</text>
<g filter="url(#glow)"><circle cx="600" cy="350" r="92" fill="#0e2447" stroke="#39dcff" stroke-width="3"/><circle cx="600" cy="350" r="136" fill="none" stroke="#a06dff" stroke-width="2" stroke-dasharray="14 10"/><circle cx="600" cy="350" r="184" fill="none" stroke="#5a87ff" stroke-width="2" stroke-dasharray="4 13"/><text x="600" y="365" text-anchor="middle" fill="#f7f9ff" font-size="34" font-family="Arial" font-weight="700">AI CORE</text></g>
<g font-family="Arial" font-size="18"><g><rect x="90" y="250" width="240" height="110" rx="22" fill="#0a1630" stroke="#5a87ff"/><text x="120" y="295" fill="#39dcff">LOG INGESTION</text><text x="120" y="330" fill="#dbe7ff">Text · JSONL · CSV</text></g><g><rect x="870" y="210" width="240" height="110" rx="22" fill="#0a1630" stroke="#a06dff"/><text x="900" y="255" fill="#cbb8ff">ANOMALY AI</text><text x="900" y="290" fill="#dbe7ff">TF-IDF · K-Means · IF</text></g><g><rect x="865" y="430" width="245" height="110" rx="22" fill="#0a1630" stroke="#ff6476"/><text x="895" y="475" fill="#ff9daa">ROOT CAUSE</text><text x="895" y="510" fill="#dbe7ff">Evidence · Confidence</text></g><g><rect x="90" y="445" width="250" height="110" rx="22" fill="#0a1630" stroke="#45e8aa"/><text x="120" y="490" fill="#80f1bf">RESPONSE PLAN</text><text x="120" y="525" fill="#dbe7ff">Runbooks · Reports</text></g></g>
<g stroke-width="3" fill="none"><path d="M330 305C430 305 455 330 505 340" stroke="#5a87ff"/><path d="M695 320C770 290 800 265 870 265" stroke="#a06dff"/><path d="M700 390C775 430 810 475 865 485" stroke="#ff6476"/><path d="M505 405C430 445 400 495 340 500" stroke="#45e8aa"/></g></svg>"""


def service_map_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#081226"/><stop offset="1" stop-color="#02050c"/></linearGradient></defs><rect width="1200" height="680" rx="36" fill="url(#g)"/><text x="70" y="85" fill="#fff" font-size="40" font-family="Arial" font-weight="700">Service Impact Map</text><text x="70" y="125" fill="#9aa9c7" font-size="20" font-family="Arial">Visualize blast radius before taking action</text><g font-family="Arial" font-weight="700" text-anchor="middle"><g><circle cx="595" cy="340" r="88" fill="#172a50" stroke="#ff6476" stroke-width="4"/><text x="595" y="333" fill="#fff" font-size="25">ORDERS</text><text x="595" y="365" fill="#ff9daa" font-size="18">92% IMPACT</text></g><g><circle cx="280" cy="235" r="70" fill="#10203f" stroke="#39dcff" stroke-width="3"/><text x="280" y="242" fill="#fff" font-size="22">GATEWAY</text></g><g><circle cx="925" cy="230" r="72" fill="#10203f" stroke="#a06dff" stroke-width="3"/><text x="925" y="237" fill="#fff" font-size="22">PAYMENTS</text></g><g><circle cx="910" cy="500" r="66" fill="#10203f" stroke="#ffd166" stroke-width="3"/><text x="910" y="507" fill="#fff" font-size="20">POSTGRES</text></g><g><circle cx="255" cy="505" r="66" fill="#10203f" stroke="#45e8aa" stroke-width="3"/><text x="255" y="512" fill="#fff" font-size="20">INVENTORY</text></g></g><g fill="none" stroke-width="5" opacity=".75"><path d="M345 260C440 285 470 305 510 330" stroke="#39dcff"/><path d="M680 315C760 270 815 245 853 240" stroke="#a06dff"/><path d="M663 405C760 450 815 480 845 490" stroke="#ff6476"/><path d="M515 405C420 455 355 485 320 495" stroke="#45e8aa"/></g></svg>"""


def timeline_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" viewBox="0 0 1200 680"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#09152c"/><stop offset="1" stop-color="#03060d"/></linearGradient></defs><rect width="1200" height="680" rx="36" fill="url(#g)"/><text x="65" y="85" fill="#fff" font-size="40" font-family="Arial" font-weight="700">Incident Timeline Replay</text><text x="65" y="125" fill="#9aa9c7" font-size="20" font-family="Arial">From first anomaly to coordinated response</text><path d="M90 360H1110" stroke="#233960" stroke-width="8" stroke-linecap="round"/><g font-family="Arial" text-anchor="middle"><g><circle cx="170" cy="360" r="28" fill="#39dcff"/><text x="170" y="425" fill="#dbe7ff" font-size="18">Baseline</text><text x="170" y="455" fill="#9aa9c7" font-size="15">00:00</text></g><g><circle cx="410" cy="360" r="34" fill="#ffd166"/><text x="410" y="425" fill="#dbe7ff" font-size="18">Latency spike</text><text x="410" y="455" fill="#9aa9c7" font-size="15">02:40</text></g><g><circle cx="665" cy="360" r="42" fill="#ff6476"/><text x="665" y="425" fill="#dbe7ff" font-size="18">Cascade</text><text x="665" y="455" fill="#9aa9c7" font-size="15">04:10</text></g><g><circle cx="920" cy="360" r="34" fill="#a06dff"/><text x="920" y="425" fill="#dbe7ff" font-size="18">Root cause</text><text x="920" y="455" fill="#9aa9c7" font-size="15">05:20</text></g><g><circle cx="1080" cy="360" r="28" fill="#45e8aa"/><text x="1080" y="425" fill="#dbe7ff" font-size="18">Mitigation</text><text x="1080" y="455" fill="#9aa9c7" font-size="15">06:00</text></g></g></svg>"""
