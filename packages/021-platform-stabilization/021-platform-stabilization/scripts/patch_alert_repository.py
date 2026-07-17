#!/usr/bin/env python3
from pathlib import Path

path = Path('backend/db/repositories/alert_repository.py')
text = path.read_text(encoding='utf-8')

start = text.find('INSERT INTO nexus.alerts (')
if start == -1:
    raise SystemExit('Could not find nexus.alerts INSERT block.')
start = text.rfind('            cursor.execute(', 0, start)
end = text.find('    return "opened"', start)
if start == -1 or end == -1:
    raise SystemExit('Could not isolate alert INSERT block.')

replacement = '''            cursor.execute(
                """
                INSERT INTO nexus.alerts (
                    alert_id,
                    asset_id,
                    event_id,
                    alert_type,
                    severity,
                    status,
                    title,
                    message,
                    rule_id,
                    occurrence_count,
                    first_seen_at,
                    last_seen_at,
                    acknowledged_by,
                    data,
                    priority,
                    actionable,
                    grouping_key,
                    required_duration_sec,
                    recommended_action
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'open',
                    %s,
                    %s,
                    %s,
                    1,
                    NOW(),
                    NOW(),
                    '',
                    %s,
                    %s,
                    TRUE,
                    %s,
                    0,
                    %s
                )
                """,
                (
                    _alert_id(grouping_key),
                    None,
                    None,
                    rule_id,
                    severity,
                    title,
                    message,
                    rule_id,
                    Jsonb(alert_data),
                    priority,
                    grouping_key,
                    recommended_action,
                ),
            )

'''

text = text[:start] + replacement + text[end:]
path.write_text(text, encoding='utf-8')
print('Alert INSERT parameter alignment fixed.')
print('Platform event ID remains in alert JSON.')
print('Legacy nexus.events foreign key remains NULL.')
