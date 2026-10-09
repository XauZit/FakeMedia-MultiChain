"""Regression tests with mocks. No MultiChain daemon is used or simulated as evidence."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import lab


class WaitRegressionTests(unittest.TestCase):
    def node(self, answers):
        node = lab.Lab.__new__(lab.Lab)
        node.rpc = MagicMock(side_effect=answers)
        return node

    def test_multichain_710_then_confirmed(self):
        node = self.node([lab.RPCError('No information available about transaction', -710),
                          {'confirmations': 0}, {'confirmations': 1}])
        with patch('lab.time.sleep'):
            node.wait(['known-tx'], timeout=2)
        self.assertEqual(node.rpc.call_count, 3)
        self.assertEqual({x.args[1] for x in node.rpc.call_args_list}, {'getrawtransaction'})

    def test_legacy_5_then_confirmed(self):
        node = self.node([lab.RPCError('not known', -5), {'confirmations': 1}])
        with patch('lab.time.sleep'):
            node.wait(['known-tx'], timeout=2)

    def test_warmup_then_confirmed(self):
        node = self.node([lab.RPCError('warming up', -28), {'confirmations': 2}])
        with patch('lab.time.sleep'):
            node.wait(['known-tx'], confirmations=2, timeout=2)

    def test_permission_failure_is_not_swallowed(self):
        node = self.node([lab.RPCError('denied', -704)])
        with self.assertRaises(lab.RPCError):
            node.wait(['known-tx'])
        self.assertEqual(node.rpc.call_count, 1)

    def test_invalid_parameter_is_not_swallowed(self):
        node = self.node([lab.RPCError('bad parameter', -8)])
        with self.assertRaises(lab.RPCError):
            node.wait(['known-tx'])

    def test_transport_read_can_be_polled(self):
        node = self.node([lab.RPCError('connection reset', transport=True), {'confirmations': 1}])
        with patch('lab.time.sleep'):
            node.wait(['known-tx'], timeout=2)

    def test_empty_wait_does_not_call_rpc(self):
        node = self.node([])
        node.wait([])
        node.rpc.assert_not_called()

    def test_invalid_confirmation_target(self):
        node = self.node([])
        with self.assertRaises(lab.LabError):
            node.wait(['known-tx'], confirmations=0)

    def test_timeout_includes_pending_txid_and_role(self):
        node = self.node([])
        node.rpc = MagicMock(side_effect=lab.RPCError('not yet known', -710))
        with self.assertRaisesRegex(lab.LabError, 'auditor.*known-tx'):
            node.wait(['known-tx'], timeout=.001)

    def test_only_reads_are_retried_by_lab_rpc(self):
        node = lab.Lab.__new__(lab.Lab)
        client = MagicMock()
        node.clients = {'auditor': client}
        client.call.side_effect = [lab.RPCError('transport', transport=True), {'blocks': 20}]
        with patch('lab.time.sleep'):
            self.assertEqual(node.rpc('auditor', 'getinfo'), {'blocks': 20})
        self.assertEqual(client.call.call_count, 2)

    def test_write_never_retried_by_lab_rpc(self):
        node = lab.Lab.__new__(lab.Lab)
        client = MagicMock()
        node.clients = {'publisher': client}
        client.call.side_effect = lab.RPCError('unknown', ambiguous=True, transport=True)
        with self.assertRaises(lab.RPCError):
            node.rpc('publisher', 'publishfrom', 'address', 'news', 'key', {})
        self.assertEqual(client.call.call_count, 1)


class ReadinessFixture:
    """Only canned RPC answers for application preflight unit tests."""
    def __init__(self, root):
        self.root = Path(root)
        self.chain = 'fakenews'
        self.cfg = {'setup_complete': True, 'chain': self.chain, 'genesis_hash': 'g',
                    'asset_issuance_txid': 'asset-tx',
                    'nodes': {r: {'address': r, 'rpc_port': 19000+i,
                                  'p2p_port': 18000+i, 'datadir': str(self.root/r)}
                              for i, r in enumerate(lab.ROLES)}}
        self.missing = set()
        self.opened = set()
        self.unsubscribed = set()
        self.revoked = set()
        self.offline = set()
        self.calls = []
        self.clients = {r: MagicMock() for r in lab.ROLES}
        self.model = MagicMock(return_value=(object(), 'model-hash'))
        self.membership = MagicMock(return_value={'event': 'ENROLL'})
        self.save = MagicMock()

    def address(self, role):
        return self.cfg['nodes'][role]['address']

    def rpc(self, role, method, *args):
        self.calls.append((role, method, args))
        if role in self.offline:
            raise lab.RPCError('offline', transport=True)
        if method == 'getinfo':
            return {'chainname': 'fakenews', 'blocks': 30, 'version': '2.3.3'}
        if method == 'validateaddress':
            return {'ismine': args[0] == role}
        if method == 'getblockhash':
            return 'g' if args[0] == 0 else 'block-hash'
        if method == 'liststreams':
            return [{'name': s, 'restrict': {'write': s not in self.opened},
                     'subscribed': s not in self.unsubscribed, 'synchronized': True}
                    for s in lab.STREAMS if s not in self.missing]
        if method == 'listminers':
            return [{'address': r, 'permitted': (r, 'mine') not in self.revoked,
                     'islocal': r == role, 'diversitywaitblocks': 0}
                    for r in ('authority', *lab.VALIDATORS)]
        if method == 'verifypermission':
            permission = args[1]
            if (role, permission) in self.revoked:
                return False
            if '.' in permission:
                return role == 'authority' or role in lab.WRITERS[permission.split('.')[0]]
            return role == 'authority' or (permission == 'mine' and role in lab.VALIDATORS)
        if method == 'getassetinfo':
            return {'issuetxid': 'asset-tx'}
        if method == 'stop':
            return 'MultiChain server stopping'
        raise AssertionError(f'Unexpected canned RPC: {role}, {method}, {args}')


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.node = ReadinessFixture(self.tmp.name)

    def test_healthy_fixture(self):
        self.assertTrue(lab.doctor(self.node)['all_passed'])

    def test_missing_stream_is_not_ready(self):
        self.node.missing.add('benchmarks')
        result = lab.doctor(self.node)
        self.assertFalse(result['all_passed'])
        self.assertIn('benchmarks', result['nodes']['publisher']['missing_streams'])

    def test_unsubscribed_stream_is_not_ready(self):
        self.node.unsubscribed.add('news')
        self.assertFalse(lab.doctor(self.node)['all_passed'])

    def test_open_stream_is_not_ready(self):
        self.node.opened.add('decisions')
        self.assertFalse(lab.doctor(self.node)['all_passed'])

    def test_revoked_writer_fails_full_preflight(self):
        self.node.revoked.add(('publisher', 'benchmarks.write'))
        self.assertFalse(lab.doctor(self.node)['all_passed'])

    def test_structure_check_allows_explicit_permission_restore(self):
        self.node.revoked.add(('publisher', 'news.write'))
        lab.require_ready(self.node, permissions=False)

    def test_missing_model_fails_model_preflight(self):
        self.node.model.side_effect = lab.LabError('train first')
        self.assertFalse(lab.doctor(self.node)['all_passed'])

    def test_ledger_preflight_does_not_require_model(self):
        self.node.model.side_effect = lab.LabError('train first')
        lab.require_ready(self.node, need_model=False)

    def test_offline_role_is_not_ready(self):
        self.node.offline.add('validator2')
        self.assertFalse(lab.doctor(self.node)['all_passed'])

    def test_incomplete_setup_sends_no_workload(self):
        self.node.cfg['setup_complete'] = False
        args = SimpleNamespace(n=1000, workers=10, payload_bytes=1024, confirmations=1,
                               timeout=300, mode='ledger', fixture_votes=False)
        with self.assertRaisesRegex(lab.LabError, 'Setup is incomplete'):
            lab.benchmark(self.node, args)
        self.assertEqual(self.node.calls, [])

    def test_doctor_reports_incomplete_even_when_nodes_run(self):
        self.node.cfg['setup_complete'] = False
        result = lab.doctor(self.node)
        self.assertFalse(result['all_passed'])
        self.assertFalse(result['setup_complete'])

    def test_completed_repair_does_not_restore_permissions(self):
        with patch('lab.start'), patch('lab.doctor', return_value={'all_passed': False}), \
                patch('lab.complete_setup') as complete:
            result = lab.repair(self.node)
        complete.assert_not_called()
        self.assertIn('No permissions', result['note'])

    def test_start_does_not_launch_a_duplicate(self):
        with patch('lab.is_ready', return_value=True), patch('lab.wait_ready'), \
                patch('lab.status', return_value={}), patch('lab.launch') as launch:
            lab.start(self.node, lab.ROLES)
        launch.assert_not_called()

    def test_shutdown_waits_for_listener_to_close(self):
        with patch('lab.is_ready', return_value=True), \
                patch('lab.node_listeners', side_effect=[[19000], []]) as listener, \
                patch('lab.time.sleep'):
            result = lab.stop(self.node, ('authority',), timeout=2)
        self.assertTrue(result['all_passed'])
        self.assertEqual(result['nodes']['authority']['status'], 'stopped')
        self.assertEqual(listener.call_count, 2)

    def test_stopped_node_is_not_force_killed(self):
        with patch('lab.is_ready', return_value=False), patch('lab.node_listeners', return_value=[]):
            result = lab.stop(self.node, ('authority',))
        self.assertTrue(result['all_passed'])
        self.assertFalse(any(c[1] == 'stop' for c in self.node.calls))

    def test_foreign_listener_is_not_stopped(self):
        with patch('lab.is_ready', return_value=False), patch('lab.node_listeners', return_value=[19000]):
            result = lab.stop(self.node, ('authority',))
        self.assertFalse(result['all_passed'])
        self.assertFalse(any(c[1] == 'stop' for c in self.node.calls))


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_reuses_existing_asset_and_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conf = root/'authority'/'fakenews'/'multichain.conf'
            conf.parent.mkdir(parents=True)
            (conf.parent/'params.dat').write_text('existing params')
            (root/'model.json').write_text('{}')
            node = MagicMock()
            node.root, node.chain = root, 'fakenews'
            node.cfg = {'setup_complete': False,
                        'nodes': {r: {'conf': str(conf)} for r in lab.ROLES}}
            node.enroll.side_effect = lambda r: 'enroll-'+r
            def rpc(role, method, *args):
                if method == 'getstreaminfo':
                    return {'createtxid': 'create-'+args[0], 'restrict': {'write': True}}
                if method == 'liststreams':
                    return [{'subscribed': True}]
                if method == 'getassetinfo':
                    return {'issuetxid': 'existing-asset', 'issueqty': 1000, 'open': False}
                if method == 'getblockchainparams':
                    return {'target-block-time': 2}
                if method == 'subscribe':
                    return None
                raise AssertionError(f'Unexpected bootstrap RPC: {method}')
            node.rpc.side_effect = rpc
            with patch('lab.ensure_network'), patch('lab.ensure_grant', return_value=None), \
                    patch('lab.doctor', return_value={'all_passed': True}), patch('lab.status'):
                lab.complete_setup(node)
            methods = [c.args[1] for c in node.rpc.call_args_list]
            self.assertNotIn('create', methods)
            self.assertNotIn('issue', methods)
            self.assertNotIn('issuemore', methods)
            self.assertTrue(node.cfg['setup_complete'])
            self.assertEqual(node.cfg['asset_issuance_txid'], 'existing-asset')
            self.assertEqual((conf.parent/'params.dat').read_text(), 'existing params')


    def test_bootstrap_creates_only_missing_entities_and_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conf = root/'authority'/'fakenews'/'multichain.conf'
            conf.parent.mkdir(parents=True)
            (conf.parent/'params.dat').write_text('preserved chain parameters')
            (root/'model.json').write_text('{}')
            node = MagicMock()
            node.root, node.chain = root, 'fakenews'
            node.cfg = {'setup_complete': False,
                        'nodes': {r: {'conf': str(conf)} for r in lab.ROLES}}
            node.enroll.side_effect = lambda r: 'enroll-'+r
            state = {'streams': {}, 'asset': None}
            def rpc(role, method, *args):
                if method == 'getstreaminfo':
                    if args[0] not in state['streams']:
                        raise lab.RPCError('stream not found', -708)
                    return state['streams'][args[0]]
                if method == 'create':
                    state['streams'][args[1]] = {'createtxid': 'create-'+args[1],
                                                  'restrict': {'write': True}}
                    return 'create-'+args[1]
                if method == 'liststreams':
                    return [{'subscribed': True}]
                if method == 'getassetinfo':
                    if state['asset'] is None:
                        raise lab.RPCError('asset not found', -708)
                    return state['asset']
                if method == 'issue':
                    state['asset'] = {'issuetxid': 'new-asset', 'issueqty': 1000, 'open': False}
                    return 'new-asset'
                if method == 'getblockchainparams':
                    return {'target-block-time': 2}
                if method == 'subscribe':
                    return None
                raise AssertionError(f'Unexpected bootstrap RPC: {method}')
            node.rpc.side_effect = rpc
            with patch('lab.ensure_network'), patch('lab.ensure_grant', return_value=None), \
                    patch('lab.doctor', return_value={'all_passed': True}), patch('lab.status'):
                lab.complete_setup(node)
                node.cfg['setup_complete'] = False  # Lost completion marker, not lost entities.
                lab.complete_setup(node)
            methods = [c.args[1] for c in node.rpc.call_args_list]
            self.assertEqual(methods.count('create'), 7)
            self.assertEqual(methods.count('issue'), 1)
            self.assertEqual(node.cfg['asset_issuance_txid'], 'new-asset')
            self.assertTrue(node.cfg['setup_complete'])

    def test_demo_failure_is_reflected_in_exit_check_field(self):
        with tempfile.TemporaryDirectory() as directory:
            node = MagicMock()
            node.root = Path(directory)
            node.pipeline.side_effect = [
                {'news_id': 'n'+str(i), 'decision': label, 'txids': ['t'+str(i)]}
                for i, label in enumerate(('REAL', 'FAKE', 'REVIEW'))]
            node.inspect.side_effect = [{'audit_pass': True}, {'audit_pass': False}, {'audit_pass': True}]
            result = lab.demo(node)
            self.assertFalse(result['all_passed'])

    def test_ensure_grant_does_not_regrant_existing_permission(self):
        node = MagicMock()
        node.rpc.return_value = True
        self.assertIsNone(lab.ensure_grant(node, 'publisher', 'connect,send,receive'))
        self.assertTrue(all(c.args[1] == 'verifypermission' for c in node.rpc.call_args_list))

    def test_setup_will_not_overwrite_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'lab.json').write_text('{"preserve":true}')
            with self.assertRaisesRegex(lab.LabError, 'Workspace already exists'):
                lab.setup(root, SimpleNamespace())
            self.assertEqual((root/'lab.json').read_text(), '{"preserve":true}')

    def test_missing_workspace_has_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(lab.LabError, 'No lab.json in workspace'):
                lab.Lab(Path(directory))

    def test_closed_stream_2x_and_legacy_fields(self):
        self.assertTrue(lab.stream_is_closed({'restrict': {'write': True}}))
        self.assertTrue(lab.stream_is_closed({'open': False}))
        self.assertFalse(lab.stream_is_closed({'restrict': {'write': False}}))
        self.assertFalse(lab.stream_is_closed({}))

    def test_mutating_getnewaddress_is_not_read_only(self):
        self.assertFalse(lab.read_only_rpc('getnewaddress'))
        self.assertFalse(lab.read_only_rpc('publishfrom'))
        self.assertTrue(lab.read_only_rpc('getinfo'))

    def test_rpc_error_includes_numeric_code(self):
        self.assertIn('-710', str(lab.RPCError('not found', -710)))

    def test_read_transport_does_not_claim_unknown_write(self):
        with tempfile.TemporaryDirectory() as directory:
            conf = Path(directory)/'multichain.conf'
            conf.write_text('rpcuser=unit\nrpcpassword=unit\nrpcport=65534\n')
            rpc = lab.RPC(conf, timeout=.1)
            with patch('http.client.HTTPConnection.request', side_effect=ConnectionResetError):
                with self.assertRaises(lab.RPCError) as caught:
                    rpc.call('getinfo')
            self.assertTrue(caught.exception.transport)
            self.assertFalse(caught.exception.ambiguous)
            self.assertNotIn('write outcome may be unknown', str(caught.exception))


if __name__ == '__main__':
    unittest.main(verbosity=2)
