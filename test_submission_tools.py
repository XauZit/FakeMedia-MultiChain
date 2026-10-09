"""Tests for packaging helpers; not live MultiChain integration tests."""
import json,tempfile,unittest
from pathlib import Path
from tools.export_evidence import export,permitted,scrub
from tools.check_repository import check
class SubmissionTests(unittest.TestCase):
    def test_allowlist_rejects_config(self):self.assertFalse(permitted(Path('lab.json')))
    def test_allowlist_rejects_wallet(self):self.assertFalse(permitted(Path('wallet.dat')))
    def test_allowlist_accepts_benchmark(self):self.assertTrue(permitted(Path('ledger-test/summary.json')))
    def test_allowlist_rejects_nested_private(self):self.assertFalse(permitted(Path('ledger-test/nodes/wallet.dat')))
    def test_credential_key_refused(self):
        with self.assertRaises(ValueError):scrub({'rpcpassword':'test-secret'},Path('/lab'))
    def test_workspace_redaction(self):self.assertEqual(scrub({'workspace':'private'},Path('/lab'))['workspace'],'<WORKSPACE>')
    def test_private_file_guard(self):self.assertTrue(check('wallet.dat',b''))
    def test_benign_code_guard(self):self.assertFalse(check('lab.py',b"name = 'rpcpassword'"))
    def test_runtime_directory_guard(self):self.assertTrue(check('workspace/any.txt',b''))
    def test_allowlisted_export_and_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);w=base/'private';(w/'evidence').mkdir(parents=True)
            (w/'lab.json').write_text('{}');(w/'evidence'/'doctor.json').write_text('{"all_passed":true}')
            (w/'evidence'/'multichain.conf').write_text('not for publication')
            result=export(w,base/'public')
            self.assertEqual(result['files_exported'],1)
            self.assertFalse((base/'public'/'multichain.conf').exists())
            manifest=json.loads((base/'public'/'EXPORT_MANIFEST.json').read_text())
            self.assertIn('original_sha256',manifest['files'][0])
    def test_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);(base/'evidence').mkdir();(base/'lab.json').write_text('{}')
            target=base.parent/(base.name+'-existing');target.mkdir()
            try:
                with self.assertRaises(ValueError):export(base,target)
            finally:target.rmdir()
if __name__=='__main__':unittest.main()
