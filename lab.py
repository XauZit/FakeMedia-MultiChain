#!/usr/bin/env python3
"""FakeMedia MultiChain exam lab. Python 3.10+, standard library only.

Real chain operations use MultiChain Community JSON-RPC; nothing simulates a
blockchain. The small NLP/tabular-Q model and its labelled corpus are teaching
substitutions, NOT the paper's deep reinforcement learning implementation.
Run: python lab.py --help
"""
from __future__ import annotations

import argparse
import base64
import collections
import concurrent.futures as cf
import contextlib
import csv
import datetime as dt
import hashlib
import html
import http.client
import json
import math
import os
import platform
import random
import re
import secrets
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

VERSION = '2.0.2-mining-check'
HERE = Path(__file__).resolve().parent
ROLES = ('authority', 'publisher', 'validator1', 'validator2', 'auditor')
VALIDATORS = ('validator1', 'validator2')
STREAMS = ('registry', 'news', 'predictions', 'votes', 'decisions', 'audit', 'benchmarks')
WRITERS = {
    'registry': ('authority',), 'news': ('publisher',),
    'predictions': ('validator1',), 'votes': VALIDATORS,
    'decisions': ('authority',), 'audit': ('authority',),
    'benchmarks': ('publisher',),
}
READ_COMMANDS = {'status', 'inspect', 'capture', 'nlp', 'rpc', 'verify-file', 'reputation', 'reconcile', 'doctor'}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds')


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def emit(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False), flush=True)


class LabError(RuntimeError):
    pass


class RPCError(LabError):
    def __init__(self, message: str, code: int | None = None, ambiguous: bool = False,
                 transport: bool = False):
        super().__init__(message + (f' [RPC code {code}]' if code is not None else ''))
        self.code = code
        self.ambiguous = ambiguous
        self.transport = transport


def read_only_rpc(method: str) -> bool:
    # Explicitly exclude getnewaddress and other state-changing "get" methods.
    return method in {
        'getinfo', 'getblockchaininfo', 'getblockchainparams', 'getblockhash',
        'getblock', 'getrawtransaction', 'getrawmempool', 'getmempoolinfo',
        'getpeerinfo', 'getaddresses', 'getassetinfo', 'getstreaminfo',
        'getruntimeparams', 'getaddressbalances', 'getstreamitem',
        'liststreams', 'listassets', 'listminers', 'listpermissions',
        'liststreamitems', 'liststreamkeyitems', 'liststreamtxitems',
        'listunspent', 'verifypermission', 'validateaddress', 'verifymessage', 'help'
    }


class RPC:
    """One HTTP connection per thread. Never automatically retry a write.

    A transport failure can happen AFTER the server broadcasts a transaction.
    Therefore it is an UNKNOWN outcome, not proof that nothing was written.
    """
    def __init__(self, conf: Path, timeout: float = 30):
        settings: dict[str, str] = {}
        for line in conf.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith(('#', ';')) and '=' in line:
                k, v = line.split('=', 1)
                settings[k.strip()] = v.strip()
        for name in ('rpcuser', 'rpcpassword', 'rpcport'):
            if not settings.get(name):
                raise LabError(f'{conf}: missing {name}')
        self.host = settings.get('rpcconnect', '127.0.0.1')
        if self.host not in ('127.0.0.1', 'localhost', '::1'):
            raise LabError('This local-lab client refuses non-loopback RPC endpoints.')
        self.port = int(settings['rpcport'])
        self.auth = base64.b64encode(
            (settings['rpcuser'] + ':' + settings['rpcpassword']).encode()).decode()
        self.timeout = timeout
        self.local = threading.local()

    def call(self, method: str, *params: Any) -> Any:
        conn = getattr(self.local, 'conn', None)
        if conn is None:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
            self.local.conn = conn
        request_id = uuid.uuid4().hex
        body = canonical({'jsonrpc': '1.0', 'id': request_id, 'method': method, 'params': list(params)})
        try:
            conn.request('POST', '/', body=body.encode('utf-8'), headers={
                'Content-Type': 'application/json', 'Authorization': 'Basic ' + self.auth})
            response = conn.getresponse()
            raw = response.read()
        except (OSError, http.client.HTTPException) as exc:
            conn.close()
            self.local.conn = None
            reading = read_only_rpc(method)
            note = ('node unavailable or connection lost; use lab.py start for a stopped lab'
                    if reading else 'write outcome may be unknown; inspect history before retrying')
            raise RPCError(f'{method}: transport failure ({type(exc).__name__}); {note}',
                           ambiguous=not reading, transport=True) from exc
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as exc:
            raise RPCError(f'{method}: HTTP {response.status}, non-JSON response', ambiguous=True) from exc
        if not isinstance(result, dict):
            raise RPCError(f'{method}: unexpected JSON response', ambiguous=not read_only_rpc(method))
        if result.get('error'):
            err = result['error']
            raise RPCError(f'{method}: {err.get("message", err)}', err.get('code'))
        if response.status != 200 or result.get('id') != request_id:
            raise RPCError(f'{method}: invalid HTTP status or response ID', ambiguous=True)
        return result.get('result')

    def close(self) -> None:
        conn = getattr(self.local, 'conn', None)
        if conn is not None:
            conn.close()
            self.local.conn = None


class WorkspaceLock:
    """Prevents concurrent lab writers; does not constrain raw RPC clients."""
    def __init__(self, root: Path):
        self.path = root / 'writer.lock'
    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise LabError(f'{self.path} exists. Another writer may be active. '
                           'After confirming no lab.py writer is running, remove this file manually.') from exc
        with os.fdopen(fd, 'w') as fh:
            fh.write(canonical({'pid': os.getpid(), 'started': utc()}))
        return self
    def __exit__(self, *args):
        self.path.unlink(missing_ok=True)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def latency_stats(values: list[float]) -> dict[str, Any]:
    return {'samples': len(values), 'mean_ms': statistics.mean(values) if values else None,
            'p50_ms': percentile(values, .5), 'p95_ms': percentile(values, .95),
            'p99_ms': percentile(values, .99), 'max_ms': max(values) if values else None}


STOP_WORDS = set('a an the is are was were to of in on for and or with at by from as this that it'.split())


def tokenize(text: str) -> list[str]:
    # Negations are intentionally retained. English-only teaching tokenizer.
    return [w for w in re.findall(r'[a-z]+', text.lower()) if w not in STOP_WORDS]


