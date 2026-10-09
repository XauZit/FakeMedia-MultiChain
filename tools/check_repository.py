#!/usr/bin/env python3
"""Conservative publication guard, not a complete secret scanner.
Default scans source files excluding local runtime folders. --staged inspects the
actual staged Git blobs (not only working-tree files) before commit/push.
"""
from __future__ import annotations
import argparse,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRIVATE_NAMES={'lab.json','wallet.dat','multichain.conf','used_nonces.json','writer.lock','model.json'}
SKIP={'.git','.venv','venv','__pycache__','workspace','local-results','nodes'}
TEXT_EXT={'.py','.ps1','.md','.txt','.json','.jsonl','.yml','.yaml','.csv','.toml','.conf','.env'}

def check(path:str,raw:bytes)->list[str]:
    p=Path(path);issues=[]
    if p.name.lower() in PRIVATE_NAMES or p.suffix.lower() in {'.pem','.key','.p12','.pfx','.exe','.dll'}:
        issues.append(path+': private/runtime/binary file must not be published')
    if any(part.lower() in {'workspace','nodes','local-results'} for part in p.parts):
        issues.append(path+': runtime directory must not be tracked')
    if p.suffix.lower() in TEXT_EXT or p.name.startswith('.env'):
        text=raw.decode('utf-8',errors='replace')
        if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):
            issues.append(path+': private key header')
        if re.search(r'(?m)^\s*rpcpassword\s*=\s*[^\s#]+',text):
            issues.append(path+': literal RPC password configuration')
        if re.search(r'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[A-Z0-9]{16})\b',text):
            issues.append(path+': possible credential token')
    return issues

def main()->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--staged',action='store_true');args=p.parse_args()
    issues=[];count=0
    if args.staged:
        proc=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True)
        if proc.returncode:print('ERROR: Run git init and git add first.');return 1
        for name in proc.stdout.decode().split('\0'):
            if not name:continue
            blob=subprocess.run(['git','show',':'+name],cwd=ROOT,capture_output=True)
            if blob.returncode:issues.append(name+': unable to read staged content');continue
            issues+=check(name,blob.stdout);count+=1
    else:
        for path in ROOT.rglob('*'):
            relative=path.relative_to(ROOT)
            if any(x in SKIP for x in relative.parts) or not path.is_file():continue
            if path.is_symlink():issues.append(str(relative)+': review symlink before publishing');continue
            issues+=check(relative.as_posix(),path.read_bytes());count+=1
    print(json.dumps({'checked_files':count,'mode':'staged Git blobs' if args.staged else 'source tree',
                      'passed':not issues,'issues':issues,
                      'limit':'Not a guarantee. Manually review all screenshots, PDFs, content and staged files.'},indent=2))
    return 1 if issues else 0
if __name__=='__main__':raise SystemExit(main())
