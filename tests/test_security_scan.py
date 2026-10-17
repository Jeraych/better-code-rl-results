"""Synthetic scanner checks; no network, candidate execution or real Git repo."""
import base64
from contextlib import redirect_stderr, redirect_stdout
import csv
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import warnings

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_security_scan', ROOT / 'analysis/security_scan.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def synthetic_token():
    return b'g' + b'hp' + b'_' + b'A' * 25


def literal_assignment(name=b'password', value=b'opaque-credential-value'):
    return name + b' = ' + bytes([34]) + value + bytes([34])


class BatchFixture:
    """Replay Git's exact size-delimited batch response, including binary trees."""
    def __init__(self, objects):
        self.objects = objects
        self.requests = []
        self.stdout = io.BytesIO()
        self.stdin = self
        self.pending = b''

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def write(self, data):
        self.pending += data
        return len(data)

    def flush(self):
        oid = self.pending.strip().decode()
        self.pending = b''
        kind, data = self.objects[oid]
        self.requests.append(oid)
        self.stdout = io.BytesIO(f'{oid} {kind} {len(data)}\n'.encode() + data + b'\n')

    def close(self):
        pass

    def wait(self, timeout=None):
        return 0


class SecurityScanTests(unittest.TestCase):
    def categories(self, payload, name='record.log'):
        return {finding['category'] for finding in scanner.inspect(payload, name)}

    def test_all_extensions_and_binary_payload_are_scanned(self):
        token = synthetic_token()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ['run.log', 'application.properties', 'data.tsv', 'opaque.unlisted', 'NO_EXTENSION', 'binary.bin']
            for name in names:
                payload = b'field\n' + token + b'\n' if name.endswith('.tsv') else token
                (root / name).write_bytes(b'\0' + payload if name.endswith('.bin') else payload)
            with patch.object(scanner, 'ROOT', root):
                result = scanner.scan(history=False)
            actual = {r['path'] for r in result['findings'] if r['category'] == 'credential'}
            self.assertEqual(actual, set(names))
            self.assertEqual(result['files_scanned'], len(names))
            self.assertNotIn(token.decode(), json.dumps(result))

    def test_literal_secret_assignments_and_env_names_are_distinguished(self):
        for name in [b'password', b'access_token', b'AI_JUDGE_API_KEY', b'secret', b'cookie']:
            with self.subTest(name=name.decode()):
                self.assertIn('assigned_secret_value', self.categories(literal_assignment(name)))
        code = b'import os, re\n' + b'API_' + b'KEY = os.getenv("SERVICE_' + b'API_KEY")\n'
        pattern = b'C:' + bytes([92, 92]) + b'Users' + bytes([92, 92]) + b'[A-Za-z]+'
        code += b'pattern = re.compile(' + repr(pattern).encode() + b')\n'
        code += b'code = "else C:' + bytes([92]) + b'n    return value"\n'
        self.assertEqual(scanner.inspect(code, 'example.py'), [])
        self.assertIn('credential', self.categories(code + b'saved = ' + repr(synthetic_token()).encode(), 'example.py'))

    def test_csv_json_escaped_cells_include_record_locations(self):
        code = literal_assignment() + b'\nreturn value'
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['raw_completion'])
        writer.writerow([code.decode()])
        findings = scanner.inspect(output.getvalue().encode(), 'saved.csv')
        self.assertTrue(any(f['category'] == 'assigned_secret_value' and f.get('row') == 2 and f.get('field') == 'raw_completion' for f in findings))
        payload = json.dumps({'raw_completion': code.decode()}).encode()
        findings = scanner.inspect(payload, 'saved.json')
        self.assertTrue(any(f['category'] == 'assigned_secret_value' and f.get('field') == 'raw_completion' for f in findings))
        payload = json.dumps({'api' + '_key': 'opaque-credential-value'}).encode()
        self.assertIn('assigned_secret_value', self.categories(payload, 'saved.json'))

    def test_large_csv_cell_is_decoded_and_field_limit_is_restored(self):
        previous = csv.field_size_limit()
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['raw_completion'])
        writer.writerow(['x' * (max(previous, 131072) + 1) + '\n' + literal_assignment().decode()])
        findings = scanner.inspect(output.getvalue().encode(), 'large.csv')
        self.assertTrue(any(f['category'] == 'assigned_secret_value' and f.get('row') == 2 and f.get('field') == 'raw_completion' for f in findings))
        self.assertEqual(csv.field_size_limit(), previous)

    def test_placeholders_sha256_and_pair_ids_are_safe(self):
        payload = json.dumps({
            'source_sha256': 'ab' * 32, 'pair_id': 'p_' + '34' * 12,
            'password': '<redacted>', 'token': 'fixture-value',
            'AI_JUDGE_API_KEY': '${AI_JUDGE_API_KEY}',
            'secret': '[REDACTED:credential]',
        }).encode()
        self.assertEqual(scanner.inspect(payload, 'manifest.json'), [])

    def test_strong_families_jwt_private_key_and_credential_urls(self):
        def segment(value):
            return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b'=')
        jwt = b'.'.join([segment({'alg': 'HS256', 'typ': 'JWT'}), segment({'sub': 'fixture-user'}), b'Q' * 32])
        url = b'https://' + b'named-user' + b':' + b'opaque-credential-value' + b'@example.invalid/path'
        private_key = b'-----BEGIN ' + b'OPENSSH ' + b'PRIVATE KEY-----'
        families = [synthetic_token(), b'h' + b'f_' + b'B' * 24, b's' + b'k-' + b'C' * 32,
                    b'AK' + b'IA' + b'D' * 16, b'xox' + b'b-' + b'E' * 25, private_key]
        for value in families:
            with self.subTest(length=len(value)):
                self.assertIn('credential', self.categories(value))
        self.assertIn('jwt', self.categories(jwt))
        self.assertIn('credential_url', self.categories(url))

    def test_networks_versions_and_actual_url_hosts(self):
        address = lambda parts: '.'.join(map(str, parts)).encode()
        private = address([10, 4, 5, 6])
        public = address([45, 67, 89, 123])
        self.assertIn('private_network', self.categories(private))
        self.assertIn('external_ipv4', self.categories(public))
        self.assertIn('external_ipv4', self.categories(public + b'.p in prose'))
        self.assertIn('external_ipv4', self.categories(public + b'suffix'))
        self.assertEqual(scanner.inspect(public + b'.55', 'numeric-series.log'), [])
        for parts in [[127, 0, 0, 1], [192, 0, 2, 7], [198, 51, 100, 8], [203, 0, 113, 9], [198, 18, 0, 1], [999, 1, 2, 3]]:
            self.assertEqual(scanner.inspect(address(parts), 'example.log'), [])
        version = address([6, 2, 0, 0])
        self.assertEqual(scanner.inspect(b'package==' + version, 'requirements.log'), [])
        for key in ['version', 'package.version', 'package-version', 'package_version']:
            self.assertEqual(scanner.inspect(json.dumps({key: version.decode()}).encode(), 'meta.json'), [])
            self.assertIn('external_ipv4', self.categories(json.dumps({key: 'https://' + public.decode()}).encode(), 'meta.json'))
        self.assertIn('private_ipv6', self.categories(b'fd' + b'12' + b'::' + b'1234'))

    def test_env_key_database_paper_and_logo_paths_are_forbidden(self):
        for name in ['.env', '.env.sample', 'env.example', 'secret.key', 'saved.sqlite3',
                     'paper/main.tex', 'final_report/final.pdf', 'UoA-Logo.png', 'Final Report - student.docx']:
            with self.subTest(path=name):
                self.assertIn('forbidden_file', self.categories(b'', name))

    def test_named_private_paths_are_detected_and_source_newline_is_not(self):
        for path in [b'C:' + bytes([92]) + b'Users' + bytes([92]) + b'NamedUser',
                     b'/home/' + b'named-user/project', b'D:' + b'/Study/project']:
            self.assertIn('private_path', self.categories(path))
        self.assertNotIn('private_path', self.categories(b'case C:' + bytes([92]) + b'nreturn value'))

    def test_values_never_enter_reports_stdout_stderr_or_secret_filenames(self):
        token = synthetic_token()
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            report = scanner.inspect(token, 'logs/' + token.decode() + '.log')
            print(json.dumps(report))
        for output in [json.dumps(report), stdout.getvalue(), stderr.getvalue()]:
            self.assertNotIn(token.decode(), output)
        allowed = {'path', 'category', 'count', 'history', 'line', 'row', 'field'}
        self.assertTrue(all(set(finding) <= allowed for finding in report))

    def test_deleted_history_alias_paths_and_commit_metadata_use_batch_protocol(self):
        token, metadata_token = synthetic_token(), b'h' + b'f_' + b'F' * 24
        oid = lambda index: f'{index:040x}'
        def tree(entries):
            return b''.join(mode + b' ' + name.encode() + b'\0' + bytes.fromhex(child) for mode, name, child in entries)
        address = b'1+research' + bytes([64]) + b'users' + b'.noreply' + b'.github' + b'.com'
        identity = b'author Research <' + address + b'> 1 +0000\ncommitter Research <' + address + b'> 1 +0000\n'
        objects = {
            oid(1): ('blob', b'prefix\0\n' + token + b'\n' + b'0' * 40 + b' tree 0\n'),
            oid(2): ('blob', b''),
            oid(3): ('tree', tree([(b'100644', 'deleted.unlisted', oid(1)), (b'100644', 'README.md', oid(2)), (b'100644', 'env.example', oid(2)), (b'40000', 'paper', oid(4))])),
            oid(4): ('tree', tree([(b'100644', 'main.pdf', oid(2))])),
            oid(5): ('tree', b''),
            oid(6): ('commit', f'tree {oid(3)}\n'.encode() + identity + b'\nold message ' + metadata_token),
            oid(7): ('commit', f'tree {oid(5)}\nparent {oid(6)}\n'.encode() + identity + b'\ndeleted files'),
        }
        process = BatchFixture(objects)
        def git_run(args, **kwargs):
            if args[1] == 'rev-list':
                output = ''.join(name + '\n' for name in objects).encode()
            elif args[1:] == ['cat-file', '--batch-check']:
                output = b''.join(f'{name} {kind} {len(data)}\n'.encode() for name, (kind, data) in objects.items())
            else:
                raise AssertionError('Unexpected Git subprocess')
            return subprocess.CompletedProcess(args, 0, stdout=output)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.git').mkdir()  # A marker only; no Git repository is created.
            with patch.object(scanner, 'ROOT', root), patch.object(scanner.subprocess, 'run', side_effect=git_run) as inventory, patch.object(scanner.subprocess, 'Popen', return_value=process) as batch:
                result = scanner.scan()
        historical = [f for f in result['findings'] if f['history']]
        self.assertTrue(any(f['path'] == 'deleted.unlisted' and f['category'] == 'credential' for f in historical))
        for name in ['env.example', 'paper/main.pdf']:
            self.assertTrue(any(f['path'] == name and f['category'] == 'forbidden_file' for f in historical))
        self.assertTrue(any(f['path'].startswith('<commit metadata:') and f['category'] == 'credential' for f in historical))
        self.assertEqual(result['git_blobs'], 2)
        self.assertEqual(inventory.call_count, 2)
        batch.assert_called_once()
        self.assertCountEqual(process.requests, list(objects))
        self.assertNotIn(token.decode(), json.dumps(result))
        self.assertNotIn(metadata_token.decode(), json.dumps(result))

    def test_scanner_source_regexes_do_not_flag_themselves(self):
        payload = (ROOT / 'analysis/security_scan.py').read_bytes()
        self.assertEqual(scanner.inspect(payload, 'analysis/security_scan.py'), [])

    def test_numeric_token_measurements_are_not_credentials(self):
        for name in scanner.TOKEN_MEASUREMENTS:
            with self.subTest(field=name):
                self.assertEqual(scanner.inspect(json.dumps({name: 256}).encode(), 'metrics.json'), [])
                self.assertEqual(scanner.inspect(json.dumps({name: '256.0'}).encode(), 'metrics.json'), [])
                self.assertEqual(scanner.inspect((name + '\n256\n').encode(), 'metrics.csv'), [])
                self.assertIn('assigned_secret_value', self.categories(literal_assignment(name.encode(), b'opaque-credential-value')))
                self.assertIn('assigned_secret_value', self.categories(json.dumps({name: 'cd' * 32}).encode(), 'metrics.json'))
                self.assertIn('credential', self.categories(json.dumps({name: synthetic_token().decode()}).encode(), 'metrics.json'))
        self.assertIn('assigned_secret_value', self.categories(literal_assignment(b'access_token', b'123456')))

    def test_tokenizer_metadata_and_shell_flags_have_bounded_exceptions(self):
        for name in [b'pad_token', b'bos_token_id', b'eos_token_id']:
            for value in [b'None}.', b'<end>.']:
                self.assertEqual(scanner.inspect(name + b'=' + value, 'startup.log'), [])
            self.assertIn('assigned_secret_value', self.categories(literal_assignment(name)))
        self.assertEqual(scanner.inspect(b'eos_token_id=128001', 'startup.log'), [])
        self.assertIn('assigned_secret_value', self.categories(b'access_token=128001'))
        self.assertEqual(scanner.inspect(b'AI_JUDGE_API_KEY_SET=1', 'launch.sh'), [])
        self.assertIn('assigned_secret_value', self.categories(literal_assignment(b'AI_JUDGE_API_KEY_SET')))
        self.assertEqual(scanner.inspect(b'SECRET_ENV_KEYS=(\nAI_JUDGE_API_KEY\n)\n[[ $secret_key =~ value ]]', 'launch.sh'), [])
        self.assertEqual(scanner.inspect(literal_assignment(b'api_key', b'SERVICE_API_KEY'), 'documentation.md'), [])
        self.assertIn('credential', self.categories(b'SECRET_ENV_KEYS=(' + synthetic_token() + b')', 'launch.sh'))

    def test_code_field_expressions_and_comparisons_preserve_quoted_literals(self):
        expressions = (b'token = existing[index]\nsecret = {}\npassword: str\n'
                       b'if token == other: pass\nif secret != value: pass\n'
                       b'api_key = [existing]\npassword = str(value)\n')
        for field in scanner.SOURCE_FIELDS:
            self.assertEqual(scanner.inspect(json.dumps({field: expressions.decode()}).encode(), 'saved.json'), [])
            payload = json.dumps({field: (expressions + literal_assignment()).decode()}).encode()
            self.assertIn('assigned_secret_value', self.categories(payload, 'saved.json'))
            typed = b'api_key: str = ' + bytes([34]) + b'opaque-credential-value' + bytes([34])
            self.assertIn('assigned_secret_value', self.categories(json.dumps({field: typed.decode()}).encode(), 'saved.json'))

    def test_log_labels_do_not_consume_the_next_unquoted_line(self):
        self.assertEqual(scanner.inspect(b'Failed to read token:\n<unrelated> log entry\n', 'training.log'), [])
        self.assertIn('assigned_secret_value', self.categories(b'password=opaque-value', 'training.log'))
        for newline in [b'\n', b'\r\n']:
            payload = b'api_key =' + newline + b'    ' + bytes([34]) + b'opaque-credential-value' + bytes([34])
            self.assertIn('assigned_secret_value', self.categories(payload, 'saved.py'))
        default = b'def connect(password: str = ' + bytes([34]) + b'opaque-credential-value' + bytes([34]) + b'): pass'
        self.assertIn('assigned_secret_value', self.categories(default, 'saved.py'))

    def test_jsonl_decodes_code_records_and_reports_row_and_field(self):
        payload = json.dumps({'prompt_token_length': 128, 'raw_completion': 'token = existing[index]'}).encode()
        payload += b'\n' + json.dumps({'raw_completion': literal_assignment().decode()}).encode() + b'\n'
        findings = scanner.inspect(payload, 'samples.jsonl')
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['category'], 'assigned_secret_value')
        self.assertEqual(findings[0]['row'], 2)
        self.assertEqual(findings[0]['field'], 'raw_completion')

    def test_network_url_paths_and_portable_cd_examples_are_not_local_paths(self):
        local = b'/home/' + b'named-user/project'
        self.assertNotIn('private_path', self.categories(b'https://example.invalid' + local))
        self.assertIn('private_path', self.categories(b'file://' + local))
        self.assertEqual(scanner.inspect(b'cd ~/' + b'repository\n', 'instructions.md'), [])
        self.assertIn('private_path', self.categories(b'cat ~/' + b'repository/file', 'instructions.md'))
        self.assertIn('private_path', self.categories(b'cd ' + local, 'instructions.md'))
        public = b'.'.join(str(number).encode() for number in [45, 67, 89, 123])
        self.assertIn('external_ipv4', self.categories(b'https://' + public + local))

    def test_unc_hosts_and_shares_are_distinct_from_escaped_text(self):
        slash = bytes([92])
        for scale in [1, 2]:
            unc = slash * (2 * scale) + b'internal-host' + slash * scale + b'private-share'
            self.assertIn('private_path', self.categories(unc))
        for escaped in [b'u1234', b'd+', b'text', b'[markdown']:
            noise = slash * 2 + escaped + slash * 2 + b'value]'
            self.assertNotIn('private_path', self.categories(noise))

    def test_csv_sanitizes_each_header_only_once(self):
        payload = b'ordinary\n' + b'content\n' * 20
        with patch.object(scanner, '_safe_location', wraps=scanner._safe_location) as sanitize:
            self.assertEqual(scanner.inspect(payload, 'records.csv'), [])
        self.assertEqual(sanitize.call_count, 1)

    def test_binary_path_noise_is_filtered_but_embedded_paths_and_tokens_remain(self):
        noise = bytes([92, 92, 129]) + b'host' + bytes([92]) + b'bad' + bytes([255]) + b'bytes'
        self.assertNotIn('private_path', self.categories(noise, 'figure.pdf'))
        unicode_noise = bytes([255]) + b'~/' + chr(0x4E01).encode() + b'a' + bytes([0])
        self.assertNotIn('private_path', self.categories(unicode_noise, 'figure.png'))
        path = b'E:' + b'/internal/project'
        self.assertIn('private_path', self.categories(bytes([255, 0]) + path + bytes([0, 255]), 'figure.pdf'))
        self.assertIn('credential', self.categories(bytes([255, 0]) + synthetic_token() + bytes([0, 255]), 'binary.bin'))

    def test_test_source_uses_safe_synthetic_inputs(self):
        self.assertEqual(scanner.inspect(Path(__file__).read_bytes(), 'tests/test_security_scan.py'), [])

    def test_long_dotted_identifier_does_not_hide_following_credential(self):
        payload = b'a.' * 32000 + b'\n' + synthetic_token()
        findings = scanner.inspect(payload, 'long.log')
        self.assertEqual({finding['category'] for finding in findings}, {'credential'})
        email = b'someone' + b'@' + b'example' + b'.invalid'
        self.assertIn('email', self.categories(email))

    def test_non_secret_assignments_never_parse_their_values(self):
        payload = literal_assignment(b'ordinary', b'opaque' + bytes([92]) + b'q-value')
        with patch.object(scanner, '_assignment_value', side_effect=AssertionError('non-secret value must not be parsed')) as parse:
            self.assertEqual(scanner.inspect(payload, 'ordinary.log'), [])
        parse.assert_not_called()

    def test_source_and_literal_warnings_do_not_escape_the_scanner(self):
        payload = literal_assignment(value=b'opaque' + bytes([92]) + b'q-value')
        stdout, stderr = io.StringIO(), io.StringIO()
        with warnings.catch_warnings(record=True) as emitted, redirect_stdout(stdout), redirect_stderr(stderr):
            warnings.simplefilter('always')
            findings = scanner.inspect(payload, 'source.py')
        self.assertIn('assigned_secret_value', {finding['category'] for finding in findings})
        self.assertEqual(emitted, [])
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(stderr.getvalue(), '')


if __name__ == '__main__':
    unittest.main()
