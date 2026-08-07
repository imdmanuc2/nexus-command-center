#!/usr/bin/env python3
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend/api/server.py"
IMPORT_LINE = "from backend.modules import platform_change_rollback\n"

GET_ROUTE_LINES = [
    '    "/api/change-rollbacks/status": platform_change_rollback.status,\n',
    '    "/api/change-rollbacks/history": platform_change_rollback.history,\n',
]

POST_BLOCK = '''        # BEGIN PACKAGE 047 CHANGE ROLLBACK POST ROUTES
        if parsed.path == "/api/change-rollbacks":
            try:
                result = platform_change_rollback.create(self._read_json_body())
                status, payload = json_response(result, 201)
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)

        if parsed.path == "/api/change-rollbacks/approve":
            try:
                result = platform_change_rollback.approve(self._read_json_body())
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)

        if parsed.path == "/api/change-rollbacks/queue":
            try:
                result = platform_change_rollback.queue(self._read_json_body())
                status, payload = json_response(result)
            except Exception as exc:
                status, payload = json_response(
                    {"status": "error", "error": str(exc)}, 400
                )
            return self._send_json(payload, status)
        # END PACKAGE 047 CHANGE ROLLBACK POST ROUTES

'''


def parse(text: str) -> ast.Module:
    return ast.parse(text, filename=str(SERVER))


def find_function(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise RuntimeError(f"Unable to locate {name} in {SERVER}")


def find_routes_dict(tree: ast.Module) -> ast.Dict:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        if not isinstance(node.value, ast.Dict):
            continue

        names = []
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node.target, ast.Name):
            names.append(node.target.id)

        if "routes" in names:
            return node.value

    raise RuntimeError("Unable to locate the global routes dictionary")


def add_import(text: str) -> str:
    if IMPORT_LINE.strip() in text:
        return text

    tree = parse(text)
    imports = [
        node for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    if not imports:
        raise RuntimeError("Unable to locate server.py import section")

    lines = text.splitlines(keepends=True)
    lines.insert(imports[-1].end_lineno, IMPORT_LINE)
    return "".join(lines)


def add_get_routes(text: str) -> str:
    if all(line.strip() in text for line in GET_ROUTE_LINES):
        return text

    routes_dict = find_routes_dict(parse(text))
    if routes_dict.end_lineno is None:
        raise RuntimeError("routes dictionary has no end location")

    lines = text.splitlines(keepends=True)
    close_index = routes_dict.end_lineno - 1
    if lines[close_index].strip() != "}":
        raise RuntimeError(
            "The routes dictionary closing brace is not on its own line"
        )

    additions = [line for line in GET_ROUTE_LINES if line.strip() not in text]
    lines[close_index:close_index] = additions
    return "".join(lines)


def add_post_dispatch(text: str) -> str:
    if "BEGIN PACKAGE 047 CHANGE ROLLBACK POST ROUTES" in text:
        return text

    function = find_function(parse(text), "do_POST")
    parsed_assignment = None

    for statement in function.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if any(
            isinstance(target, ast.Name) and target.id == "parsed"
            for target in targets
        ):
            parsed_assignment = statement
            break

    if parsed_assignment is None or parsed_assignment.end_lineno is None:
        raise RuntimeError(
            "Unable to locate `parsed = urlparse(self.path)` in do_POST"
        )

    lines = text.splitlines(keepends=True)
    lines.insert(parsed_assignment.end_lineno, "\n" + POST_BLOCK)
    return "".join(lines)


def verify(text: str) -> None:
    required = [
        "from backend.modules import platform_change_rollback",
        '"/api/change-rollbacks/status": platform_change_rollback.status',
        '"/api/change-rollbacks/history": platform_change_rollback.history',
        'parsed.path == "/api/change-rollbacks"',
        'parsed.path == "/api/change-rollbacks/approve"',
        'parsed.path == "/api/change-rollbacks/queue"',
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(
            "Rollback route verification failed: " + ", ".join(missing)
        )
    parse(text)


def main() -> None:
    if not SERVER.is_file():
        raise RuntimeError(f"Nexus API server not found: {SERVER}")

    text = SERVER.read_text()
    text = add_import(text)
    text = add_get_routes(text)
    text = add_post_dispatch(text)
    verify(text)

    SERVER.write_text(text)
    verify(SERVER.read_text())

    print(f"Patched and verified live API file: {SERVER}")
    print("Package 047 rollback routes registered")


if __name__ == "__main__":
    main()
