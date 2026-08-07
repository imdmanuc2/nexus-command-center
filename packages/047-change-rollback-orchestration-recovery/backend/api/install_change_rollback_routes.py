#!/usr/bin/env python3
from pathlib import Path
path=Path(__file__).resolve().parents[3]/'backend/api/server.py'; text=path.read_text()
anchor='from backend.modules import platform_change_execution\n'; line='from backend.modules import platform_change_rollback\n'
if line not in text:
    if anchor not in text: raise SystemExit('Missing platform_change_execution import anchor')
    text=text.replace(anchor,anchor+line,1)
get_block="""        if parsed.path == \"/api/change-rollbacks/status\":\n            try: status, payload = json_response(platform_change_rollback.status(query))\n            except Exception as exc: status, payload = json_response({\"status\":\"error\",\"error\":str(exc)}, 400)\n            return self._send_json(payload, status)\n\n        if parsed.path == \"/api/change-rollbacks/history\":\n            try: status, payload = json_response(platform_change_rollback.history(query))\n            except Exception as exc: status, payload = json_response({\"status\":\"error\",\"error\":str(exc)}, 400)\n            return self._send_json(payload, status)\n\n"""
get_anchor='        if parsed.path == "/api/change-execution/status":\n'
if get_block not in text:
    if get_anchor not in text: raise SystemExit('Missing change execution GET anchor')
    text=text.replace(get_anchor,get_block+get_anchor,1)
post_block="""        if parsed.path == \"/api/change-rollbacks\":\n            try: status, payload = json_response(platform_change_rollback.create(self._read_json_body()), 201)\n            except Exception as exc: status, payload = json_response({\"status\":\"error\",\"error\":str(exc)}, 400)\n            return self._send_json(payload, status)\n\n        if parsed.path == \"/api/change-rollbacks/approve\":\n            try: status, payload = json_response(platform_change_rollback.approve(self._read_json_body()))\n            except Exception as exc: status, payload = json_response({\"status\":\"error\",\"error\":str(exc)}, 400)\n            return self._send_json(payload, status)\n\n        if parsed.path == \"/api/change-rollbacks/queue\":\n            try: status, payload = json_response(platform_change_rollback.queue(self._read_json_body()))\n            except Exception as exc: status, payload = json_response({\"status\":\"error\",\"error\":str(exc)}, 400)\n            return self._send_json(payload, status)\n\n"""
post_anchor='        if parsed.path == "/api/changes":\n'
if post_block not in text:
    if post_anchor not in text: raise SystemExit('Missing change management POST anchor')
    text=text.replace(post_anchor,post_block+post_anchor,1)
path.write_text(text); print('server.py rollback routes installed')
