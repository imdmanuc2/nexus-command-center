#!/usr/bin/env python3
from pathlib import Path

TARGETS = [
    Path('backend/db/repositories/platform_event_repository.py'),
    Path('backend/db/repositories/context_repository.py'),
]

HELPER = '''\ndef _json_safe(value):\n    """Convert database-native values into JSON-compatible values."""\n\n    if isinstance(value, Decimal):\n        return float(value)\n\n    if isinstance(value, (datetime, date)):\n        return value.isoformat()\n\n    if isinstance(value, dict):\n        return {str(key): _json_safe(item) for key, item in value.items()}\n\n    if isinstance(value, (list, tuple, set)):\n        return [_json_safe(item) for item in value]\n\n    return value\n'''

for path in TARGETS:
    text = path.read_text(encoding='utf-8')
    if 'from decimal import Decimal\n' not in text:
        anchor = 'from __future__ import annotations\n'
        if anchor not in text:
            raise SystemExit(f'Future import anchor missing in {path}')
        text = text.replace(
            anchor,
            anchor + '\nfrom datetime import date, datetime\nfrom decimal import Decimal\n',
            1,
        )
    if 'def _json_safe(value):' not in text:
        lines = text.splitlines()
        idx = next((i for i, line in enumerate(lines) if line.startswith('def ')), len(lines))
        lines.insert(idx, HELPER.strip() + '\n')
        text = '\n'.join(lines) + '\n'
    replacements = {
        'Jsonb(state_payload)': 'Jsonb(_json_safe(state_payload))',
        'Jsonb(previous_state or {})': 'Jsonb(_json_safe(previous_state or {}))',
        'Jsonb(current_state or {})': 'Jsonb(_json_safe(current_state or {}))',
        'Jsonb(context_payload)': 'Jsonb(_json_safe(context_payload))',
        'Jsonb(source_state)': 'Jsonb(_json_safe(source_state))',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    path.write_text(text, encoding='utf-8')
    print(f'JSON serialization hardened: {path}')
