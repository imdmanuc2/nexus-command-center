#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "backend/api/server.py"

IMPORT_LINE = "from backend.modules import platform_change_rollback\n"

GET_BLOCK = '''        # BEGIN PACKAGE 047 CHANGE ROLLBACK GET ROUTES
        if parsed.path == "/api/change-rollbacks/status":
            try:
                status, payload = json_response(platform_change_rollback.status(query))
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)

        if parsed.path == "/api/change-rollbacks/history":
            try:
                status, payload = json_response(platform_change_rollback.history(query))
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)
        # END PACKAGE 047 CHANGE ROLLBACK GET ROUTES

'''

POST_BLOCK = '''        # BEGIN PACKAGE 047 CHANGE ROLLBACK POST ROUTES
        if parsed.path == "/api/change-rollbacks":
            try:
                status, payload = json_response(
                    platform_change_rollback.create(self._read_json_body()), 201
                )
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)

        if parsed.path == "/api/change-rollbacks/approve":
            try:
                status, payload = json_response(
                    platform_change_rollback.approve(self._read_json_body())
                )
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)

        if parsed.path == "/api/change-rollbacks/queue":
            try:
                status, payload = json_response(
                    platform_change_rollback.queue(self._read_json_body())
                )
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)
        # END PACKAGE 047 CHANGE ROLLBACK POST ROUTES

'''


def parse_functions(text: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(text, filename=str(SERVER))
    found: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in {"do_GET", "do_POST"}:
            found[node.name] = node
    return found


def insert_before_final_statement(text: str, function: ast.FunctionDef, block: str) -> str:
    if not function.body:
        raise RuntimeError(f"{function.name} has no body")
    lines = text.splitlines(keepends=True)
    insert_index = function.body[-1].lineno - 1
    lines.insert(insert_index, block)
    return "".join(lines)


def verify(text: str) -> None:
    required = [
        "from backend.modules import platform_change_rollback",
        'parsed.path == "/api/change-rollbacks/status"',
        'parsed.path == "/api/change-rollbacks/history"',
        'parsed.path == "/api/change-rollbacks"',
        'parsed.path == "/api/change-rollbacks/approve"',
        'parsed.path == "/api/change-rollbacks/queue"',
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("Route installation verification failed: " + ", ".join(missing))
    ast.parse(text, filename=str(SERVER))


def main() -> None:
    text = SERVER.read_text()

    if IMPORT_LINE.strip() not in text:
        functions = parse_functions(text)
        first_route_line = min(node.lineno for node in functions.values())
        lines = text.splitlines(keepends=True)
        import_indexes = [
            i for i, line in enumerate(lines[: first_route_line - 1])
            if line.startswith("from ") or line.startswith("import ")
        ]
        if not import_indexes:
            raise RuntimeError("No import section found in server.py")
        lines.insert(import_indexes[-1] + 1, IMPORT_LINE)
        text = "".join(lines)

    if "BEGIN PACKAGE 047 CHANGE ROLLBACK GET ROUTES" not in text:
        functions = parse_functions(text)
        if "do_GET" not in functions:
            raise RuntimeError("Unable to locate do_GET in server.py")
        text = insert_before_final_statement(text, functions["do_GET"], GET_BLOCK)

    if "BEGIN PACKAGE 047 CHANGE ROLLBACK POST ROUTES" not in text:
        functions = parse_functions(text)
        if "do_POST" not in functions:
            raise RuntimeError("Unable to locate do_POST in server.py")
        text = insert_before_final_statement(text, functions["do_POST"], POST_BLOCK)

    verify(text)
    SERVER.write_text(text)
    verify(SERVER.read_text())
    print("server.py rollback routes installed and verified")


if __name__ == "__main__":
    main()