def load_dataset(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    if not rows or not {'id', 'split', 'label', 'text'} <= set(rows[0]):
        raise LabError('CSV needs id,split,label,text columns')
    seen: set[str] = set()
    for row in rows:
        if row['label'] not in ('REAL', 'FAKE') or row['split'] not in ('train', 'test'):
            raise LabError('Dataset label must be REAL/FAKE and split must be train/test')
        normalized = ' '.join(tokenize(row['text']))
        if not normalized or normalized in seen:
            raise LabError('Dataset has empty or duplicate normalized text; fix before training')
        seen.add(normalized)
    train_labels = {r['label'] for r in rows if r['split'] == 'train'}
    if train_labels != {'REAL', 'FAKE'}:
        raise LabError('Training split must contain both labels')
    return rows


class TeachingModel:
    """NLP lexical-count states + TF-IDF cosine evidence + tabular Q-learning.

    Each training example is one terminal episode: reward +1 correct, -1 wrong,
    -0.15 abstain. gamma=0. No online rewards are inferred from confirmation.
    This is a tiny contextual-bandit-style RL simplification, not paper DRL.
    """
    ACTIONS = ('REAL', 'FAKE', 'REVIEW')
    def __init__(self, train_rows: list[dict[str, str]], qtable: dict | None = None):
        self.rows = train_rows
        dfs = collections.Counter(t for r in train_rows for t in set(tokenize(r['text'])))
        self.idf = {t: math.log((1 + len(train_rows)) / (1 + n)) + 1 for t, n in dfs.items()}
        self.vectors = [self.vector(r['text']) for r in train_rows]
        self.qtable = qtable or {}

    def vector(self, text: str) -> dict[str, float]:
        counts = collections.Counter(tokenize(text))
        vector = {t: (1 + math.log(n)) * self.idf[t] for t, n in counts.items() if t in self.idf}
        norm = math.sqrt(sum(v * v for v in vector.values())) or 1
        return {t: v / norm for t, v in vector.items()}

    def evidence(self, text: str, exclude: int | None = None) -> tuple[float, float]:
        vector = self.vector(text)
        best = {'REAL': 0.0, 'FAKE': 0.0}
        for index, (row, other) in enumerate(zip(self.rows, self.vectors)):
            if index == exclude:
                continue
            cosine = sum(v * other.get(t, 0) for t, v in vector.items())
            best[row['label']] = max(best[row['label']], cosine)
        return best['REAL'], best['FAKE']

    @staticmethod
    def state(text: str) -> str:
        # Hand-selected FEATURE words, not a rule assigning a truth label.
        # The Q table learns an action from labelled terminal rewards.
        words = set(tokenize(text))
        suspicion = len(words & {'anonymous', 'unverified', 'rumor', 'secret', 'shocking', 'unbelievable', 'viral'})
        evidence = len(words & {'published', 'official', 'record', 'report', 'notice', 'schedule', 'timetable',
                                'approved', 'confirms', 'confirmed', 'announcement', 'minutes'})
        return f'suspicion={min(2, suspicion)};evidence={min(2, evidence)}'

    def train(self, epochs: int = 250, seed: int = 42) -> None:
        rng = random.Random(seed)
        examples = [(self.state(r['text']), r['label']) for r in self.rows]
        self.qtable = {}
        for _ in range(epochs):
            rng.shuffle(examples)
            for state, truth in examples:
                q = self.qtable.setdefault(state, [0.0, 0.0, 0.0])
                a = rng.randrange(3) if rng.random() < .2 else max(range(3), key=lambda j: q[j])
                reward = -.15 if a == 2 else (1.0 if self.ACTIONS[a] == truth else -1.0)
                q[a] += .1 * (reward - q[a])

    def predict(self, text: str, threshold: float = .35) -> dict[str, Any]:
        real, fake = self.evidence(text)
        state = self.state(text)
        q = self.qtable.get(state)
        label = self.ACTIONS[max(range(3), key=lambda j: q[j])] if q else 'REVIEW'
        reason = 'tabular_policy' if q else 'unseen_state'
        if max(real, fake) < threshold:
            label, reason = 'REVIEW', 'low_similarity'
        return {'label': label, 'real_similarity': real, 'fake_similarity': fake,
                'state': state, 'q_values': q, 'threshold': threshold, 'reason': reason,
                'warning': 'Teaching recommendation; similarity is not probability of truth.'}


def train_model(root: Path, dataset: Path, epochs: int = 250, seed: int = 42) -> dict:
    rows = load_dataset(dataset)
    training = [r for r in rows if r['split'] == 'train']
    model = TeachingModel(training)
    model.train(epochs, seed)
    tests = [r for r in rows if r['split'] == 'test']
    outcomes = [{'id': r['id'], 'truth': r['label'], **model.predict(r['text'])} for r in tests]
    decided = [r for r in outcomes if r['label'] != 'REVIEW']
    correct = sum(r['label'] == r['truth'] for r in outcomes)
    metadata = {'method': 'NLP lexical-count states + TF-IDF evidence + terminal tabular Q-learning; NOT DRL',
                'dataset_sha256': hashlib.sha256(dataset.read_bytes()).hexdigest(),
                'dataset_kind': 'small hand-authored classroom fixture; not research evidence',
                'seed': seed, 'epochs': epochs, 'alpha': .1, 'epsilon': .2, 'gamma': 0,
                'train_rows': len(training), 'test_rows': len(tests),
                'test_accuracy_including_abstentions_as_incorrect': correct / len(tests) if tests else None,
                'test_coverage': len(decided) / len(tests) if tests else None,
                'test_accuracy_on_decided': correct / len(decided) if decided else None,
                'test_outcomes': outcomes}
    write_json(root / 'model.json', {'training': training, 'qtable': model.qtable, 'metadata': metadata})
    write_json(root / 'evidence' / 'model_evaluation.json', metadata)
    return metadata


def resolve_decision(votes: list[dict], addresses: set[str], news_id: str,
                     content_hash: str, minconf: int = 1) -> dict:
    """Verify observed chain publisher identities, references and 2-of-2 votes.

    Any duplicate/conflicting vote from a validator leads to REVIEW; this avoids
    relying on a race-prone 'latest item wins' rule. Native miners do not run this.
    """
    seen: dict[str, dict] = {}
    reasons: list[str] = []
    for item in votes:
        data = item.get('data', {}).get('json', {})
        publishers = item.get('publishers', [])
        if len(publishers) != 1 or publishers[0] not in addresses:
            reasons.append('unrecognized_publisher')
            continue
        signer = publishers[0]
        if (data.get('validator_address') != signer or data.get('news_id') != news_id
                or data.get('content_sha256') != content_hash
                or data.get('label') not in ('REAL', 'FAKE', 'REVIEW')):
            reasons.append('invalid_vote_binding')
            continue
        if item.get('confirmations', 0) < minconf:
            reasons.append('unconfirmed_vote')
            continue
        if signer in seen:
            reasons.append('duplicate_validator_vote')
        seen[signer] = item
    if reasons or set(seen) != addresses:
        return {'label': 'REVIEW', 'reasons': reasons or ['missing_validator'],
                'vote_txids': [v['txid'] for v in seen.values()]}
    labels = {v['data']['json']['label'] for v in seen.values()}
    result = labels.pop() if len(labels) == 1 else 'REVIEW'
    return {'label': result, 'reasons': ['two_matching_votes'] if result != 'REVIEW' else ['disagreement_or_abstention'],
            'vote_txids': sorted(v['txid'] for v in seen.values())}


class Lab:
    def __init__(self, root: Path):
        self.root = root.resolve()
        config_path = self.root / 'lab.json'
        if not config_path.is_file():
            raise LabError(f'No lab.json in workspace: {self.root}. '
                           'Select the original workspace with --workspace BEFORE the command, '
                           'or run setup --bin-dir PATH for a NEW lab.')
        self.cfg = read_json(config_path)
        self.chain = self.cfg['chain']
        self.clients = {r: RPC(Path(n['conf'])) for r, n in self.cfg['nodes'].items()}
        self.local_lock = threading.RLock()

    def rpc(self, role: str, method: str, *args: Any) -> Any:
        attempts = 2 if read_only_rpc(method) else 1
        for attempt in range(attempts):
            try:
                return self.clients[role].call(method, *args)
            except RPCError as exc:
                if not exc.transport or attempt + 1 == attempts:
                    raise
                time.sleep(.1)
        raise AssertionError('unreachable')

    def address(self, role: str) -> str:
        address = self.cfg['nodes'][role].get('address')
        if not address:
            raise LabError(f'{role} is not initialized; complete setup first')
        return address

    def save(self) -> None:
        write_json(self.root / 'lab.json', self.cfg)

    def publish(self, role: str, stream: str, keys: list[str] | str, payload: dict) -> str:
        return self.rpc(role, 'publishfrom', self.address(role), stream, keys, {'json': payload})

    def items(self, role: str, stream: str, key: str) -> list[dict]:
        result: list[dict] = []
        start = 0
        while True:
            page = self.rpc(role, 'liststreamkeyitems', stream, key, False, 200, start)
            result.extend(page)
            if len(page) < 200:
                return result
            start += len(page)
            if start > 100000:
                raise LabError('Safety limit: too many records for one key')

    def stream_tx(self, role: str, stream: str, txid: str) -> dict:
        result = self.rpc(role, 'liststreamtxitems', stream, txid, False)
        if len(result) != 1:
            raise LabError(f'Expected one item in {stream} for {txid}; observed {len(result)}')
        return result[0]

    def wait(self, txids: list[str], role: str = 'auditor', confirmations: int = 1,
             timeout: float = 180) -> None:
        """Retry READS while a peer learns a broadcast tx; never rebroadcast it.

        MultiChain -710 means RPC_TX_NOT_FOUND, not a rejected transaction.
        -5 is retained for older Bitcoin-derived responses. Invalid parameter
        (-8) and permission (-704) errors are not swallowed.
        """
        if confirmations < 1 or timeout <= 0:
            raise LabError('Confirmation target and timeout must be positive')
        pending = set(txids)
        if any(not isinstance(t, str) or not t for t in pending):
            raise LabError('Confirmation wait requires non-empty transaction IDs')
        deadline = time.perf_counter() + timeout
        last_error = None
        while pending and time.perf_counter() < deadline:
            for txid in list(pending):
                try:
                    tx = self.rpc(role, 'getrawtransaction', txid, True)
                    if int(tx.get('confirmations', 0)) >= confirmations:
                        pending.remove(txid)
                except RPCError as exc:
                    if exc.code not in (-710, -5, -28) and not exc.transport:
                        raise
                    last_error = str(exc)
                if time.perf_counter() >= deadline:
                    break
            if pending:
                time.sleep(.2)
        if pending:
            sample = ', '.join(sorted(pending)[:3])
            raise LabError(f'Timed out on {role}: {len(pending)} transactions lack '
                           f'{confirmations} confirmation(s). Example txids: {sample}. '
                           f'Last read error: {last_error or "none; not yet confirmed"}. '
                           'Check lab.py status / doctor and node logs. Do not resubmit blindly.')

    def membership(self, role: str) -> dict:
        addr = self.address(role)
        records = self.items('authority', 'registry', addr)
        if not records:
            raise LabError(f'{role} has no registration record')
        for item in records:
            data = item.get('data', {}).get('json', {})
            if (item.get('publishers') == [self.address('authority')]
                    and data.get('event') == 'ENROLL' and data.get('address') == addr
                    and data.get('role') == role and item.get('confirmations', 0) >= 1):
                return data
        raise LabError(f'{role} has no confirmed authority-issued membership')

    def submit(self, text: str, news_id: str | None = None, run_id: str | None = None) -> dict:
        if not text.strip() or len(text.encode('utf-8')) > 65536:
            raise LabError('News text must be 1 to 65536 UTF-8 bytes')
        news_id = news_id or uuid.uuid4().hex
        if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,80}', news_id):
            raise LabError('Invalid news ID')
        self.membership('publisher')
        with self.local_lock:
            if self.items('authority', 'news', news_id):
                raise LabError('Duplicate news ID; stream keys are not natively unique')
            payload = {'schema': 1, 'news_id': news_id, 'publisher_address': self.address('publisher'),
                       'text': text, 'content_sha256': digest(text), 'created_at': utc(), 'run_id': run_id}
            txid = self.publish('publisher', 'news', [news_id, run_id or 'manual'], payload)
        return {'news_id': news_id, 'txid': txid, 'content_sha256': payload['content_sha256']}

    def news(self, news_id: str, role: str = 'authority', minconf: int = 1) -> dict:
        records = self.items(role, 'news', news_id)
        if len(records) != 1:
            raise LabError(f'Expected exactly one submitted article, found {len(records)}')
        item = records[0]
        data = item.get('data', {}).get('json', {})
        if (item.get('publishers') != [self.address('publisher')]
                or data.get('publisher_address') != self.address('publisher')
                or data.get('news_id') != news_id or digest(data.get('text', '')) != data.get('content_sha256')):
            raise LabError('News author, ID or content-hash verification failed')
        if item.get('confirmations', 0) < minconf:
            raise LabError('News is not sufficiently confirmed')
        return item

    def model(self) -> tuple[TeachingModel, str]:
        path = self.root / 'model.json'
        if not path.exists():
            raise LabError('Run: python lab.py train')
        saved = read_json(path)
        return TeachingModel(saved['training'], saved['qtable']), hashlib.sha256(path.read_bytes()).hexdigest()

    def analyze(self, news_id: str, threshold: float = .35) -> dict:
        item = self.news(news_id, 'validator1')
        data = item['data']['json']
        model, model_hash = self.model()
        prediction = model.predict(data['text'], threshold)
        payload = {'schema': 1, 'news_id': news_id, 'news_txid': item['txid'],
                   'content_sha256': data['content_sha256'], 'model_sha256': model_hash,
                   'created_at': utc(), **prediction}
        txid = self.publish('validator1', 'predictions', news_id, payload)
        return {'txid': txid, **payload}

    def vote(self, role: str, news_id: str, label: str, reason: str) -> dict:
        if role not in VALIDATORS or label not in ('REAL', 'FAKE', 'REVIEW') or not reason.strip():
            raise LabError('A validator, allowed label and non-empty reason are required')
        self.membership(role)
        article = self.news(news_id, role)
        with self.local_lock:
            previous = self.items(role, 'votes', news_id)
            if any(self.address(role) in v.get('publishers', []) for v in previous):
                raise LabError('This validator has already voted')
            payload = {'schema': 1, 'news_id': news_id, 'news_txid': article['txid'],
                       'validator_address': self.address(role), 'content_sha256': article['data']['json']['content_sha256'],
                       'label': label, 'reason': reason, 'created_at': utc()}
            txid = self.publish(role, 'votes', news_id, payload)
        return {'txid': txid, **payload}

    def finalize(self, news_id: str) -> dict:
        article = self.news(news_id)
        with self.local_lock:
            if self.items('authority', 'decisions', news_id):
                raise LabError('Already finalized; create a new review version instead of overwriting')
            for role in VALIDATORS:
                self.membership(role)
                if not self.rpc('authority', 'verifypermission', self.address(role), 'votes.write'):
                    raise LabError(f'{role} currently revoked; do not finalize using that authority')
            result = resolve_decision(self.items('authority', 'votes', news_id),
                                      {self.address(r) for r in VALIDATORS}, news_id,
                                      article['data']['json']['content_sha256'])
            # Also bind each accepted vote to the exact article transaction.
            for v in self.items('authority', 'votes', news_id):
                if v['txid'] in result['vote_txids'] and v['data']['json'].get('news_txid') != article['txid']:
                    result['label'], result['reasons'] = 'REVIEW', ['wrong_news_transaction']
            payload = {'schema': 1, 'news_id': news_id, 'news_txid': article['txid'],
                       'content_sha256': article['data']['json']['content_sha256'],
                       'policy': 'two-distinct-registered-validators-v1', 'created_at': utc(), **result}
            txid = self.publish('authority', 'decisions', news_id, payload)
        return {'txid': txid, **payload}

    def inspect(self, news_id: str) -> dict:
        article = self.news(news_id, 'auditor')
        decisions = self.items('auditor', 'decisions', news_id)
        votes = self.items('auditor', 'votes', news_id)
        result = {'news': article, 'predictions': self.items('auditor', 'predictions', news_id),
                  'votes': votes, 'decisions': decisions, 'audit_pass': False}
        if len(decisions) != 1:
            result['audit_error'] = 'Missing or multiple decision records'
            return result
        decision = decisions[0]
        data = decision.get('data', {}).get('json', {})
        referenced = [v for v in votes if v['txid'] in data.get('vote_txids', [])]
        recomputed = resolve_decision(referenced, {self.address(r) for r in VALIDATORS}, news_id,
                                      article['data']['json']['content_sha256'])
        # Verify historical decision evidence, not whether a member remains active today.
        audit_ok = (decision.get('publishers') == [self.address('authority')]
                    and decision.get('confirmations', 0) >= 1
                    and data.get('news_txid') == article['txid']
                    and data.get('content_sha256') == article['data']['json']['content_sha256']
                    and data.get('label') == recomputed['label']
                    and len(set(data.get('vote_txids', []))) == len(data.get('vote_txids', []))
                    and set(data.get('vote_txids', [])) == {v['txid'] for v in referenced}
                    and all(v['data']['json'].get('news_txid') == article['txid'] for v in referenced))
        result.update(audit_pass=audit_ok, recomputed_label=recomputed['label'],
                      audit_scope='Referenced signed records and confirmed content; not real-world truth or full historical permission reconstruction')
        return result

    def pipeline(self, row: dict, news_id: str, run_id: str, threshold: float = .35,
                 second_label: str | None = None, txlog: list[str] | None = None) -> dict:
        txlog = txlog if txlog is not None else []
        submitted = self.submit(row['text'], news_id, run_id)
        txlog.append(submitted['txid'])
        # Ensure prerequisites are confirmed before being consumed by reviewers.
        for role in ('validator1', 'validator2'):
            self.wait([submitted['txid']], role)
        prediction = self.analyze(news_id, threshold)
        txlog.append(prediction['txid'])
        v1 = self.vote('validator1', news_id, row['label'], 'Classroom fixture label; not independent fact checking')
        txlog.append(v1['txid'])
        v2 = self.vote('validator2', news_id, second_label or row['label'], 'Classroom fixture label; not independent fact checking')
        txlog.append(v2['txid'])
        self.wait([v1['txid'], v2['txid']], 'authority')
        decision = self.finalize(news_id)
        txlog.append(decision['txid'])
        return {'news_id': news_id, 'decision': decision['label'], 'prediction': prediction['label'], 'txids': list(txlog)}

    def challenge(self, role: str, age: int = 0) -> dict:
        now = int(time.time()) - age
        return {'domain': 'FakeMedia-enrollment-v1', 'chain': self.chain,
                'genesis': self.rpc('authority', 'getblockhash', 0),
                'role': role, 'address': self.address(role),
                'nonce': secrets.token_hex(24), 'issued_at': now, 'expires_at': now + 120}

    def consume_challenge(self, challenge: dict, signature: str) -> bool:
        path = self.root / 'used_nonces.json'
        used = read_json(path) if path.exists() else []
        now = int(time.time())
        role = challenge.get('role')
        if (role not in ROLES or challenge.get('address') != self.address(role)
                or challenge.get('domain') != 'FakeMedia-enrollment-v1' or challenge.get('chain') != self.chain
                or challenge.get('genesis') != self.rpc('authority', 'getblockhash', 0)
                or not re.fullmatch(r'[a-f0-9]{48}', challenge.get('nonce', ''))
                or challenge.get('issued_at', now + 1) > now
                or challenge.get('expires_at', 0) < now
                or challenge.get('expires_at', 0) - challenge.get('issued_at', 0) != 120
                or challenge['nonce'] in used):
            return False
        try:
            valid = self.rpc('authority', 'verifymessage', challenge['address'], signature, canonical(challenge))
        except RPCError as exc:
            if exc.ambiguous:
                raise
            valid = False
        if valid:
            used.append(challenge['nonce'])
            write_json(path, used)
        return bool(valid)

    def enroll(self, role: str) -> str | None:
        existing = self.items('authority', 'registry', self.address(role))
        valid = [v for v in existing
                 if v.get('publishers') == [self.address('authority')]
                 and v.get('data', {}).get('json', {}).get('event') == 'ENROLL'
                 and v['data']['json'].get('address') == self.address(role)
                 and v['data']['json'].get('role') == role]
        if len(valid) > 1:
            raise LabError(f'Multiple enrollment records for {role}; inspect registry before repair')
        if valid:
            self.wait([valid[0]['txid']], 'authority')
            return valid[0]['txid']
        if existing:
            raise LabError(f'Unexpected registry records for {role}; refusing to overwrite identity')
        challenge = self.challenge(role)
        signature = self.rpc(role, 'signmessage', self.address(role), canonical(challenge))
        if not self.consume_challenge(challenge, signature):
            raise LabError('Enrollment challenge verification failed')
        payload = {'schema': 1, 'event': 'ENROLL', 'role': role, 'address': self.address(role),
                   'challenge': challenge, 'signature': signature, 'created_at': utc(),
                   'identity_check': 'local classroom operator approval; NOT real identity verification',
                   'initial_credibility': 50}
        return self.publish('authority', 'registry', self.address(role), payload)


