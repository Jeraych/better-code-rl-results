"""Verify archived bytes first and recompute into disposable output only."""
import copy
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'analysis'))
spec = importlib.util.spec_from_file_location('verify_all', ROOT / 'analysis/verify_all.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

SNAPSHOTS = {
    'automatic': 'automatic.json',
    'human': 'human.json',
    'judge': 'judge-diagnostics.json',
    'exploratory': 'exploratory.json',
}


class VerificationTests(unittest.TestCase):
    def make_fixture(self, root, newline='\r\n'):
        (root / 'data').mkdir(parents=True)
        (root / 'data/raw.csv').write_bytes(b'group,value\r\n1,2\r\n')
        (root / 'verification').mkdir()
        self.results = {
            key: {'status': 'PASS', 'count': 2, 'values': [0.5, 1.0], 'label': 'saved'}
            for key in SNAPSHOTS
        }
        for key, name in SNAPSHOTS.items():
            text = json.dumps(self.results[key], indent=2) + '\n'
            (root / 'verification' / name).write_bytes(text.replace('\n', newline).encode())
        (root / 'fixture.py').write_bytes(b'"""Syntax-only fixture."""\n')
        paths = sorted(p for p in root.rglob('*') if p.is_file())
        entries = [
            {'path': p.relative_to(root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in paths
        ]
        (root / 'manifests').mkdir()
        with (root / 'manifests/files.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['path', 'sha256'])
            writer.writeheader()
            writer.writerows(entries)
        (root / 'manifests/sha256.txt').write_bytes(
            ''.join(f'{r["sha256"]}  {r["path"]}\n' for r in entries).encode()
        )
        self.producers = {key: Mock(return_value=copy.deepcopy(result)) for key, result in self.results.items()}

    @staticmethod
    def tree_bytes(root):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_default_keeps_archives_and_inputs_byte_identical_on_both_newlines(self):
        for newline in ['\r\n', '\n']:
            with self.subTest(newline=repr(newline)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'archive'
                self.make_fixture(root, newline)
                before = self.tree_bytes(root)
                with patch.object(verifier, 'ROOT', root), patch.multiple(verifier, **self.producers):
                    result = verifier.verify()
                self.assertEqual(result['manifest']['status'], 'PASS')
                self.assertEqual(result['derived_comparison']['files'], 4)
                self.assertEqual(self.tree_bytes(root), before)
                for producer in self.producers.values():
                    producer.assert_called_once_with()

    def test_explicit_output_uses_lf_and_does_not_overwrite_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root, output = Path(directory) / 'archive', Path(directory) / 'fresh'
            self.make_fixture(root)
            before = self.tree_bytes(root)
            with patch.object(verifier, 'ROOT', root), patch.multiple(verifier, **self.producers):
                verifier.verify(output)
            for key, name in SNAPSHOTS.items():
                raw = (output / name).read_bytes()
                self.assertNotIn(b'\r', raw)
                self.assertTrue(raw.endswith(b'\n'))
                self.assertEqual(json.loads(raw), self.results[key])
            self.assertTrue((output / 'verification-report.json').is_file())
            self.assertEqual(self.tree_bytes(root), before)

    def test_raw_input_hash_tamper_rejected_before_recomputation_or_output(self):
        for tampered in [b'group,value\r\n1,999\r\n', b'group,value\n1,2\n']:
            with self.subTest(tampered=repr(tampered)), tempfile.TemporaryDirectory() as directory:
                root, output = Path(directory) / 'archive', Path(directory) / 'fresh'
                self.make_fixture(root)
                (root / 'data/raw.csv').write_bytes(tampered)
                before = self.tree_bytes(root)
                with patch.object(verifier, 'ROOT', root), patch.multiple(verifier, **self.producers):
                    with self.assertRaisesRegex(ValueError, 'data/raw.csv'):
                        verifier.verify(output)
                self.assertFalse(output.exists())
                self.assertEqual(self.tree_bytes(root), before)
                for producer in self.producers.values():
                    producer.assert_not_called()

    def test_second_manifest_mismatch_also_prevents_recomputation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'archive'
            self.make_fixture(root)
            manifest = root / 'manifests/sha256.txt'
            manifest.write_bytes(('0' * 64 + '  data/raw.csv\n').encode())
            with patch.object(verifier, 'ROOT', root), patch.multiple(verifier, **self.producers):
                with self.assertRaisesRegex(ValueError, 'data/raw.csv'):
                    verifier.verify()
            for producer in self.producers.values():
                producer.assert_not_called()

    def test_changed_recomputed_value_is_rejected_without_modifying_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'archive'
            self.make_fixture(root)
            self.producers['automatic'].return_value['count'] = 3
            before = self.tree_bytes(root)
            with patch.object(verifier, 'ROOT', root), patch.multiple(verifier, **self.producers):
                with self.assertRaisesRegex(ValueError, 'automatic.json'):
                    verifier.verify()
            self.assertEqual(self.tree_bytes(root), before)

    def test_output_cannot_target_frozen_repository_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'archive'
            self.make_fixture(root)
            before = self.tree_bytes(root)
            with patch.object(verifier, 'ROOT', root), patch.multiple(verifier, **self.producers):
                with self.assertRaisesRegex(ValueError, 'runs/'):
                    verifier.verify(root / 'verification')
            self.assertEqual(self.tree_bytes(root), before)


if __name__ == '__main__':
    unittest.main()
