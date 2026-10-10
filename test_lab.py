"""Local unit tests. These tests do NOT execute a MultiChain daemon."""
import copy
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import lab


class PureTests(unittest.TestCase):
    def test_sha256_known_vector(self):
        self.assertEqual(lab.digest('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')
    def test_tamper_changes_hash(self):
        self.assertNotEqual(lab.digest('message'), lab.digest('message!'))
    def test_canonical_key_order(self):
        self.assertEqual(lab.canonical({'b':2,'a':1}), lab.canonical({'a':1,'b':2}))
    def test_percentile_empty(self): self.assertIsNone(lab.percentile([], .95))
    def test_percentile_single(self): self.assertEqual(lab.percentile([5], .95), 5)
    def test_percentile_interpolation(self): self.assertAlmostEqual(lab.percentile([0,10,20,30], .5),15)
    def test_stats_samples(self): self.assertEqual(lab.latency_stats([1,2,3])['samples'],3)
    def test_negation_retained(self): self.assertIn('not', lab.tokenize('This is not approved.'))
    def test_tokenization(self): self.assertEqual(lab.tokenize('The NEWS, and DATA!'), ['news','data'])
    def test_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.json';lab.write_json(path,{'hello':'world'})
            self.assertEqual(lab.read_json(path),{'hello':'world'})
    def test_writer_lock_excludes_second_writer(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with lab.WorkspaceLock(root):
                with self.assertRaises(lab.LabError):
                    with lab.WorkspaceLock(root):pass
            self.assertFalse((root/'writer.lock').exists())


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.addrs={'v1','v2'}
        self.votes=[self.vote('v1','REAL','t1'),self.vote('v2','REAL','t2')]
    @staticmethod
    def vote(signer,label,txid):
        return {'txid':txid,'publishers':[signer],'confirmations':2,
                'data':{'json':{'validator_address':signer,'news_id':'n1','content_sha256':'h1','label':label}}}
    def result(self,votes):return lab.resolve_decision(votes,self.addrs,'n1','h1')
    def test_two_agree_real(self):self.assertEqual(self.result(self.votes)['label'],'REAL')
    def test_two_agree_fake(self):self.assertEqual(self.result([self.vote('v1','FAKE','a'),self.vote('v2','FAKE','b')])['label'],'FAKE')
    def test_one_missing(self):self.assertEqual(self.result(self.votes[:1])['label'],'REVIEW')
    def test_disagreement(self):
        self.votes[1]['data']['json']['label']='FAKE'
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_abstention(self):
        self.votes[1]['data']['json']['label']='REVIEW'
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_duplicate_vote(self):self.assertEqual(self.result(self.votes+[copy.deepcopy(self.votes[0])])['label'],'REVIEW')
    def test_impersonation(self):
        self.votes[0]['data']['json']['validator_address']='v2'
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_wrong_hash(self):
        self.votes[0]['data']['json']['content_sha256']='changed'
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_wrong_news_id(self):
        self.votes[0]['data']['json']['news_id']='another'
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_unconfirmed(self):
        self.votes[0]['confirmations']=0
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_wrong_publisher(self):
        self.votes[0]['publishers']=['attacker']
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_multiple_publishers_fail_closed(self):
        self.votes[0]['publishers']=['v1','v2']
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_invalid_label(self):
        self.votes[0]['data']['json']['label']='APPROVE'
        self.assertEqual(self.result(self.votes)['label'],'REVIEW')
    def test_permutation_invariant(self):
        self.assertEqual(self.result(self.votes),self.result(list(reversed(self.votes))))


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.rows=lab.load_dataset(lab.HERE/'demo_news.csv')
        self.train=[r for r in self.rows if r['split']=='train']
    def test_dataset_counts(self):self.assertEqual((len(self.train),len(self.rows)),(24,32))
    def test_no_exact_train_test_overlap(self):
        train={' '.join(lab.tokenize(r['text'])) for r in self.train}
        test={' '.join(lab.tokenize(r['text'])) for r in self.rows if r['split']=='test'}
        self.assertFalse(train & test)
    def test_reproducible_q_learning(self):
        a=lab.TeachingModel(self.train);b=lab.TeachingModel(self.train)
        a.train(seed=42);b.train(seed=42);self.assertEqual(a.qtable,b.qtable)
    def test_unknown_words_abstain(self):
        m=lab.TeachingModel(self.train);m.train()
        self.assertEqual(m.predict('quux xyzzy blorb')['label'],'REVIEW')
    def test_similarities_are_bounded(self):
        m=lab.TeachingModel(self.train)
        for row in self.rows:
            r,f=m.evidence(row['text']);self.assertTrue(-1e-10<=r<=1.0000001 and -1e-10<=f<=1.0000001)
    def test_cosine_identity(self):
        m=lab.TeachingModel(self.train)
        self.assertAlmostEqual(m.evidence(self.train[0]['text'])[0],1.0)
    def test_training_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            stats=lab.train_model(Path(d),lab.HERE/'demo_news.csv')
            self.assertEqual(stats['train_rows'],24)
            self.assertTrue((Path(d)/'model.json').is_file())
            self.assertIn('test_coverage',stats)


class RPCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                cls.calls.append(data)
                if data['method']=='fail':
                    answer={'id':data['id'],'result':None,'error':{'code':-704,'message':'permission denied'}}
                else:answer={'id':data['id'],'result':data['params'],'error':None}
                raw=json.dumps(answer).encode();self.send_response(200)
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def client(self,path):
        path.write_text(f'rpcuser=test\nrpcpassword=not-a-real-credential\nrpcport={self.server.server_port}\n')
        return lab.RPC(path)
    def test_parameter_types_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            rpc=self.client(Path(d)/'conf')
            self.assertEqual(rpc.call('echo',True,3,{'x':[1,2]}),[True,3,{'x':[1,2]}])
    def test_rpc_error_not_transport_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            rpc=self.client(Path(d)/'conf')
            with self.assertRaises(lab.RPCError) as ctx:rpc.call('fail')
            self.assertEqual(ctx.exception.code,-704);self.assertFalse(ctx.exception.ambiguous)
    def test_permission_denied_recognizes_multichain_stream_rejection(self):
        # Exact MultiChain 2.3.3 response to an unauthorized stream write.
        stream=lab.RPCError('publishfrom: Publishing in this stream is not allowed from this address',-704)
        self.assertTrue(lab.permission_denied(stream))
        self.assertTrue(lab.permission_denied(lab.RPCError('permission denied',-1)))
        self.assertFalse(lab.permission_denied(lab.RPCError('Invalid parameter',-8)))
        self.assertFalse(lab.permission_denied(lab.RPCError('permission denied',-704,ambiguous=True)))
        self.assertFalse(lab.permission_denied(lab.RPCError('connection refused: permission',None,transport=True)))
    def test_no_retry_on_error(self):
        with tempfile.TemporaryDirectory() as d:
            rpc=self.client(Path(d)/'conf');before=len(self.calls)
            with self.assertRaises(lab.RPCError):rpc.call('fail')
            self.assertEqual(len(self.calls)-before,1)
    def test_remote_rpc_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'conf'
            path.write_text('rpcuser=x\nrpcpassword=y\nrpcport=8441\nrpcconnect=example.com\n')
            with self.assertRaises(lab.LabError):lab.RPC(path)
    def test_transport_failure_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'conf';path.write_text('rpcuser=x\nrpcpassword=y\nrpcport=65534\n')
            rpc=lab.RPC(path,timeout=.1)
            with patch('http.client.HTTPConnection.request',side_effect=ConnectionResetError):
                with self.assertRaises(lab.RPCError) as ctx:rpc.call('publishfrom','a','s','k',{})
            self.assertTrue(ctx.exception.ambiguous)


if __name__=='__main__':unittest.main(verbosity=2)
