"""Canned-RPC regression tests, NOT native MultiChain integration tests."""
import tempfile
import unittest
from unittest.mock import MagicMock
import lab
from test_recovery import ReadinessFixture


class MiningFixture(ReadinessFixture):
    def __init__(self, root):
        super().__init__(root)
        self.waiting = {'validator1'}
        self.extra_miners = set()

    def rpc(self, observer, method, *args):
        if method == 'listminers':
            self.calls.append((observer, method, args))
            return [{'address': role, 'permitted': (role, 'mine') not in self.revoked,
                     'islocal': role == observer,
                     'diversitywaitblocks': 1 if role in self.waiting else 0,
                     'chainstate': 'mining-diversity' if role in self.waiting else 'mining-permitted',
                     'localstate': 'waiting-mining-diversity' if role in self.waiting else 'waiting-block-time',
                     'startblock': 0, 'endblock': 4294967295, 'lastmined': 29}
                    for role in ('authority', *lab.VALIDATORS, *sorted(self.extra_miners))]
        if method == 'verifypermission' and args[1] == 'mine':
            self.calls.append((observer, method, args))
            address = args[0]
            return ((address in ('authority', *lab.VALIDATORS) or address in self.extra_miners)
                    and address not in self.waiting and (address, 'mine') not in self.revoked)
        return super().rpc(observer, method, *args)


class MiningCheckRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.node = MiningFixture(self.tmp.name)

    def test_authorized_miner_waiting_turn_passes_doctor(self):
        # Old checker fails here: verifypermission('validator1', 'mine') is false.
        report = lab.doctor(self.node)
        self.assertTrue(report['all_passed'], report['issues'])

    def test_doctor_never_uses_verifypermission_for_mine(self):
        lab.doctor(self.node)
        self.assertFalse(any(method == 'verifypermission' and args[1] == 'mine'
                             for _, method, args in self.node.calls))

    def test_doctor_preserves_wait_diagnostics(self):
        mining = lab.doctor(self.node)['nodes']['validator1']['mining']
        self.assertTrue(mining['permitted'])
        self.assertTrue(mining['expected_permitted'])
        self.assertEqual(mining['diversitywaitblocks'], 1)
        self.assertEqual(mining['source'], 'listminers.permitted')

    def test_each_authorized_miner_may_be_waiting_in_its_snapshot(self):
        # Independent RPC snapshots can be taken at different chain tips.
        self.node.waiting = {'authority', *lab.VALIDATORS}
        self.assertTrue(lab.doctor(self.node)['all_passed'])

    def test_revoked_miner_still_fails(self):
        self.node.revoked.add(('validator1', 'mine'))
        result = lab.doctor(self.node)
        self.assertFalse(result['all_passed'])
        self.assertIn('mine', result['nodes']['validator1']['permission_mismatches'])

    def test_unexpected_publisher_mining_still_fails(self):
        self.node.extra_miners.add('publisher')
        result = lab.doctor(self.node)
        self.assertFalse(result['all_passed'])
        self.assertIn('mine', result['nodes']['publisher']['permission_mismatches'])

    def test_waiting_miner_is_not_regranted_during_repair(self):
        self.assertIsNone(lab.ensure_grant(self.node, 'validator1', 'mine'))
        self.assertEqual([method for _, method, _ in self.node.calls], ['listminers'])

    def test_missing_miner_is_false_not_allowed(self):
        state = lab.assigned_mining_state(self.node, 'authority', 'unknown-address')
        self.assertFalse(state['permitted'])
        self.assertFalse(state['present'])

    def test_rpc_errors_are_not_swallowed(self):
        node = MagicMock()
        node.rpc.side_effect = lab.RPCError('permission query denied', -704)
        with self.assertRaises(lab.RPCError):
            lab.assigned_mining_state(node, 'authority', 'addr')

    def test_invalid_response_is_not_treated_as_permission(self):
        for answer in (None, {}, [None], [{'address': 'addr'}],
                       [{'address': 'addr', 'permitted': 'false'}],
                       [{'address': 'addr', 'permitted': True}] * 2):
            with self.subTest(answer=answer):
                node = MagicMock()
                node.rpc.return_value = answer
                with self.assertRaises(lab.LabError):
                    lab.assigned_mining_state(node, 'authority', 'addr')

    def test_missing_mining_permission_is_granted_once_and_waited(self):
        node = MagicMock()
        node.address.return_value = 'addr'
        node.cfg = {}
        node.rpc.side_effect = [[], 'new-grant-tx']
        self.assertEqual(lab.ensure_grant(node, 'validator1', 'mine'), 'new-grant-tx')
        node.rpc.assert_any_call('authority', 'grant', 'addr', 'mine')
        self.assertEqual(node.rpc.call_count, 2)
        node.wait.assert_called_once_with(['new-grant-tx'], 'authority')
        self.assertEqual(node.cfg['setup_transactions']['grant:validator1:mine'], 'new-grant-tx')

    def test_other_permissions_still_use_verifypermission(self):
        node = MagicMock()
        node.address.return_value = 'addr'
        node.rpc.return_value = True
        self.assertIsNone(lab.ensure_grant(node, 'publisher', 'news.write'))
        node.rpc.assert_called_once_with('authority', 'verifypermission', 'addr', 'news.write')

    def test_disabling_permission_diagnostics_makes_no_mining_read(self):
        self.assertTrue(lab.doctor(self.node, check_permissions=False)['all_passed'])
        self.assertNotIn('listminers', [m for _, m, _ in self.node.calls])

    def test_explicit_false_is_denied_even_when_wait_is_zero(self):
        node = MagicMock()
        node.rpc.return_value = [{'address': 'addr', 'permitted': False, 'diversitywaitblocks': 0}]
        self.assertFalse(lab.assigned_mining_state(node, 'authority', 'addr')['permitted'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
