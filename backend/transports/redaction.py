from __future__ import annotations

import re
from typing import Iterable

_DEFAULT_PATTERNS = [
    re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key)\s*[=:]\s*([^\s]+)"),
    re.compile(r"(?i)(rpcpassword\s*=\s*)([^\s]+)"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)([^\s]+)"),
]


def redact_text(value: str, secrets: Iterable[str] = ()) -> str:
    text = value or ""
    for secret in secrets:
        if secret:
            text = text.replace(str(secret), "[REDACTED]")
    for pattern in _DEFAULT_PATTERNS:
        text = pattern.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    return text
