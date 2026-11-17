"""Portable foreground supervisor; systemd is preferred on Ubuntu."""
import argparse,subprocess,sys,time
from pathlib import Path

def command(component,env_file):return [sys.executable,'-m','elevenbot','--env-file',str(Path(env_file).resolve()),component]

def main():
    p=argparse.ArgumentParser();p.add_argument('--env-file',default='.env');a=p.parse_args()
    from .config import Config
    try:
        cfg=Config.env(a.env_file)
        if not cfg.token:raise ValueError('Token missing')
    except Exception:print('Invalid configuration; run SETUP_SERVICE first. No settings changed.');raise SystemExit(1)
    processes={};failures={x:0 for x in ('bot','worker')};next_start={x:0 for x in failures}
    try:
        while True:
            for component in failures:
                process=processes.get(component)
                if process and process.poll() is not None:
                    failures[component]+=1;next_start[component]=time.monotonic()+5
                    processes.pop(component);print(component+' stopped; retry scheduled (no secrets logged).',flush=True)
                    if failures[component]>=5:raise RuntimeError('Repeated process failure; run doctor')
                if component not in processes and time.monotonic()>=next_start[component]:
                    processes[component]=subprocess.Popen(command(component,a.env_file))
                    print(component+' started.',flush=True)
            time.sleep(.5)
    except KeyboardInterrupt:print('Stopping service processes...')
    except RuntimeError:print('Service stopped after repeated errors. Run doctor; configuration and database are retained.');raise SystemExit(1)
    finally:
        for process in processes.values():
            if process.poll() is None:process.terminate()
        for process in processes.values():
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

if __name__=='__main__':main()