def executable(bin_dir: Path, name: str) -> str:
    path = bin_dir / (name + ('.exe' if os.name == 'nt' else ''))
    if not path.is_file():
        raise LabError(f'Missing executable: {path}')
    return str(path.resolve())


def conf_text(rpc_port: int, p2p_port: int) -> str:
    return (f'rpcuser=lab_{secrets.token_hex(6)}\nrpcpassword={secrets.token_urlsafe(32)}\n'
            f'rpcport={rpc_port}\nport={p2p_port}\nrpcallowip=127.0.0.1\n'
            'rpcbind=127.0.0.1\nbind=127.0.0.1\nserver=1\ndaemon=0\n'
            'rpcthreads=16\ntxindex=1\nmaxshowndata=2097152\nautosubscribe=streams,assets\n')


def launch(lab: Lab, role: str, join: bool = False) -> subprocess.Popen:
    node = lab.cfg['nodes'][role]
    chain_arg = f'{lab.chain}@127.0.0.1:{lab.cfg["nodes"]["authority"]["p2p_port"]}' if join else lab.chain
    cmd = [executable(Path(lab.cfg['bin_dir']), 'multichaind'), chain_arg,
           f'-datadir={node["datadir"]}', f'-rpcport={node["rpc_port"]}',
           f'-port={node["p2p_port"]}', '-daemon=0', '-shortoutput=1']
    for other, cfg in lab.cfg['nodes'].items():
        if other != role:
            cmd.append(f'-addnode=127.0.0.1:{cfg["p2p_port"]}')
    log = Path(node['datadir']) / 'startup.log'
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if os.name == 'nt' else 0
    with log.open('wb') as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                creationflags=flags, start_new_session=(os.name != 'nt'))
    node['pid'] = proc.pid
    lab.save()
    return proc


def is_ready(lab: Lab, role: str) -> bool:
    try:
        info = lab.rpc(role, 'getinfo')
        if info.get('chainname') != lab.chain:
            raise LabError(f'Port for {role} belongs to a different chain; refusing to use it')
        saved = lab.cfg['nodes'][role].get('address')
        if saved and not lab.rpc(role, 'validateaddress', saved).get('ismine'):
            raise LabError(f'{role} RPC endpoint belongs to a different wallet; refusing to use it')
        genesis = lab.cfg.get('genesis_hash')
        if genesis and lab.rpc(role, 'getblockhash', 0) != genesis:
            raise LabError(f'{role} has the wrong genesis block; refusing to use it')
        return True
    except RPCError:
        return False


def wait_ready(lab: Lab, role: str, timeout: float = 45) -> None:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if is_ready(lab, role):
            return
        time.sleep(.25)
    raise LabError(f'{role} not ready; inspect {lab.cfg["nodes"][role]["datadir"]}/startup.log')


