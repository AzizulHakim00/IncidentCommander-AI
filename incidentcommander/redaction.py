from __future__ import annotations

import re

PATTERNS = {
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    "jwt": re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"),
    "api_key": re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\s*[=:]\s*[\"']?([^\s,;\"']{6,})"),
    "credit_card_like": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
}


def audit_sensitive_text(text: str) -> dict[str, int]:
    return {name: len(pattern.findall(text)) for name, pattern in PATTERNS.items()}


def redact_text(text: str) -> str:
    redacted = text
    redacted = PATTERNS["email"].sub("[REDACTED_EMAIL]", redacted)
    redacted = PATTERNS["jwt"].sub("[REDACTED_JWT]", redacted)
    redacted = PATTERNS["api_key"].sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED_SECRET]"), redacted)
    redacted = PATTERNS["credit_card_like"].sub("[REDACTED_NUMBER]", redacted)
    return redacted
