#!/usr/bin/env python3
"""Run checks against an EXISTING workspace. No setup, reset, or guessed ports.
Default: doctor and status. --run-live-tests explicitly authorizes fixture writes,
permission revocation/restoration tests, and a 10-request then N-request benchmark.
Raw logs stay in ignored local-results/. Use export_evidence.py for reviewed copies.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, subprocess, sys, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--run-live-tests',action='store_true')
    p.add_argument('--requests',type=int,default=1000)
    p.add_argument('--workers',type=int,default=10)
    p.add_argument('--timeout',type=int,default=300,help='Post-submission confirmation timeout, not total runtime')
    args=p.parse_args();workspace=args.workspace.resolve()
    if not (workspace/'lab.json').is_file():
        p.error('Existing workspace/lab.json is missing; this tool will not create a chain')
    if not 1<=args.requests<=100000 or not 1<=args.workers<=128 or args.timeout<1:
        p.error('Use 1..100000 requests, 1..128 workers and a positive timeout')
    output=ROOT/'local-results'/(dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    output.mkdir(parents=True)
    commands=[['doctor'],['status']]
    if args.run_live_tests:
        commands += [['demo'],['security-tests'],
                     ['benchmark','--mode','ledger','--n','10','--workers','2','--timeout',str(args.timeout)],
                     ['benchmark','--mode','ledger','--n',str(args.requests),'--workers',str(args.workers),
                      '--payload-bytes','1024','--confirmations','1','--timeout',str(args.timeout)],['capture']]
    manifest={'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'live_tests_requested':args.run_live_tests,
              'lab_sha256':hashlib.sha256((ROOT/'lab.py').read_bytes()).hexdigest(),'commands':[]}
    for index,command in enumerate(commands,1):
        print(f'\n[{index}/{len(commands)}] '+' '.join(command),flush=True)
        stem=f'{index:02d}-{command[0]}'
        # Files prevent huge benchmark stdout from filling process memory.
        with (output/(stem+'.stdout.txt')).open('w',encoding='utf-8') as out, (output/(stem+'.stderr.txt')).open('w',encoding='utf-8') as err:
            try:
                run=subprocess.run([sys.executable,str(ROOT/'lab.py'),'--workspace',str(workspace),*command],
                                   stdout=out,stderr=err,cwd=ROOT,check=False)
                code=run.returncode
            except KeyboardInterrupt:
                print('Interrupted. Do not blindly retry writes; inspect the saved evidence.');return 130
        print((output/(stem+'.stdout.txt')).read_text(encoding='utf-8'))
        errors=(output/(stem+'.stderr.txt')).read_text(encoding='utf-8')
        if errors:print(errors,file=sys.stderr)
        manifest['commands'].append({'arguments':command,'exit_code':code,'stdout':stem+'.stdout.txt','stderr':stem+'.stderr.txt'})
        (output/'collection.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        if code:
            print('Stopped at first failure. Private logs:',output)
            print('For a stopped lab, run lab.py --workspace PATH start before collecting again.')
            return code if code>0 else 1
    print('Collection complete. Private logs:',output)
    print('Next: export_evidence.py --workspace YOUR_EXISTING_WORKSPACE, then review exports.')
    return 0
if __name__=='__main__':raise SystemExit(main())
