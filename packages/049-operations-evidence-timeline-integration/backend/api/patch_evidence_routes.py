from pathlib import Path

IMPORT = 'from backend.modules import platform_evidence\n'
ANCHOR = 'from backend.modules import platform_change_rollback\n'
MARKER = '# Package 049: Operations Evidence & Timeline Integration'
BLOCK = '''        # Package 049: Operations Evidence & Timeline Integration
        _evidence_url = urlparse(self.path)
        _evidence_path = _evidence_url.path
        _evidence_query = parse_qs(_evidence_url.query)

        if _evidence_path == "/api/evidence":
            status, payload = json_response(platform_evidence.evidence(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path == "/api/evidence/status":
            status, payload = json_response(platform_evidence.status(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path == "/api/timeline/operations":
            status, payload = json_response(platform_evidence.timeline(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path == "/api/recommendations/context":
            status, payload = json_response(platform_evidence.recommendation_context(_evidence_query))
            return self._send_json(payload, status)

        if _evidence_path.startswith("/api/evidence/"):
            _evidence_id = _evidence_path.removeprefix("/api/evidence/").strip("/")
            if _evidence_id:
                result = platform_evidence.evidence_detail(_evidence_id)
                response_status = 404 if result.get("status") == "not-found" else 200
                status, payload = json_response(result, response_status)
                return self._send_json(payload, status)

        if _evidence_path.startswith("/api/assets/") and _evidence_path.endswith("/operations"):
            _asset_id = _evidence_path.removeprefix("/api/assets/").removesuffix("/operations").strip("/")
            if _asset_id:
                status, payload = json_response(platform_evidence.asset_operations(_asset_id, _evidence_query))
                return self._send_json(payload, status)

'''

def main():
    root = Path(__file__).resolve().parents[4]
    server = root / 'backend/api/server.py'
    text = server.read_text()
    original = text
    if IMPORT.strip() not in text:
        if ANCHOR not in text:
            raise SystemExit('Could not locate platform module import anchor')
        text = text.replace(ANCHOR, ANCHOR + IMPORT, 1)
    if MARKER not in text:
        anchor = '    def do_GET(self):\n'
        if anchor not in text:
            raise SystemExit('Could not locate NexusHandler.do_GET')
        text = text.replace(anchor, anchor + BLOCK, 1)
    if text != original:
        backup = server.with_suffix('.py.before-package-049')
        if not backup.exists():
            backup.write_text(original)
        server.write_text(text)
    print('Package 049 HTTP routes registered')

if __name__ == '__main__':
    main()
