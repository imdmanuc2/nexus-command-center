from __future__ import annotations
import os,socket,time
from backend.services.verification_service import run_once
def main():
    worker=os.getenv("NEXUS_VERIFICATION_WORKER_ID") or f"{socket.gethostname()}-verification"
    interval=max(1,int(os.getenv("NEXUS_VERIFICATION_POLL_SECONDS","3")))
    while True:
        try:
            if not run_once(worker): time.sleep(interval)
        except KeyboardInterrupt: return
        except Exception as exc:
            print(f"verification worker error: {exc}",flush=True); time.sleep(interval)
if __name__=="__main__": main()
