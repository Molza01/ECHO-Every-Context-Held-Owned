"""Privacy redaction — runs BEFORE anything is written to Supermemory or shown to an AI.

Removes secrets/credentials from any captured or derived text. This is defense-in-depth:
applied at ingestion (so secrets never reach Supermemory) and again on passport/answer
output (so they never reach an AI tool).
"""
from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_\-]{16,}\b"), "[redacted-key]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"), "[redacted-token]"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"), "[redacted-token]"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"), "[redacted-token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[redacted-aws-key]"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "[redacted-jwt]"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[redacted-private-key]"),
    (re.compile(r"(?i)\b(pass(word|wd)?|secret|api[_-]?key|token|authorization|bearer)\b\s*[:=]\s*\S+"),
     lambda m: f"{m.group(1)}=[redacted]"),  # type: ignore[arg-type]
    (re.compile(r"\b[A-Za-z][A-Za-z0-9+.\-]*://[^\s:@/]+:[^\s:@/]+@"), "[redacted-credentials]@"),  # user:pass@host
]


def redact(text: str | None) -> str:
    if not text:
        return text or ""
    out = text
    for pat, repl in _PATTERNS:
        out = pat.sub(repl, out)  # type: ignore[arg-type]
    return out


def redact_dict(d: dict) -> dict:
    """Redact string values in a shallow dict (metadata)."""
    return {k: (redact(v) if isinstance(v, str) else v) for k, v in d.items()}