def ensure_ports_free(ports: list[int]) -> None:
    for port in ports:
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', port))
            except OSError as exc:
                raise LabError(f'Port {port} is already in use; choose different --rpc-base/--p2p-base') from exc


def setup(root: Path, args: argparse.Namespace) -> dict:
    cfg_path = root / 'lab.json'
    if cfg_path.exists():
        raise LabError('Workspace already exists. Use repair --bin-dir PATH to finish an incomplete '
                       'setup, or start for a completed lab. No data was deleted.')
    bin_dir = Path(args.bin_dir).resolve()
    utility = executable(bin_dir, 'multichain-util')
    executable(bin_dir, 'multichaind')
    executable(bin_dir, 'multichain-cli')
    if not re.fullmatch(r'[a-z][a-z0-9_]{1,30}', args.chain):
        raise LabError('Use a lowercase chain name such as fakenews')
    if args.block_time < 1 or args.block_size < 1048576 or not .5 < args.diversity <= 1:
        raise LabError('Use block time >=1, block size >=1048576 and diversity >0.5 to 1')
    ports = [args.rpc_base + i for i in range(5)] + [args.p2p_base + i for i in range(5)]
    if len(set(ports)) != 10 or not all(1024 <= p <= 65535 for p in ports):
        raise LabError('RPC and P2P ranges must be distinct and in 1024..65535')
    if args.auto_ports:
        for offset in range(0, 30000, 20):
            candidates = [p + offset for p in ports]
            if max(candidates) > 65535:
                break
            try:
                ensure_ports_free(candidates)
                args.rpc_base += offset
                args.p2p_base += offset
                break
            except LabError:
                continue
        else:
            raise LabError('No unused port ranges found')
        ports = [args.rpc_base + i for i in range(5)] + [args.p2p_base + i for i in range(5)]
    ensure_ports_free(ports)
    print(f'Workspace: {root} | chain: {args.chain} | RPC: {args.rpc_base}-{args.rpc_base+4} '
          f'| P2P: {args.p2p_base}-{args.p2p_base+4}', flush=True)
    root.mkdir(parents=True, exist_ok=True)
    nodes = {}
    for i, role in enumerate(ROLES):
        datadir = (root / 'nodes' / role).resolve()
        if datadir.exists() and any(datadir.iterdir()):
            raise LabError(f'Existing node data at {datadir}, but no lab.json. '
                           'Use a new --workspace; existing wallets will not be overwritten.')
        datadir.mkdir(parents=True, exist_ok=True)
        nodes[role] = {'datadir': str(datadir), 'conf': str(datadir / args.chain / 'multichain.conf'),
                       'rpc_port': args.rpc_base + i, 'p2p_port': args.p2p_base + i}
    overrides = {'target-block-time': args.block_time, 'maximum-block-size': args.block_size,
                 'mining-diversity': args.diversity, 'mining-turnover': 0,
                 'mine-empty-rounds': -1, 'setup-first-blocks': 10, 'target-adjust-freq': -1,
                 'root-stream-open': 'false', 'anyone-can-connect': 'false',
                 'anyone-can-send': 'false', 'anyone-can-receive': 'false',
                 'anyone-can-create': 'false', 'anyone-can-issue': 'false',
                 'anyone-can-mine': 'false', 'anyone-can-admin': 'false'}
    cmd = [utility, 'create', args.chain, f'-datadir={nodes["authority"]["datadir"]}']
    # Official multichain-util supports blockchain parameter overrides on create.
    cmd.extend(f'-{k}={v}' for k, v in overrides.items())
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    (root / 'create_chain.log').write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
    if result.returncode:
        raise LabError('multichain-util failed. See create_chain.log')
    for node in nodes.values():
        conf = Path(node['conf'])
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text(conf_text(node['rpc_port'], node['p2p_port']), encoding='ascii')
        with contextlib.suppress(OSError):
            conf.chmod(0o600)
    cfg = {'chain': args.chain, 'bin_dir': str(bin_dir), 'created_at': utc(), 'nodes': nodes,
           'parameters_requested': overrides, 'setup_complete': False}
    write_json(cfg_path, cfg)
    return complete_setup(Lab(root))


