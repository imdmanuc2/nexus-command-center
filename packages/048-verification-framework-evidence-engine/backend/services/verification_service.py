from __future__ import annotations

import re
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

from backend.capabilities.registry import get_capability_registry
from backend.db.repositories import verification_repository as repo


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _run_local_capability(argv: list[str], timeout_seconds: int) -> dict:
    """Execute an allow-listed capability locally using the existing registry argv."""
    start = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "exitCode": completed.returncode,
            "timedOut": False,
            "durationMs": _ms(start),
            "transport": "local",
            "argv": argv,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "exitCode": None,
            "timedOut": True,
            "durationMs": _ms(start),
            "transport": "local",
            "argv": argv,
        }


def capability(run, step):
    cfg = step.get("configuration") or {}
    capability_id = str(cfg.get("capability") or "")
    parameters = dict(run.get("parameters") or {})
    registry = get_capability_registry()
    capability_definition = registry.resolve(capability_id)
    registry.validate_parameters(capability_definition, parameters)

    argv = (
        capability_definition.verify_argv(parameters)
        if capability_definition.verify_argv
        else capability_definition.build_argv(parameters)
    )
    argv = [str(value) for value in argv]

    transport = str(run.get("transport") or "local")
    if transport != "local":
        raise ValueError(
            "Package 048 currently executes capability verification through the "
            "existing allow-listed registry on the local Nexus host. Remote verification "
            "must be submitted through the Change Execution worker and linked to this run."
        )

    result = _run_local_capability(
        argv,
        int(step.get("timeout_seconds") or capability_definition.timeout_seconds),
    )
    expected = int((step.get("expected") or {}).get("exitCode", 0))
    passed = result.get("exitCode") == expected and not result.get("timedOut")
    return passed, {
        **result,
        "evidenceType": "capability",
        "capability": capability_id,
    }


def tcp(run, step):
    start = time.monotonic()
    cfg = step.get("configuration") or {}
    host = str(cfg.get("host") or run["target_id"])
    port = int(cfg["port"])
    try:
        with socket.create_connection(
            (host, port), timeout=int(step.get("timeout_seconds") or 10)
        ):
            pass
        return True, {
            "evidenceType": "tcp",
            "host": host,
            "port": port,
            "connected": True,
            "durationMs": _ms(start),
        }
    except Exception as exc:
        return False, {
            "evidenceType": "tcp",
            "host": host,
            "port": port,
            "connected": False,
            "error": str(exc),
            "durationMs": _ms(start),
        }


def http(run, step):
    start = time.monotonic()
    cfg = step.get("configuration") or {}
    url = str(cfg["url"])
    expected = int((step.get("expected") or {}).get("status", 200))
    try:
        request = urllib.request.Request(
            url=url, method=str(cfg.get("method") or "GET").upper()
        )
        with urllib.request.urlopen(
            request, timeout=int(step.get("timeout_seconds") or 20)
        ) as response:
            body = response.read(65536).decode("utf-8", errors="replace")
            result = {
                "evidenceType": "http",
                "url": url,
                "status": response.status,
                "body": body,
                "durationMs": _ms(start),
            }
            return response.status == expected, result
    except Exception as exc:
        return False, {
            "evidenceType": "http",
            "url": url,
            "error": str(exc),
            "durationMs": _ms(start),
        }


def file_exists(run, step):
    start = time.monotonic()
    path = Path(str((step.get("configuration") or {})["path"]))
    exists = path.exists()
    return exists, {
        "evidenceType": "file",
        "path": str(path),
        "exists": exists,
        "isFile": path.is_file(),
        "isDirectory": path.is_dir(),
        "durationMs": _ms(start),
    }


def regex(run, step):
    start = time.monotonic()
    cfg = step.get("configuration") or {}
    value = str(cfg.get("value") or "")
    pattern = str(cfg["pattern"])
    matched = re.search(pattern, value) is not None
    return matched, {
        "evidenceType": "regex",
        "pattern": pattern,
        "value": value,
        "matched": matched,
        "durationMs": _ms(start),
    }


VERIFIERS = {
    "capability": capability,
    "tcp": tcp,
    "http": http,
    "https": http,
    "file-exists": file_exists,
    "regex": regex,
}


def execute(run):
    items = repo.steps(run["run_id"])
    total = sum(float(step.get("weight") or 1) for step in items) or 1
    passed_weight = 0.0
    required_failure = False
    results = []

    for step in items:
        repo.start_step(step["step_run_id"])
        try:
            verifier = VERIFIERS.get(str(step["verifier_type"]))
            if verifier is None:
                raise ValueError(
                    f"Unsupported verifier type: {step['verifier_type']}"
                )
            passed, result = verifier(run, step)
            error = "" if passed else f"{step['name']} failed."
        except Exception as exc:
            passed = False
            error = str(exc)
            result = {
                "evidenceType": str(step["verifier_type"]),
                "error": error,
                "durationMs": 0,
            }

        repo.finish_step(step["step_run_id"], passed, result, error)
        if passed:
            passed_weight += float(step.get("weight") or 1)
        elif bool(step.get("required", True)):
            required_failure = True

        results.append(
            {
                "stepRunId": str(step["step_run_id"]),
                "name": step["name"],
                "status": "passed" if passed else "failed",
                "required": bool(step.get("required", True)),
            }
        )

    score = round(passed_weight / total * 100, 2)
    profile = next(
        (
            item
            for item in repo.profiles()
            if str(item["profile_id"]) == str(run["profile_id"])
        ),
        {},
    )
    minimum = float(profile.get("minimum_score") or 100)
    passed = not required_failure and score >= minimum
    summary = {
        "profileKey": run["profile_key"],
        "score": score,
        "minimumScore": minimum,
        "requiredFailure": required_failure,
        "rollbackRecommended": bool(
            not passed and profile.get("rollback_on_failure")
        ),
        "steps": results,
    }
    repo.finish_run(
        run,
        passed,
        score,
        summary,
        "" if passed else "Verification profile did not meet its acceptance policy.",
    )
    return summary


def run_once(worker_id="verification-worker"):
    repo.reconcile()
    run = repo.claim(worker_id)
    if not run:
        return None
    execute(run)
    return str(run["run_id"])
