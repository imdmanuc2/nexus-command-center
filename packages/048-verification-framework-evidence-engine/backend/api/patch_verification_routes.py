#!/usr/bin/env python3
"""Idempotently register Package 048 routes in the Nexus HTTP server."""
from pathlib import Path

SERVER = Path("backend/api/server.py")
IMPORT = "from backend.modules import platform_verifications\n"
GET_BEGIN = "        # PACKAGE-048-VERIFICATION-GET-BEGIN\n"
GET_END = "        # PACKAGE-048-VERIFICATION-GET-END\n"
POST_BEGIN = "        # PACKAGE-048-VERIFICATION-POST-BEGIN\n"
POST_END = "        # PACKAGE-048-VERIFICATION-POST-END\n"

GET_BLOCK = '''        # PACKAGE-048-VERIFICATION-GET-BEGIN
        if parsed.path == "/api/verifications/profiles":
            try:
                result = platform_verifications.profiles(query)
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path == "/api/verifications/runs":
            try:
                result = platform_verifications.runs(query)
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if parsed.path.startswith("/api/verifications/runs/"):
            run_id = parsed.path.rsplit("/", 1)[-1]
            try:
                result = platform_verifications.run_detail(run_id)
                status, payload = json_response(result)
            except LookupError as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 404)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
        # PACKAGE-048-VERIFICATION-GET-END

'''

POST_BLOCK = '''        # PACKAGE-048-VERIFICATION-POST-BEGIN
        verification_path = urlparse(self.path).path

        if verification_path == "/api/verifications/profiles":
            try:
                result = platform_verifications.create_profile(self._read_json_body())
                status, payload = json_response(result, 201)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if verification_path == "/api/verifications/run":
            try:
                result = platform_verifications.queue(self._read_json_body())
                status, payload = json_response(result, 202)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)

        if verification_path.startswith("/api/verifications/runs/") and verification_path.endswith("/retry"):
            run_id = verification_path.removeprefix("/api/verifications/runs/").removesuffix("/retry").strip("/")
            try:
                result = platform_verifications.retry(run_id)
                status, payload = json_response(result, 202)
            except LookupError as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 404)
            except Exception as exc:
                status, payload = json_response({"status": "error", "error": str(exc)}, 400)
            return self._send_json(payload, status)
        # PACKAGE-048-VERIFICATION-POST-END

'''


def insert_import(text: str) -> str:
    if IMPORT in text:
        return text
    anchors = (
        "from backend.modules import platform_change_rollback\n",
        "from backend.modules import platform_change_execution\n",
        "from backend.modules import platform_nodes\n",
    )
    for anchor in anchors:
        if anchor in text:
            return text.replace(anchor, anchor + IMPORT, 1)
    raise SystemExit("Could not locate Nexus platform module import section")


def insert_get(text: str) -> str:
    if GET_BEGIN in text and GET_END in text:
        return text
    anchor = "        query = parse_qs(parsed.query)\n\n"
    if anchor not in text:
        raise SystemExit("Could not locate Nexus GET query dispatch anchor")
    return text.replace(anchor, anchor + GET_BLOCK, 1)


def insert_post(text: str) -> str:
    if POST_BEGIN in text and POST_END in text:
        return text
    anchor = "    def do_POST(self):\n"
    if anchor not in text:
        raise SystemExit("Could not locate Nexus do_POST method")
    return text.replace(anchor, anchor + POST_BLOCK, 1)


def main() -> None:
    text = SERVER.read_text()
    text = insert_import(text)
    text = insert_get(text)
    text = insert_post(text)
    SERVER.write_text(text)
    print("Package 048 HTTP routes registered")


if __name__ == "__main__":
    main()