def port_listening(port: int) -> bool:
    """Check for a live listener, not just a TIME_WAIT socket after shutdown."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(.3)
        return sock.connect_ex(('127.0.0.1', port)) == 0


def node_listeners(lab: Lab, role: str) -> list[int]:
    node = lab.cfg['nodes'][role]
    return [node[k] for k in ('rpc_port', 'p2p_port') if port_listening(node[k])]


def stream_is_closed(info: dict) -> bool:
    # MultiChain 2.x uses restrict.write; older APIs exposed open.
    if isinstance(info.get('restrict'), dict):
        return info['restrict'].get('write') is True
    return info.get('open') is False


def remember_setup_tx(lab: Lab, action: str, txid: str) -> None:
    lab.cfg.setdefault('setup_transactions', {})[action] = txid
    lab.save()


def assigned_mining_state(lab: Lab, observer: str, address: str) -> dict[str, Any]:
    """Read confirmed mining authorization, NOT eligibility for the next block.

    MultiChain verifypermission(address, 'mine') calls CanMine(), which also
    applies mining-diversity. It can be false for an authorized miner waiting
    its turn. listminers.permitted separates authorization from that wait.
    This lab uses restricted mining (anyone-can-mine=false).
    """
    miners = lab.rpc(observer, 'listminers', True)
    if not isinstance(miners, list) or any(not isinstance(m, dict) for m in miners):
        raise LabError(f'{observer}: malformed listminers response')
    matches = [m for m in miners if m.get('address') == address]
    if len(matches) > 1:
        raise LabError(f'{observer}: duplicate mining records for {address}')
    if not matches:
        return {'address': address, 'permitted': False, 'present': False,
                'source': 'listminers.permitted'}
    miner = matches[0]
    if not isinstance(miner.get('permitted'), bool):
        raise LabError(f'{observer}: listminers.permitted is not a boolean for {address}')
    fields = ('address', 'permitted', 'islocal', 'diversitywaitblocks',
              'startblock', 'endblock', 'lastmined', 'chainstate', 'localstate')
    state = {key: miner[key] for key in fields if key in miner}
    state.update(present=True, source='listminers.permitted')
    return state


def ensure_grant(lab: Lab, role: str, permissions: str) -> str | None:
    """State-checked bootstrap only. Not called to silently undo revocation."""
    missing = []
    for permission in permissions.split(','):
        if permission == 'mine':
            granted = assigned_mining_state(lab, 'authority', lab.address(role))['permitted']
        else:
            granted = lab.rpc('authority', 'verifypermission', lab.address(role), permission)
        if not granted:
            missing.append(permission)
    if not missing:
        return None
    txid = lab.rpc('authority', 'grant', lab.address(role), ','.join(missing))
    remember_setup_tx(lab, 'grant:' + role + ':' + ','.join(missing), txid)
    lab.wait([txid], 'authority')
    return txid


def ensure_network(lab: Lab) -> None:
    """Bring up this workspace only and finish interrupted peer enrollment."""
    if not is_ready(lab, 'authority'):
        if node_listeners(lab, 'authority'):
            wait_ready(lab, 'authority', timeout=20)
        else:
            launch(lab, 'authority')
            wait_ready(lab, 'authority')
    if not lab.cfg['nodes']['authority'].get('address'):
        admins = lab.rpc('authority', 'listpermissions', 'admin')
        local = set(lab.rpc('authority', 'getaddresses'))
        addresses = [p['address'] for p in admins if p['address'] in local]
        if len(addresses) != 1:
            raise LabError('Expected exactly one local genesis administrator; inspect authority wallet')
        lab.cfg['nodes']['authority']['address'] = addresses[0]
    genesis = lab.rpc('authority', 'getblockhash', 0)
    if lab.cfg.get('genesis_hash') not in (None, genesis):
        raise LabError('Authority genesis does not match workspace metadata')
    lab.cfg['genesis_hash'] = genesis
    lab.save()
    for role in ROLES[1:]:
        print(f'Checking/joining {role}...', file=sys.stderr, flush=True)
        node = lab.cfg['nodes'][role]
        permissions = 'connect,receive' if role == 'auditor' else 'connect,send,receive'
        proc = None
        if not node.get('address'):
            if not is_ready(lab, role):
                if node_listeners(lab, role):
                    wait_ready(lab, role, timeout=20)
                else:
                    proc = launch(lab, role, join=True)
            deadline = time.perf_counter() + 60
            while time.perf_counter() < deadline:
                if is_ready(lab, role):
                    addresses = lab.rpc(role, 'getaddresses')
                    if len(addresses) != 1:
                        raise LabError(f'{role} has multiple addresses and no saved identity; inspect manually')
                    node['address'] = addresses[0]
                    break
                log = Path(node['datadir']) / 'startup.log'
                text = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
                found = re.findall(r'grant\s+([1-9A-HJ-NP-Za-km-z]{26,60})\s+connect', text)
                if not found:
                    found = re.findall(r'(?m)^\s*([1-9A-HJ-NP-Za-km-z]{26,60})\s*$', text)
                if found:
                    node['address'] = found[-1]
                    break
                if proc and proc.poll() is not None:
                    raise LabError(f'{role} initializer exited; inspect {log}')
                time.sleep(.25)
            if not node.get('address'):
                raise LabError(f'Cannot discover {role} address; inspect {node["datadir"]}/startup.log')
            lab.save()
        ensure_grant(lab, role, permissions)
        if not is_ready(lab, role):
            if proc:
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    wait_ready(lab, role, timeout=20)
            if not is_ready(lab, role):
                if node_listeners(lab, role):
                    wait_ready(lab, role, timeout=20)
                else:
                    launch(lab, role, join=True)
        wait_ready(lab, role)
        if not lab.rpc(role, 'validateaddress', lab.address(role)).get('ismine'):
            raise LabError(f'{role} does not own its saved identity; refusing to grant further permissions')


def complete_setup(lab: Lab) -> dict:
    """Resume only unfinished bootstrap. Does not replace params.dat or wallets."""
    if lab.cfg.get('setup_complete'):
        raise LabError('Setup already complete; use start, doctor, or explicit restore for revoked permissions')
    def stage(name: str):
        lab.cfg['setup_stage'] = name
        lab.cfg['software_version'] = VERSION
        lab.save()
        print('Setup: ' + name, file=sys.stderr, flush=True)

    stage('network')
    ensure_network(lab)
    stage('mining permissions')
    mining_txs = [t for r in VALIDATORS if (t := ensure_grant(lab, r, 'mine'))]
    for role in ROLES:
        lab.wait(mining_txs, role)
    stage('streams')
    creation_txs = []
    for stream in STREAMS:
        try:
            info = lab.rpc('authority', 'getstreaminfo', stream, True)
        except RPCError as exc:
            if exc.code != -708:
                raise
            txid = lab.rpc('authority', 'create', 'stream', stream, False)
            remember_setup_tx(lab, 'stream:' + stream, txid)
            lab.wait([txid], 'authority')
            info = lab.rpc('authority', 'getstreaminfo', stream, True)
        if not stream_is_closed(info):
            raise LabError(f'{stream} is not write-restricted; will not treat it as a secure lab stream')
        creation_txs.append(info['createtxid'])
    for role in ROLES:
        lab.wait(creation_txs, role)
        for stream in STREAMS:
            entries = lab.rpc(role, 'liststreams', stream)
            if not entries or not entries[0].get('subscribed'):
                lab.rpc(role, 'subscribe', stream, True)
    stage('signed registration')
    registrations = [t for r in ROLES if (t := lab.enroll(r))]
    for role in ROLES:
        lab.wait(registrations, role)
    stage('application permissions')
    grants = []
    for stream, writers in WRITERS.items():
        for role in writers:
            txid = ensure_grant(lab, role, stream + '.write')
            if txid:
                grants.append(txid)
    for role in ROLES:
        lab.wait(grants, role)
    stage('asset')
    try:
        asset = lab.rpc('authority', 'getassetinfo', 'NewsCredit', True)
    except RPCError as exc:
        if exc.code != -708:
            raise
        txid = lab.rpc('authority', 'issue', lab.address('authority'), 'NewsCredit', 1000, 1)
        remember_setup_tx(lab, 'asset:NewsCredit', txid)
        lab.wait([txid], 'authority')
        asset = lab.rpc('authority', 'getassetinfo', 'NewsCredit', True)
    if asset.get('open') is True or asset.get('issueqty') not in (None, 1000):
        raise LabError('Existing NewsCredit does not match the fixed 1000-unit lab asset; inspect it')
    txid = asset['issuetxid']
    for role in ROLES:
        lab.wait([txid], role)
        lab.rpc(role, 'subscribe', 'NewsCredit', True)
    lab.cfg['asset_issuance_txid'] = txid
    lab.save()
    stage('teaching model and evidence')
    if not (lab.root / 'model.json').is_file():
        train_model(lab.root, HERE / 'demo_news.csv')
    params = lab.rpc('authority', 'getblockchainparams')
    write_json(lab.root / 'evidence' / 'blockchain_parameters.json', params)
    source = Path(lab.cfg['nodes']['authority']['conf']).parent / 'params.dat'
    shutil.copy2(source, lab.root / 'evidence' / 'params.dat')
    stage('readiness validation')
    deadline = time.perf_counter() + 180
    while True:
        report = doctor(lab, include_setup=False)
        if report['all_passed']:
            break
        if time.perf_counter() >= deadline:
            raise LabError('Setup checks failed: ' + '; '.join(report['issues']) + '. Run doctor for details.')
        time.sleep(.5)
    lab.cfg['setup_complete'] = True
    lab.cfg['setup_stage'] = 'complete'
    lab.cfg['setup_completed_at'] = utc()
    lab.save()
    status(lab)
    return doctor(lab)


def repair(lab: Lab, bin_dir: str | None = None) -> dict:
    if bin_dir:
        path = Path(bin_dir).resolve()
        for name in ('multichaind', 'multichain-util', 'multichain-cli'):
            executable(path, name)
        lab.cfg['bin_dir'] = str(path)
        lab.save()
    # State-driven recovery, not a reset. Completed labs keep deliberate revocations.
    if lab.cfg.get('setup_complete'):
        start(lab, ROLES)
        result = doctor(lab)
        result['note'] = ('Setup was already complete. No permissions or assets were changed. '
                          'Use restore explicitly for a deliberately revoked writer.')
        return result
    return complete_setup(lab)


def doctor(lab: Lab, need_model: bool = True, check_permissions: bool = True,
           include_setup: bool = True) -> dict:
    issues: list[str] = []
    if include_setup and not lab.cfg.get('setup_complete'):
        issues.append('Setup is incomplete: run lab.py repair --bin-dir PATH')
    nodes: dict[str, dict] = {}
    heights: dict[str, int] = {}
    for role in ROLES:
        node = lab.cfg['nodes'][role]
        report: dict[str, Any] = {'rpc_port': node['rpc_port'], 'p2p_port': node['p2p_port']}
        nodes[role] = report
        try:
            if not is_ready(lab, role):
                raise LabError('RPC not ready; run start or repair and inspect startup.log')
            info = lab.rpc(role, 'getinfo')
            report['online'] = True
            report['blocks'] = int(info['blocks'])
            report['version'] = info.get('version')
            heights[role] = int(info['blocks'])
            if not lab.rpc(role, 'validateaddress', lab.address(role)).get('ismine'):
                issues.append(f'{role}: saved address does not belong to this wallet')
            stream_info = {v['name']: v for v in lab.rpc(role, 'liststreams')}
            missing = [s for s in STREAMS if s not in stream_info]
            unsubscribed = [s for s in STREAMS if s in stream_info and not stream_info[s].get('subscribed')]
            unclosed = [s for s in STREAMS if s in stream_info and not stream_is_closed(stream_info[s])]
            unsynced = [s for s in STREAMS if s in stream_info and stream_info[s].get('synchronized') is False]
            report.update(missing_streams=missing, unsubscribed_streams=unsubscribed,
                          open_streams=unclosed, unsynchronized_streams=unsynced)
            if missing:
                issues.append(f'{role}: missing streams: {", ".join(missing)}')
            if unsubscribed or unsynced:
                issues.append(f'{role}: stream subscription/index not ready: {", ".join(unsubscribed + unsynced)}')
            if unclosed:
                issues.append(f'{role}: streams unexpectedly allow unrestricted writes: {", ".join(unclosed)}')
            if check_permissions and not missing:
                mismatches = []
                for stream in STREAMS:
                    expected = role == 'authority' or role in WRITERS[stream]
                    actual = lab.rpc(role, 'verifypermission', lab.address(role), stream + '.write')
                    if bool(actual) != expected:
                        mismatches.append(stream + '.write')
                for permission in ('admin', 'issue', 'create', 'mine'):
                    expected = role == 'authority' or (permission == 'mine' and role in VALIDATORS)
                    if permission == 'mine':
                        mining = assigned_mining_state(lab, role, lab.address(role))
                        report['mining'] = dict(mining, expected_permitted=expected)
                        actual = mining['permitted']
                    else:
                        actual = lab.rpc(role, 'verifypermission', lab.address(role), permission)
                    if bool(actual) != expected:
                        mismatches.append(permission)
                if mismatches:
                    issues.append(f'{role}: permission mismatch: {", ".join(mismatches)}')
                report['permission_mismatches'] = mismatches
        except (LabError, KeyError, TypeError, ValueError) as exc:
            report['error'] = str(exc)
            issues.append(f'{role}: {exc}')
    shared: dict[str, Any] = {}
    if len(heights) == len(ROLES):
        minimum, maximum = min(heights.values()), max(heights.values())
        try:
            hashes = {r: lab.rpc(r, 'getblockhash', minimum) for r in ROLES}
            shared = {'height': minimum, 'same_hash': len(set(hashes.values())) == 1,
                      'height_lag': maximum - minimum}
            if not shared['same_hash']:
                issues.append('Nodes disagree at the common block height')
            if maximum - minimum > 2:
                issues.append('A node is more than 2 blocks behind; wait for synchronization')
            if minimum <= 10:
                issues.append('Wait until all five nodes have passed setup block 10')
        except LabError as exc:
            issues.append('Common-height check: ' + str(exc))
    try:
        asset = lab.rpc('authority', 'getassetinfo', 'NewsCredit')
        asset_id = asset.get('issuetxid')
        if not asset_id:
            issues.append('NewsCredit has no issuance transaction')
        if lab.cfg.get('asset_issuance_txid') and lab.cfg['asset_issuance_txid'] != asset_id:
            issues.append('NewsCredit issuance transaction differs from saved metadata')
    except LabError as exc:
        issues.append('Asset not ready: ' + str(exc))
    # A successful enrollment is required for every configured role.
    if nodes.get('authority', {}).get('online') and not nodes['authority'].get('missing_streams'):
        for role in ROLES:
            try:
                lab.membership(role)
            except LabError as exc:
                issues.append('Registration: ' + str(exc))
    if need_model:
        try:
            lab.model()
        except (LabError, KeyError, ValueError, OSError) as exc:
            issues.append('Teaching model not ready: ' + str(exc))
    result = {'software_version': VERSION, 'captured_at': utc(), 'workspace': str(lab.root),
              'chain': lab.chain, 'setup_complete': bool(lab.cfg.get('setup_complete')),
              'all_passed': not issues, 'nodes': nodes, 'shared_height_check': shared,
              'issues': issues,
              'note': 'Readiness checks are not a performance result or a real-world truth guarantee.'}
    write_json(lab.root / 'evidence' / 'doctor.json', result)
    return result


def require_ready(lab: Lab, need_model: bool = False, permissions: bool = False) -> None:
    if not lab.cfg.get('setup_complete'):
        raise LabError('Setup is incomplete. Run lab.py repair --bin-dir PATH in this workspace '
                       'before demo, security tests, or benchmarks. No workload was sent.')
    result = doctor(lab, need_model=need_model, check_permissions=permissions)
    if not result['all_passed']:
        raise LabError('Lab is not ready; no workload was sent. ' + '; '.join(result['issues']))


def stop(lab: Lab, roles: tuple[str, ...], timeout: float = 90) -> dict:
    """Request graceful shutdown, then wait for both node listeners to close.

    Does not taskkill every multichaind process or touch any other workspace.
    """
    results: dict[str, dict] = {}
    waiting: set[str] = set()
    for role in roles:
        try:
            if is_ready(lab, role):
                answer = lab.rpc(role, 'stop')
                results[role] = {'status': 'stopping', 'response': answer}
                waiting.add(role)
            elif not node_listeners(lab, role):
                results[role] = {'status': 'already_stopped', 'ports_closed': True}
            else:
                results[role] = {'status': 'unreachable', 'ports_closed': False,
                                 'error': 'Ports have a listener but expected RPC is not ready. No process was killed.'}
        except LabError as exc:
            results[role] = {'status': 'error', 'error': str(exc), 'ports_closed': False}
        finally:
            lab.clients[role].close()
    deadline = time.perf_counter() + timeout
    while waiting and time.perf_counter() < deadline:
        for role in list(waiting):
            if not node_listeners(lab, role):
                results[role].update(status='stopped', ports_closed=True)
                waiting.remove(role)
        if waiting:
            time.sleep(.25)
    for role in waiting:
        results[role].update(status='shutdown_timeout', ports_closed=False,
                             listening_ports=node_listeners(lab, role))
    return {'all_passed': all(v.get('ports_closed', False) for v in results.values()),
            'nodes': results, 'note': 'Wallets and blockchain data were preserved. No force termination was used.'}


def status(lab: Lab) -> dict:
    result: dict[str, Any] = {'captured_at': utc(), 'version': VERSION, 'chain': lab.chain,
                                   'workspace': str(lab.root),
                                   'setup_complete': bool(lab.cfg.get('setup_complete')), 'nodes': {}}
    for role in ROLES:
        try:
            info = lab.rpc(role, 'getinfo')
            peers = lab.rpc(role, 'getpeerinfo')
            chaininfo = lab.rpc(role, 'getblockchaininfo')
            result['nodes'][role] = {'address': lab.address(role), 'rpc_port': lab.cfg['nodes'][role]['rpc_port'],
                                     'blocks': info.get('blocks'), 'connections': info.get('connections'),
                                     'peer_count': len(peers), 'bestblockhash': chaininfo.get('bestblockhash'),
                                     'version': info.get('version'), 'protocolversion': info.get('protocolversion'),
                                     'setupblocks': info.get('setupblocks'), 'miningpaused': info.get('miningpaused')}
        except LabError as exc:
            result['nodes'][role] = {'error': str(exc)}
    try:
        result['miners'] = lab.rpc('authority', 'listminers', True)
        result['permissions'] = lab.rpc('authority', 'listpermissions')
        result['streams'] = lab.rpc('authority', 'liststreams')
        heights = [n['blocks'] for n in result['nodes'].values() if isinstance(n.get('blocks'), int)]
        common = min(heights) if len(heights) == len(ROLES) else None
        if common is not None:
            hashes = {r: lab.rpc(r, 'getblockhash', common) for r in ROLES}
            result['shared_height_check'] = {'height': common, 'hashes': hashes, 'same_hash': len(set(hashes.values())) == 1}
        result['past_setup_phase'] = bool(len(heights) == len(ROLES) and min(heights) > 10)
        present = {v.get('name') for v in result.get('streams', [])}
        result['missing_streams'] = sorted(set(STREAMS) - present)
        if not lab.cfg.get('setup_complete'):
            result['action_required'] = 'Setup is incomplete. Run lab.py repair; do not benchmark yet.'
    except LabError as exc:
        result['chain_error'] = str(exc)
    write_json(lab.root / 'evidence' / 'status.json', result)
    return result


def start(lab: Lab, roles: tuple[str, ...]) -> dict:
    for role in roles:
        if not is_ready(lab, role):
            if node_listeners(lab, role):
                wait_ready(lab, role, timeout=15)
            else:
                launch(lab, role, join=(role != 'authority'))
        wait_ready(lab, role)
    return status(lab)


def permission_change(lab: Lab, role: str, grant: bool) -> dict:
    if role not in ('publisher', *VALIDATORS):
        raise LabError('This command only changes application write permissions, never admin or mining')
    streams = [s for s, writers in WRITERS.items() if role in writers]
    txs = [lab.rpc('authority', 'grant' if grant else 'revoke', lab.address(role), f'{s}.write') for s in streams]
    lab.wait(txs)
    # Wait on originating role too: a stale wallet can otherwise accept locally.
    lab.wait(txs, role)
    audit = lab.publish('authority', 'audit', lab.address(role), {
        'event': 'RESTORE_WRITE' if grant else 'REVOKE_WRITE', 'role': role,
        'address': lab.address(role), 'permissions': [s + '.write' for s in streams],
        'permission_txids': txs, 'created_at': utc()})
    lab.wait([audit])
    return {'role': role, 'granted': grant, 'txids': txs, 'audit_txid': audit}


def security_tests(lab: Lab) -> dict:
    checks: list[dict] = []
    def record(name: str, passed: bool, details: Any):
        checks.append({'test': name, 'passed': bool(passed), 'details': details})
    challenge = lab.challenge('publisher')
    sig = lab.rpc('publisher', 'signmessage', lab.address('publisher'), canonical(challenge))
    record('valid_key_possession', lab.consume_challenge(challenge, sig), 'Fresh bound challenge accepted')
    record('challenge_replay_rejected', not lab.consume_challenge(challenge, sig), 'Same nonce consumed twice')
    fresh = lab.challenge('publisher')
    sig2 = lab.rpc('publisher', 'signmessage', lab.address('publisher'), canonical(fresh))
    altered = dict(fresh, role='validator1')
    record('role_substitution_rejected', not lab.consume_challenge(altered, sig2), 'Role/address and signature bound')
    expired = lab.challenge('publisher', age=300)
    sig3 = lab.rpc('publisher', 'signmessage', lab.address('publisher'), canonical(expired))
    record('expired_challenge_rejected', not lab.consume_challenge(expired, sig3), 'Expiration enforced')
    forged = lab.challenge('publisher')
    badsig = lab.rpc('validator1', 'signmessage', lab.address('validator1'), canonical(forged))
    record('wrong_key_rejected', not lab.consume_challenge(forged, badsig), 'Validator cannot sign as publisher')
    # A valid sender lacking stream permission: tests the stream ACL specifically.
    try:
        lab.publish('publisher', 'decisions', 'unauthorized-' + uuid.uuid4().hex, {'label': 'REAL'})
        record('publisher_cannot_finalize', False, 'Unexpected write; inspect permissions')
    except RPCError as exc:
        record('publisher_cannot_finalize', not exc.ambiguous and exc.code is not None and 'permission' in str(exc).lower(), str(exc))
    permission = lab.rpc('authority', 'verifypermission', lab.address('publisher'), 'news.write')
    if not permission:
        raise LabError('Publisher is already revoked. Restore explicitly before running security-tests')
    try:
        permission_change(lab, 'publisher', False)
        effective = lab.rpc('publisher', 'verifypermission', lab.address('publisher'), 'news.write')
        record('revocation_effective', not effective, 'Confirmed change on publisher node')
        try:
            lab.publish('publisher', 'news', 'revoked-' + uuid.uuid4().hex, {'text': 'should fail'})
            record('revoked_write_rejected', False, 'Unexpected write')
        except RPCError as exc:
            record('revoked_write_rejected', not exc.ambiguous and exc.code is not None and 'permission' in str(exc).lower(), str(exc))
    finally:
        permission_change(lab, 'publisher', True)
    original = 'Classroom article version one.'
    record('changed_content_detected', digest(original) != digest(original + ' changed'), 'SHA-256 recomputation')
    sample_id = 'integrity-' + uuid.uuid4().hex
    submitted = lab.submit(original, sample_id)
    lab.wait([submitted['txid']])
    article = lab.news(sample_id, 'auditor')
    stored_hash = article['data']['json']['content_sha256']
    record('ledger_hash_matches_original', digest(original) == stored_hash, submitted['txid'])
    record('ledger_hash_rejects_modified_copy', digest(original + ' changed') != stored_hash, submitted['txid'])
    try:
        lab.submit(original, sample_id)
        record('gateway_duplicate_id_rejected', False, 'Unexpected duplicate')
    except LabError as exc:
        record('gateway_duplicate_id_rejected', 'Duplicate' in str(exc), str(exc))
    validators = {lab.address(r) for r in VALIDATORS}
    single = [{'txid': 'fixture', 'publishers': [lab.address('validator1')], 'confirmations': 1,
               'data': {'json': {'validator_address': lab.address('validator1'), 'news_id': 'fixture',
                                 'content_sha256': 'hash', 'label': 'REAL'}}}]
    record('single_validator_not_enough_local_policy',
           resolve_decision(single, validators, 'fixture', 'hash')['label'] == 'REVIEW', 'Policy-unit assertion, not chain consensus')
    result = {'captured_at': utc(), 'all_passed': all(c['passed'] for c in checks), 'checks': checks}
    write_json(lab.root / 'evidence' / 'security_tests.json', result)
    txid = lab.publish('authority', 'audit', 'security-' + uuid.uuid4().hex, result)
    lab.wait([txid])
    result['audit_txid'] = txid
    write_json(lab.root / 'evidence' / 'security_tests.json', result)
    return result


def benchmark(lab: Lab, args: argparse.Namespace) -> dict:
    if args.n < 1 or args.n > 100000 or args.workers < 1 or args.workers > 128:
        raise LabError('Use 1..100000 requests and 1..128 workers')
    if args.payload_bytes < 1 or args.payload_bytes > 65536 or args.confirmations < 1 or args.timeout < 1:
        raise LabError('Payload must be 1..65536 bytes; confirmations and timeout must be positive')
    if args.mode == 'pipeline' and not args.fixture_votes:
        raise LabError('Pipeline load uses fixture reviewers. Add --fixture-votes to acknowledge this is not human fact checking')
    require_ready(lab, need_model=(args.mode == 'pipeline'), permissions=True)
    snapshot = status(lab)
    if not snapshot.get('past_setup_phase') or not snapshot.get('shared_height_check', {}).get('same_hash'):
        raise LabError('Wait until all five nodes are synchronized beyond setup block 10, then retry')
    if any('error' in v for v in snapshot['nodes'].values()):
        raise LabError('All five roles must be running for benchmark')
    if args.mode == 'pipeline':
        lab.model()  # Validate model exists before launching workers.
    params = lab.rpc('authority', 'getblockchainparams')
    run_id = f'{args.mode}-{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S")}-{uuid.uuid4().hex[:8]}'
    evidence_dir = lab.root / 'evidence' / run_id
    evidence_dir.mkdir(parents=True)
    rows = load_dataset(HERE / 'demo_news.csv')
    samples = [r for r in rows if r['split'] == 'test'] or rows
    prepared = []
    for i in range(args.n):
        if args.mode == 'ledger':
            # ASCII padding gives exactly the requested CONTENT bytes; JSON and tx overhead are extra.
            body = ('x' * args.payload_bytes)
            payload = {'schema': 1, 'run_id': run_id, 'sequence': i, 'content': body,
                       'content_sha256': digest(body), 'nonce': f'{run_id}:{i}'}
            prepared.append(payload)
        else:
            prepared.append(samples[i % len(samples)])
    start_height = int(lab.rpc('auditor', 'getinfo')['blocks'])
    before_mempool = lab.rpc('auditor', 'getmempoolinfo')
    gate = threading.Event()
    clock: dict[str, float] = {}
    completed: list[dict] = []
    trace_lock = threading.Lock()
    trace = (evidence_dir / 'requests.jsonl').open('w', encoding='utf-8')

    def work(index: int) -> dict:
        gate.wait()
        service_start = time.perf_counter()
        txs: list[str] = []
        entry: dict[str, Any] = {'sequence': index, 'request_id': f'{run_id}-{index}',
                                 'status': 'success', 'txids': txs, 'error': None,
                                 'queue_ms': (service_start - clock['start']) * 1000}
        try:
            if args.mode == 'ledger':
                txs.append(lab.publish('publisher', 'benchmarks', [run_id, str(index)], prepared[index]))
            else:
                result = lab.pipeline(prepared[index], entry['request_id'], run_id, args.threshold, txlog=txs)
                entry['decision'] = result['decision']
        except RPCError as exc:
            entry.update(status='unknown' if exc.ambiguous else 'failed', error=str(exc))
        except Exception as exc:
            entry.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        end = time.perf_counter()
        entry.update(service_ms=(end - service_start) * 1000,
                     burst_response_ms=(end - clock['start']) * 1000)
        with trace_lock:
            trace.write(json.dumps(entry) + '\n')
            trace.flush()
        return entry

    try:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(work, i) for i in range(args.n)]
            clock['start'] = time.perf_counter()
            wall_start = utc()
            gate.set()  # All N logical requests arrive now; only workers requests run concurrently.
            for future in cf.as_completed(futures):
                completed.append(future.result())
                if len(completed) % max(1, args.n // 10) == 0:
                    print(f'Benchmark requests completed: {len(completed)}/{args.n}',
                          file=sys.stderr, flush=True)
            submission_end = time.perf_counter()
    finally:
        trace.close()
    completed.sort(key=lambda r: r['sequence'])
    txids = {txid for r in completed for txid in r['txids']}
    confirmed: set[str] = set()
    tx_observed: dict[str, dict] = {}
    # Confirmation measurement is intentionally AFTER submission: these are
    # observation upper bounds, not per-transaction inclusion latency.
    deadline = time.perf_counter() + args.timeout
    last_tip = None
    while time.perf_counter() < deadline:
        tip = lab.rpc('auditor', 'getblockchaininfo')
        marker = (tip.get('blocks'), tip.get('bestblockhash'))
        if marker != last_tip:
            last_tip = marker
            current = int(lab.rpc('auditor', 'getinfo')['blocks'])
            stable_height = current - args.confirmations + 1
            now_observed = time.perf_counter()
            observed_now: set[str] = set()
            # Rescan this run's block range after each tip change, so a short reorg
            # is not silently treated as permanent confirmation.
            for height in range(max(0, start_height), stable_height + 1):
                block = lab.rpc('auditor', 'getblock', height, 1)
                for tx in block.get('tx', []):
                    txid = tx if isinstance(tx, str) else tx['txid']
                    if txid in txids:
                        observed_now.add(txid)
                        tx_observed[txid] = {'block_height': height, 'block_hash': block['hash'],
                                            'observed_after_burst_ms': (time.perf_counter() - clock['start']) * 1000}
            confirmed = observed_now
        if confirmed == txids:
            break
        time.sleep(.25)
    confirmation_end = time.perf_counter()
    ok = [r for r in completed if r['status'] == 'success']
    fully_confirmed = [r for r in ok if r['txids'] and set(r['txids']) <= confirmed]
    submit_seconds = submission_end - clock['start']
    confirm_seconds = confirmation_end - clock['start']
    result = {
        'software_version': VERSION, 'run_id': run_id, 'mode': args.mode, 'started_at_utc': wall_start,
        'finished_at_utc': utc(), 'requested': args.n, 'workers': args.workers,
        'load_model': 'bounded-concurrency burst; every logical arrival at t0; not N independent machines',
        'payload_content_bytes': args.payload_bytes if args.mode == 'ledger' else None,
        'fixture_votes': args.fixture_votes if args.mode == 'pipeline' else False,
        'expected_txs_per_success': 1 if args.mode == 'ledger' else 5,
        'successes': len(ok), 'failures': sum(r['status'] == 'failed' for r in completed),
        'unknown_outcomes': sum(r['status'] == 'unknown' for r in completed),
        'known_broadcast_transactions': len(txids), 'confirmed_known_transactions': len(confirmed),
        'confirmed_complete_requests': len(fully_confirmed),
        'confirmation_target': args.confirmations, 'confirmation_observer': 'auditor',
        'confirmation_timeout_seconds_after_submission': args.timeout,
        'unconfirmed_known_transactions': sorted(txids - confirmed),
        'submission_seconds': submit_seconds, 'confirmation_observation_seconds': confirm_seconds,
        'successful_requests_per_second': len(ok) / submit_seconds,
        'known_broadcast_transactions_per_second': len(txids) / submit_seconds,
        'confirmed_complete_requests_per_second': len(fully_confirmed) / confirm_seconds,
        'confirmed_known_transactions_per_second': len(confirmed) / confirm_seconds,
        'success_rate': len(ok) / args.n,
        'service_latency_success_only': latency_stats([r['service_ms'] for r in ok]),
        'burst_response_latency_success_only': latency_stats([r['burst_response_ms'] for r in ok]),
        'queue_latency_all_requests': latency_stats([r['queue_ms'] for r in completed]),
        'confirmation_metric_note': 'Post-submission polling upper bound for batch completion; not per-tx confirmation latency.',
        'unknown_outcome_note': 'Unknown writes are NOT retried. Reconcile by run_id before drawing exact-count conclusions.',
        'error_examples': [r for r in completed if r['status'] != 'success'][:5],
        'parameters': params, 'mempool_before': before_mempool,
        'mempool_after': lab.rpc('auditor', 'getmempoolinfo'),
        'environment': {'platform': platform.platform(), 'python': sys.version,
                        'cpu_logical_count': os.cpu_count(), 'multichain_version': snapshot['nodes']['authority'].get('version'),
                        'topology': 'five processes, one host, loopback; not a distributed network benchmark'},
        'transaction_observations': tx_observed,
    }
    write_json(evidence_dir / 'summary.json', result)
    fields = ['sequence', 'request_id', 'status', 'queue_ms', 'service_ms', 'burst_response_ms', 'txids', 'error']
    with (evidence_dir / 'requests.csv').open('w', encoding='utf-8', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in completed:
            writer.writerow({**row, 'txids': ';'.join(row['txids'])})
    # Store only compact metadata, after the timer. The benchmark-summary tx is excluded.
    compact = {k: result[k] for k in ('run_id', 'mode', 'requested', 'successes', 'failures', 'unknown_outcomes',
                                      'submission_seconds', 'confirmation_observation_seconds')}
    compact['summary_sha256'] = hashlib.sha256((evidence_dir / 'summary.json').read_bytes()).hexdigest()
    try:
        summary_tx = lab.publish('authority', 'audit', run_id, compact)
        write_json(evidence_dir / 'summary_anchor.json', {'txid': summary_tx, 'excluded_from_metrics': True})
    except LabError as exc:
        write_json(evidence_dir / 'summary_anchor.json', {'error': str(exc), 'excluded_from_metrics': True})
    return {k: v for k, v in result.items() if k not in ('transaction_observations', 'parameters')}


def demo(lab: Lab) -> dict:
    rows = load_dataset(HERE / 'demo_news.csv')
    real = next(r for r in rows if r['label'] == 'REAL')
    fake = next(r for r in rows if r['label'] == 'FAKE')
    run_id = 'demo-' + uuid.uuid4().hex[:10]
    out = []
    for name, row, other in [('real', real, None), ('fake', fake, None), ('disagreement', real, 'FAKE')]:
        news_id = f'{run_id}-{name}'
        result = lab.pipeline(row, news_id, run_id, second_label=other)
        lab.wait(result['txids'])
        proof = lab.inspect(news_id)
        result['audit_pass'] = proof['audit_pass']
        write_json(lab.root / 'evidence' / f'{news_id}.json', proof)
        out.append(result)
    result = {'run_id': run_id, 'cases': out,
              'all_passed': all(c['audit_pass'] and c['decision'] == expected
                                for c, expected in zip(out, ('REAL', 'FAKE', 'REVIEW'))),
              'notice': 'Votes follow classroom labels to test workflow; these are not independently verified real news items.'}
    write_json(lab.root / 'evidence' / 'demo.json', result)
    return result


def reputation(lab: Lab) -> dict:
    """Derived classroom credibility; never equate transferable tokens to reputation."""
    start = 0
    records = []
    while True:
        page = lab.rpc('auditor', 'liststreamitems', 'decisions', False, 200, start)
        records.extend(page)
        if len(page) < 200:
            break
        start += len(page)
    counts = collections.Counter()
    seen = set()
    for item in records:
        data = item.get('data', {}).get('json', {})
        news_id = data.get('news_id')
        if (item.get('confirmations', 0) >= 1 and item.get('publishers') == [lab.address('authority')]
                and news_id and news_id not in seen):
            counts[data.get('label', 'REVIEW')] += 1
            seen.add(news_id)
    score = max(0, min(100, 50 + 5 * counts['REAL'] - 10 * counts['FAKE']))
    return {'publisher': lab.address('publisher'), 'score': score, 'counts': dict(counts),
            'formula': 'clip(50 + 5*REAL - 10*FAKE, 0, 100)',
            'scope': 'Teaching formula over authority-issued decisions. Not the paper formula; not a truth guarantee.',
            'note': 'Descriptive only: this score does not dynamically change mining or publishing permissions.'}


def reconcile(lab: Lab, run_id: str, stream: str) -> dict:
    records = lab.items('auditor', stream, run_id)
    confirmed = [r for r in records if r.get('confirmations', 0) >= 1]
    invalid = []
    seen = collections.Counter()
    for item in confirmed:
        data = item.get('data', {}).get('json', {})
        body = data.get('content', '') if stream == 'benchmarks' else data.get('text', '')
        identity = data.get('sequence') if stream == 'benchmarks' else data.get('news_id')
        seen[str(identity)] += 1
        if (item.get('publishers') != [lab.address('publisher')]
                or data.get('run_id') != run_id or digest(body) != data.get('content_sha256')):
            invalid.append(item['txid'])
    result = {'run_id': run_id, 'stream': stream, 'items_seen': len(records),
              'confirmed_items': len(confirmed), 'distinct_confirmed_transactions': len({r['txid'] for r in confirmed}),
              'distinct_logical_ids': len(seen), 'duplicate_ids': {k:v for k,v in seen.items() if v > 1},
              'invalid_records': invalid, 'captured_at': utc(),
              'scope': 'Ledger records on auditor; pipeline mode counts submitted articles, not finalized decisions.'}
    safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', run_id)
    write_json(lab.root / 'evidence' / ('reconcile-' + safe_name + '.json'), result)
    return result


def capture(lab: Lab) -> dict:
    status(lab)
    items = []
    for path in sorted((lab.root / 'evidence').rglob('*.json')):
        # Only evidence; never read conf files or wallets into the evidence page.
        text = path.read_text(encoding='utf-8')
        items.append(f'<section><h2>{html.escape(str(path.relative_to(lab.root)))}</h2><pre>{html.escape(text)}</pre></section>')
    page = ('<!doctype html><meta charset="utf-8"><title>FakeMedia execution evidence</title>'
            '<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;border:1px solid #bbb;padding:16px;font-size:13px}'
            'section{break-inside:avoid}h1{font-size:28px}</style>'
            '<h1>FakeMedia - captured execution evidence</h1><p>Actual JSON output from this workspace. '
            'Screenshots must be captured on the student machine. Credentials and wallet keys are excluded.</p>'
            + ''.join(items))
    path = lab.root / 'evidence.html'
    path.write_text(page, encoding='utf-8')
    return {'evidence_page': str(path), 'json_sections': len(items)}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--version', action='version', version=VERSION)
    p.add_argument('--workspace', type=Path, default=HERE / 'workspace', help='Put BEFORE the subcommand')
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('setup', help='Create a NEW isolated five-node lab')
    s.add_argument('--bin-dir', required=True)
    s.add_argument('--auto-ports', action='store_true', help='Choose unused local port ranges if defaults are busy')
    s.add_argument('--chain', default='fakenews')
    s.add_argument('--rpc-base', type=int, default=8441)
    s.add_argument('--p2p-base', type=int, default=7441)
    s.add_argument('--block-time', type=int, default=2)
    s.add_argument('--block-size', type=int, default=8388608)
    s.add_argument('--diversity', type=float, default=.6)
    s = sub.add_parser('repair', help='Resume incomplete setup in-place; never delete wallets or chain data')
    s.add_argument('--bin-dir', help='Update path to installed MultiChain binaries')
    for command in ('start', 'stop'):
        s = sub.add_parser(command)
        s.add_argument('--role', choices=ROLES)
    for command in ('status', 'doctor', 'demo', 'security-tests', 'capture', 'reputation'):
        sub.add_parser(command)
    s = sub.add_parser('train')
    s.add_argument('--dataset', type=Path, default=HERE / 'demo_news.csv')
    s.add_argument('--epochs', type=int, default=250)
    s.add_argument('--seed', type=int, default=42)
    s = sub.add_parser('nlp')
    s.add_argument('--text', required=True)
    s.add_argument('--threshold', type=float, default=.35)
    s = sub.add_parser('submit')
    s.add_argument('--text', required=True)
    s.add_argument('--id')
    s = sub.add_parser('analyze')
    s.add_argument('--id', required=True)
    s.add_argument('--threshold', type=float, default=.35)
    s = sub.add_parser('vote')
    s.add_argument('--role', choices=VALIDATORS, required=True)
    s.add_argument('--id', required=True)
    s.add_argument('--label', choices=('REAL', 'FAKE', 'REVIEW'), required=True)
    s.add_argument('--reason', required=True)
    for command in ('finalize', 'inspect'):
        s = sub.add_parser(command)
        s.add_argument('--id', required=True)
    for command in ('revoke', 'restore'):
        s = sub.add_parser(command)
        s.add_argument('--role', choices=('publisher', *VALIDATORS), required=True)
    s = sub.add_parser('verify-file')
    s.add_argument('--id', required=True)
    s.add_argument('--file', type=Path, required=True)
    s = sub.add_parser('benchmark')
    s.add_argument('--mode', choices=('ledger', 'pipeline'), default='ledger')
    s.add_argument('--n', type=int, default=1000)
    s.add_argument('--workers', type=int, default=10)
    s.add_argument('--payload-bytes', type=int, default=1024)
    s.add_argument('--confirmations', type=int, default=1)
    s.add_argument('--timeout', type=float, default=180)
    s.add_argument('--threshold', type=float, default=.35)
    s.add_argument('--fixture-votes', action='store_true')
    s = sub.add_parser('reconcile')
    s.add_argument('--run-id', required=True)
    s.add_argument('--stream', choices=('benchmarks', 'news'), default='benchmarks')
    s = sub.add_parser('reward', help='Demonstrate explicit transfer; NOT a truth/credibility score')
    s.add_argument('--amount', type=int, default=1)
    s = sub.add_parser('rpc', help='Pass exact RPC parameters as JSON; operator-level access')
    s.add_argument('--role', choices=ROLES, default='authority')
    s.add_argument('method')
    s.add_argument('--params', default='[]')
    s.add_argument('--params-file', type=Path)
    return p


def dispatch(root: Path, args: argparse.Namespace) -> Any:
    if hasattr(args, 'threshold') and not 0 <= args.threshold <= 1:
        raise LabError('Threshold must be between 0 and 1')
    if args.command == 'setup':
        return setup(root, args)
    if args.command == 'train':
        if args.epochs < 1:
            raise LabError('Epochs must be positive')
        return train_model(root, args.dataset, args.epochs, args.seed)
    if args.command == 'nlp':
        saved = read_json(root / 'model.json')
        return TeachingModel(saved['training'], saved['qtable']).predict(args.text, args.threshold)
    lab = Lab(root)
    if args.command == 'repair': return repair(lab, args.bin_dir)
    if args.command == 'doctor': return doctor(lab)
    if args.command == 'status': return status(lab)
    if args.command == 'reputation': return reputation(lab)
    if args.command == 'reconcile': return reconcile(lab, args.run_id, args.stream)
    if args.command == 'start': return start(lab, (args.role,) if args.role else ROLES)
    if args.command == 'stop':
        return stop(lab, (args.role,) if args.role else tuple(reversed(ROLES)))
    if args.command not in READ_COMMANDS and args.command not in ('benchmark',):
        require_ready(lab, need_model=args.command in ('demo', 'analyze'))
    if args.command == 'demo': return demo(lab)
    if args.command == 'security-tests': return security_tests(lab)
    if args.command == 'capture': return capture(lab)
    if args.command == 'benchmark': return benchmark(lab, args)
    if args.command == 'submit':
        result = lab.submit(args.text, args.id)
        lab.wait([result['txid']])
        return result
    if args.command == 'analyze':
        result = lab.analyze(args.id, args.threshold)
        lab.wait([result['txid']])
        return result
    if args.command == 'vote':
        result = lab.vote(args.role, args.id, args.label, args.reason)
        lab.wait([result['txid']])
        return result
    if args.command == 'finalize':
        result = lab.finalize(args.id)
        lab.wait([result['txid']])
        return result
    if args.command == 'inspect': return lab.inspect(args.id)
    if args.command in ('revoke', 'restore'):
        return permission_change(lab, args.role, args.command == 'restore')
    if args.command == 'verify-file':
        article = lab.news(args.id, 'auditor')
        expected = article['data']['json']['content_sha256']
        actual = hashlib.sha256(args.file.read_bytes()).hexdigest()
        return {'match': actual == expected, 'expected_sha256': expected, 'actual_sha256': actual,
                'note': 'Hashes exact UTF-8 text bytes; BOM and newline changes also change the hash.'}
    if args.command == 'reward':
        if args.amount < 1: raise LabError('Amount must be positive')
        txid = lab.rpc('authority', 'sendassetfrom', lab.address('authority'), lab.address('publisher'), 'NewsCredit', args.amount)
        lab.wait([txid])
        return {'txid': txid, 'publisher_balances': lab.rpc('publisher', 'getaddressbalances', lab.address('publisher')),
                'note': 'Transferable demonstration token, NOT reputation or native mining rewards.'}
    if args.command == 'rpc':
        params = read_json(args.params_file) if args.params_file else json.loads(args.params)
        if not isinstance(params, list): raise LabError('RPC params must be a JSON array')
        return lab.rpc(args.role, args.method, *params)
    raise LabError('Unknown command')


def main() -> int:
    args = parser().parse_args()
    root = args.workspace.resolve()
    try:
        unlocked = args.command in READ_COMMANDS
        if args.command == 'rpc' and not read_only_rpc(args.method):
            unlocked = False
        lock = contextlib.nullcontext() if unlocked else WorkspaceLock(root)
        with lock:
            result = dispatch(root, args)
        emit(result)
        if isinstance(result, dict) and result.get('all_passed') is False:
            return 2
        if args.command == 'benchmark' and (result.get('failures', 0)
                or result.get('unknown_outcomes', 0)
                or result.get('confirmed_complete_requests', 0) != args.n):
            return 2
        return 0
    except KeyboardInterrupt:
        print('Interrupted. Inspect transaction history before retrying any write.', file=sys.stderr)
        return 130
    except (LabError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
