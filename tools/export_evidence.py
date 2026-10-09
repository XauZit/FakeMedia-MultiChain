#!/usr/bin/env python3
"""Export an allowlisted, path-redacted copy of lab evidence. Never export wallets.

Run from any directory: python tools/export_evidence.py --workspace PATH
Review exports manually before committing; no scanner guarantees secret detection.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = {'doctor.json', 'status.json', 'demo.json', 'security_tests.json',
             'model_evaluation.json', 'blockchain_parameters.json'}
RUN_FILES = {'summary.json', 'requests.csv', 'requests.jsonl'}
DENIED_KEYS = {'rpcpassword', 'rpcuser', 'password', 'private_key', 'privatekey',
               'secret', 'access_token', 'api_key', 'authorization'}

def scrub_text(text: str, workspace: Path) -> str:
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text):
        raise ValueError('Private-key material detected; evidence export refused')
    text = text.replace(str(workspace), '<WORKSPACE>')
    text = re.sub(r'[A-Za-z]:\\Users\\[^\\\s"\n]+', '<USER_HOME>', text)
    text = re.sub(r'/home/[^/\s"\n]+', '<USER_HOME>', text)
    return text

def scrub(value, workspace: Path):
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key.lower() in DENIED_KEYS:
                raise ValueError('Sensitive credential key in evidence; export refused: ' + key)
            out[key] = '<WORKSPACE>' if key == 'workspace' else scrub(item, workspace)
        return out
    if isinstance(value, list): return [scrub(x, workspace) for x in value]
    return scrub_text(value, workspace) if isinstance(value, str) else value

def permitted(relative: Path) -> bool:
    if len(relative.parts) == 1:
        return (relative.name in TOP_LEVEL or
                bool(re.fullmatch(r'demo-[0-9a-f]+-(?:real|fake|disagreement)\.json', relative.name)) or
                bool(re.fullmatch(r'reconcile-(?:ledger|pipeline)-[A-Za-z0-9_.-]+\.json', relative.name)))
    return (len(relative.parts) == 2 and
            bool(re.fullmatch(r'(?:ledger|pipeline)-[A-Za-z0-9_.-]+', relative.parts[0])) and
            relative.name in RUN_FILES)

def export(workspace: Path, destination: Path) -> dict:
    workspace = workspace.resolve()
    source = workspace / 'evidence'
    if not (workspace / 'lab.json').is_file() or not source.is_dir():
        raise ValueError('Expected an existing lab workspace with lab.json and evidence/')
    destination = destination.resolve()
    if destination == workspace or workspace in destination.parents:
        raise ValueError('Export destination must be outside the private workspace')
    if destination.exists():
        raise ValueError('Destination already exists. Choose a new output directory.')
    prepared = []
    for path in sorted(source.rglob('*')):
        if not path.is_file(): continue
        relative = path.relative_to(source)
        if not permitted(relative): continue
        if path.is_symlink() or source.resolve() not in path.resolve().parents:
            raise ValueError('Refusing evidence symlink or escaped path: ' + str(relative))
        raw = path.read_bytes()
        if len(raw) > 100_000_000:
            raise ValueError('Evidence file exceeds 100 MB: ' + str(relative))
        text = raw.decode('utf-8-sig')
        if path.suffix == '.json':
            payload = json.dumps(scrub(json.loads(text), workspace), indent=2, ensure_ascii=False) + '\n'
        elif path.suffix == '.jsonl':
            payload = ''.join(json.dumps(scrub(json.loads(line), workspace), ensure_ascii=False) + '\n'
                              for line in text.splitlines() if line.strip())
        else:
            reader = csv.DictReader(io.StringIO(text))
            expected = {'sequence','request_id','status','queue_ms','service_ms','burst_response_ms','txids','error'}
            if set(reader.fieldnames or ()) != expected:
                raise ValueError('Unexpected benchmark CSV columns: ' + str(relative))
            buffer = io.StringIO(newline='')
            writer = csv.DictWriter(buffer, fieldnames=reader.fieldnames)
            writer.writeheader()
            for row in reader: writer.writerow(scrub(row, workspace))
            payload = buffer.getvalue()
        prepared.append((relative, raw, payload.encode('utf-8')))
    if not prepared: raise ValueError('No allowlisted evidence files found')
    destination.mkdir(parents=True)
    files = []
    for relative, original, cleaned in prepared:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(cleaned)
        files.append({'path':relative.as_posix(), 'original_sha256':hashlib.sha256(original).hexdigest(),
                      'exported_sha256':hashlib.sha256(cleaned).hexdigest()})
    manifest = {'exported_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'files':files,
                'note':'Allowlisted evidence only; private workspace not copied. Paths may be redacted. '
                       'Original on-chain summary hashes refer to original files, not reformatted exports. '
                       'Review text and any manually added screenshots before publishing.',
                'not_exported':['lab.json','multichain.conf','wallets','used_nonces.json','model.json',
                                'params.dat','summary_anchor.json','startup logs']}
    (destination/'EXPORT_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return {'destination':str(destination),'files_exported':len(files)}

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    target=args.out or ROOT/'evidence'/'runs'/dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    try:
        print(json.dumps(export(args.workspace,target),indent=2));return 0
    except (OSError,ValueError) as exc:
        print('ERROR:',exc);return 1
if __name__=='__main__':raise SystemExit(main())
