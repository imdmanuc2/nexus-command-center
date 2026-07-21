#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import socket
import time
import uuid

from backend.db.repositories import change_execution_repository as repo
from backend.services.change_execution_service import run_once


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("NEXUS_CHANGE_WORKER_POLL_SECONDS","2")))
    parser.add_argument("--worker-id", default=os.getenv("NEXUS_CHANGE_WORKER_ID") or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}")
    args = parser.parse_args()

    running = True
    def stop(*_):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    repo.register_worker(args.worker_id, os.getpid(), {"mode":"once" if args.once else "daemon"})
    try:
        if args.once:
            print(run_once(args.worker_id))
            return
        while running:
            result = run_once(args.worker_id)
            if result.get("status") == "idle":
                time.sleep(args.poll_seconds)
    finally:
        repo.stop_worker(args.worker_id)


if __name__ == "__main__":
    main()
