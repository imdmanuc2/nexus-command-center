import os
import signal
import time
from backend.services.operation_evidence_service import aggregate_once

running = True

def stop(_signum, _frame):
    global running
    running = False

def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    interval = max(5, int(os.getenv('NEXUS_EVIDENCE_INTERVAL_SECONDS', '30')))
    while running:
        try:
            aggregate_once()
        except Exception as exc:
            print(f'operation evidence aggregation failed: {exc}', flush=True)
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

if __name__ == '__main__':
    main()
