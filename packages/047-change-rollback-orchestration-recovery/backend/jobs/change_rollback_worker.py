import argparse,json,os,socket,time,uuid
from backend.services.change_rollback_service import run_once
def default_id(): return os.getenv('NEXUS_ROLLBACK_WORKER_ID',f"{socket.gethostname()}-rollback-{uuid.uuid4().hex[:8]}")
def main():
    p=argparse.ArgumentParser(); p.add_argument('--once',action='store_true'); p.add_argument('--worker-id',default=default_id()); p.add_argument('--poll-seconds',type=float,default=2.0); a=p.parse_args()
    if a.once: print(json.dumps(run_once(a.worker_id),default=str)); return
    while True:
        try:
            r=run_once(a.worker_id)
            if r.get('status')!='idle': print(json.dumps(r,default=str),flush=True)
        except Exception as e: print(json.dumps({'status':'error','error':str(e)}),flush=True)
        time.sleep(max(1.0,a.poll_seconds))
if __name__=='__main__': main()
