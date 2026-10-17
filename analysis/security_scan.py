"""Read-only byte/record/history scan. Findings contain locations, never values."""
import ast
import csv
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.cache',
             '.pytest_cache', '.mypy_cache', '.ruff_cache', 'runs'}
SOURCE_SUFFIXES = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.cs'}
SOURCE_FIELDS = {'raw_completion', 'extracted_code'}
TOKEN_MEASUREMENTS = {'prompt_token_length', 'completion_token_length',
                      'before_completion_token_length', 'after_completion_token_length',
                      'complete_token_usage_count'}
SPECIAL_TOKENS = {'bos_token', 'eos_token', 'pad_token', 'unk_token', 'sep_token',
                  'cls_token', 'mask_token'}
PATTERNS = {
    'credential': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{24,}|(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|ya29\.[A-Za-z0-9_-]{20,}|(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----|-----BEGIN PGP PRIVATE KEY BLOCK-----)'),
    'jwt': re.compile(rb'(?<![\w.-])eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?![\w.-])'),
    'credential_url': re.compile(rb'(?i)(?<![a-z0-9+.-])[a-z][a-z0-9+.-]*://(?P<user>[^\s/\x22\x27<>:@]+):(?P<password>[^\s/\x22\x27<>@]+)@[^\s/\x22\x27<>]+'),
    'private_network': re.compile(rb'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?!\d|\.\d)'),
    'private_ipv6': re.compile(rb'(?i)(?<![\w:])(?:f[cd][0-9a-f]{2}|fe[89ab][0-9a-f]):[0-9a-f:]+(?![\w:])'),
    'private_path': re.compile(rb'(?i)(?:(?<![\w])[a-z]:[\\/]+(?:Users|Study|Projects?|Downloads?|Desktop|Documents|Workspaces?|Temp|Repos?|Dev)(?=[\\/\s\x22\x27,;]|$)|(?<![\w])[a-z]:[\\/]+[a-z0-9_.-]{2,}[\\/]+[^\x00-\x1f\x7f\x22\x27<>|]+|(?<!\\)\\{2,4}[^\\\s\x00-\x1f\x7f\x22\x27]+\\[^\s\x00-\x1f\x7f\x22\x27]+|/(?:home|Users|workspace|scratch|gpfs)/[^/\s\x00-\x1f\x7f\x22\x27]+|~[\\/][^\s\x00-\x1f\x7f\x22\x27]+)'),
    'named_reviewer_record': re.compile(rb'(?i)[\x22\x27]reviewer[\x22\x27]\s*:\s*[\x22\x27](?:Jacky|Conrad)[\x22\x27]'),
    'assigned_secret_value': re.compile(rb'(?i)(?<![\w.-])[\x22\x27]?(?P<name>[a-z_][a-z0-9_.-]*)[\x22\x27]?[ \t]*(?:(?::[ \t]*(?:str|bytes|string|Any|Optional\[(?:str|bytes)\])[ \t]*)?=(?![=~>])|:(?!=))[ \t]*(?P<value>(?:\r?\n[ \t]*)?[br]?(?:\x22(?:\\.|[^\x22\\\r\n])*\x22|\x27(?:\\.|[^\x27\\\r\n])*\x27)|[^\s,;#]+)'),
    'email': re.compile(rb'(?<![A-Z0-9._%+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.I),
    'exact_response_time': re.compile(rb'20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z'),
}
IP_EXEMPT = tuple(ipaddress.ip_network(n) for n in (
    '0.0.0.0/8', '127.0.0.0/8', '192.0.2.0/24', '198.51.100.0/24',
    '203.0.113.0/24', '198.18.0.0/15', '224.0.0.0/4', '240.0.0.0/4'))


def _placeholder(value):
    text = value.decode('utf-8', 'replace').strip() if isinstance(value, bytes) else str(value).strip()
    if text.lower() in {'', 'none', 'null', 'true', 'false', 'redacted', 'removed', 'unset',
                        'placeholder', 'changeme', 'change-me', 'change_me', 'replace-me',
                        'replace_me', 'unused', 'ollama', 'dummy', 'example', 'fixture', 'test'}:
        return True
    if re.fullmatch(r'(?:[A-Z][A-Z0-9]*_)*(?:API_KEY|ACCESS_TOKEN|API_TOKEN|SECRET_KEY|PASSWORD|COOKIE)', text):
        return True  # An explicit environment variable name is not its value.
    return bool(re.fullmatch(r'(?:<[^<>]+>|\[[^\[\]]*(?:redacted|removed)[^\[\]]*\]|\$\{[^}]+\}|\$[A-Z_][A-Z0-9_]*|\{\{[^}]+\}\}|(?:your|insert|replace|redacted|removed|dummy|example|sample|fixture|synthetic|placeholder|fake)[_ :.-].+|test[-_](?:only|key|token|value|password)(?:[-_].*)?)', text, re.I))


def _secret_name(name):
    return bool(re.search(r'(?:^|_)(?:password|passwd|pwd|token|secret|cookie|cookies|api_key|api_token|session_key|sessionid|authorization)(?:$|_)', name.lower().replace('-', '_').replace('.', '_')))


def _numeric_token_measurement(name, value):
    # Exempt counts only, never arbitrary strings stored under a measurement name.
    return (name.lower() in TOKEN_MEASUREMENTS
            and re.fullmatch(rb'\+?\d{1,18}(?:\.\d{1,9})?(?:[eE][+-]?\d{1,3})?', value.strip()) is not None)


def _safe_named_value(name, value, path):
    name = name.lower()
    if _placeholder(value) or _numeric_token_measurement(name, value):
        return True
    token_name = name.removesuffix('_id')
    if token_name in SPECIAL_TOKENS:
        clean = value.strip().rstrip(b'.,;:)}]')
        if _placeholder(clean):
            return True
        if name.endswith('_id') and re.fullmatch(rb'-?\d{1,9}', clean):
            return True
    if name == 'ai_judge_api_key_set' and value.strip() in {b'0', b'1'}:
        return True
    return name == 'secret_env_keys' and Path(path).suffix.lower() in {'.sh', '.bash'} and value == b'('


def _plausible_text_path(value):
    try:
        text = value.decode('utf-8')
    except UnicodeError:
        return False
    if not text or not text.isprintable():
        return False
    if value.startswith(b'\\\\'):
        parts = re.split(rb'\\+', value)
        runs = re.findall(rb'\\+', value)
        # UNC paths have a host and share; escaped regex/Unicode/LaTeX text does not.
        return (len(parts) >= 3 and len(runs) >= 2 and len(runs[0]) in {2, 4}
                and len(runs[1]) == len(runs[0]) // 2
                and re.fullmatch(rb'[A-Za-z0-9][A-Za-z0-9_.-]{1,252}', parts[1]) is not None
                and re.match(rb'[A-Za-z0-9_$][A-Za-z0-9_$.-]*(?:$|[\s\x22\x27`),;])', parts[2]) is not None)
    return True


def _private_path_context(raw, match, path):
    if not _plausible_text_path(match.group()):
        return False
    if match.start() and raw[match.start() - 1] not in b'\x00 \t\r\n\x22\x27=:([{}<>|`/\\-':
        return False  # A path starts at a text delimiter, not inside compressed bytes.
    for url in re.finditer(rb'(?i)(?<![a-z0-9+.-])(?P<scheme>[a-z][a-z0-9+.-]*)://[^\s\x22\x27<>`]+', raw):
        if url.group('scheme').lower() != b'file' and url.start() <= match.start() < url.end():
            return False
    if match.group().startswith(b'~/') and Path(path).suffix.lower() in {'.md', '.rst'}:
        before = raw[raw.rfind(b'\n', 0, match.start()) + 1:match.start()]
        if re.search(rb'(?:^|[\s`>#$])cd\s+[\x22\x27]?$', before):
            return False  # Portable home-relative shell example, without a username.
    return True


def _assignment_value(match, path, source=False):
    raw = match.group('value').lstrip(b'\r\n \t')
    if raw[:1] in (b'\x22', b'\x27') or raw[:2].lower() in (b'b\x22', b'b\x27', b'r\x22', b'r\x27'):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                warnings.simplefilter('ignore', DeprecationWarning)
                value = ast.literal_eval(raw.decode('utf-8'))
            return value if isinstance(value, bytes) else str(value).encode('utf-8')
        except (SyntaxError, ValueError, UnicodeError):
            return raw.strip(b'\x22\x27')
    if (source or Path(path).suffix.lower() in SOURCE_SUFFIXES) and not re.fullmatch(rb'\d+', raw):
        return None  # A variable/expression is not a literal credential.
    if raw.startswith((b'$', b'{{', b'os.environ', b'os.getenv', b'getenv(')):
        return None
    return raw.rstrip(b',}]')


def _mask_regex_definitions(data, path):
    """Parse source only; never import or execute it, and keep line positions."""
    if Path(path).suffix.lower() != '.py':
        return data
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SyntaxWarning)
            warnings.simplefilter('ignore', DeprecationWarning)
            tree = ast.parse(data)
    except (SyntaxError, ValueError, UnicodeError):
        return data
    offsets = [0]
    for line in data.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    masked = bytearray(data)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 're'
                and node.func.attr in {'compile', 'search', 'match', 'fullmatch', 'findall', 'finditer', 'sub', 'split'}
                and node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, (bytes, str))):
            value = node.args[0]
            start = offsets[value.lineno - 1] + value.col_offset
            end = offsets[value.end_lineno - 1] + value.end_col_offset
            for index in range(start, end):
                if masked[index] not in (10, 13):
                    masked[index] = 32
    return bytes(masked)


def _safe_location(value):
    raw = str(value).encode('utf-8', 'surrogateescape')
    for category, pattern in PATTERNS.items():
        if category == 'assigned_secret_value':
            raw = pattern.sub(lambda match: b'<redacted>' if _secret_name(match.group('name').decode()) else match.group(), raw)
        elif category not in {'named_reviewer_record', 'exact_response_time'}:
            raw = pattern.sub(b'<redacted>', raw)
    return raw.decode('utf-8', 'replace')


def _forbidden_path(path):
    parts = path.replace('\\', '/').lower().split('/')
    name = parts[-1]
    suffix = Path(name).suffix
    return bool(name == '.env' or name.startswith('.env.') or name in {'env', 'env.example', 'env.sample', 'env.template', '.envrc'}
                or name.endswith('.env') or name in {'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', '.netrc', 'credentials'}
                or suffix in {'.pem', '.key', '.p12', '.pfx', '.jks', '.keystore', '.db', '.db3', '.mdb', '.sqlite', '.sqlite3'}
                or re.search(r'\.(?:db|sqlite\d*)(?:-wal|-shm)$', name)
                or any(p in {'paper', 'papers', 'final_report', 'final-report', 'manuscript'} for p in parts)
                or any(p in SKIP_DIRS - {'.git'} for p in parts)
                or (suffix in {'.pdf', '.doc', '.docx', '.tex', '.bib'} and re.search(r'^(?:main(?:document)?\.|final[ _-]*report|softeng700|manuscript)', name))
                or ('logo' in name and suffix in {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.pdf', '.eps', '.ai', '.psd', '.zip'}))


def _record_views(data, path):
    """Decode structured cells so escaped/doubled quotes cannot hide literals."""
    try:
        text = data.decode('utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    except UnicodeError:
        yield data, {}, None
        return
    suffix = Path(path).suffix.lower()
    if suffix in {'.csv', '.tsv'}:
        previous_limit = csv.field_size_limit()
        # A field cannot exceed its already-loaded record file; restore the caller's limit.
        csv.field_size_limit(max(previous_limit, len(text)))
        reader = csv.reader(io.StringIO(text, newline=''), delimiter='\t' if suffix == '.tsv' else ',')
        try:
            headers = next(reader)
            safe_headers = [_safe_location(header) for header in headers]
            for column, header in enumerate(headers):
                yield header.encode(), {'row': 1, 'field': f'column_{column + 1}'}, None
            for row, cells in enumerate(reader, 2):
                for column, cell in enumerate(cells):
                    name = headers[column] if column < len(headers) else f'column_{column + 1}'
                    safe_name = safe_headers[column] if column < len(headers) else name
                    yield cell.encode(), {'row': row, 'field': safe_name}, name
            return
        except (StopIteration, csv.Error):
            pass
        finally:
            csv.field_size_limit(previous_limit)
    if suffix == '.jsonl':
        for row, line in enumerate(text.split('\n'), 1):
            if line.strip():
                for raw, location, name in _record_views(line.encode(), 'record.json'):
                    yield raw, {'row': row, **location}, name
        return
    try:
        obj = json.loads(text)
    except (ValueError, RecursionError):
        obj = None
    if isinstance(obj, (dict, list, str)):
        def walk(value, field='', name=None):
            if isinstance(value, dict):
                for key, item in value.items():
                    yield key.encode(), {'field': _safe_location(field + '.<key>')}, None
                    yield from walk(item, f'{field}.{key}'.lstrip('.'), key)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    yield from walk(item, f'{field}[{index}]')
            elif isinstance(value, str):
                yield value.encode(), {'field': _safe_location(field)}, name
            elif value is not None and not isinstance(value, bool):
                yield str(value).encode(), {'field': _safe_location(field)}, name
        yield from walk(obj)
        return
    yield text.encode('utf-8'), {}, None


def _version_context(raw, match, field_name):
    # Never excuse an address inside a URL, even in a field named version.
    before = raw[max(0, match.start() - 200):match.start()]
    if re.search(rb'[a-z][a-z0-9+.-]*://[^\s\x22\x27<>]*$', before, re.I):
        return False
    if field_name and re.search(r'(?:^|[_.-])versions?$', field_name, re.I) and raw.strip() == match.group():
        return True
    return bool(re.search(rb'(?<![\w.-])[a-z0-9_.-]+\s*===?\s*$', before, re.I)
                or re.search(rb'(?:^|\b)(?:__version__|version)\s*[:=]\s*[\x22\x27]?$', before, re.I))


def inspect(data, path, history=False):
    """Return only safe locations and classifications, without matching values."""
    path = str(path)
    issues = {}

    def add(category, location=None):
        location = location or {}
        key = (category, tuple(sorted(location.items())))
        if key not in issues:
            issues[key] = {'path': _safe_location(path), 'category': category, 'count': 0, 'history': history, **location}
        issues[key]['count'] += 1

    def examine(raw, location, field_name=None):
        source = field_name in SOURCE_FIELDS
        raw = _mask_regex_definitions(raw, 'record.py' if source else path)
        for category, pattern in PATTERNS.items():
            if category == 'exact_response_time' and 'data/human-validation' not in path.replace('\\', '/'):
                continue
            if category == 'email' and path.replace('\\', '/').startswith('licenses/'):
                continue
            for match in pattern.finditer(raw):
                output_category = category
                if category == 'assigned_secret_value':
                    if not _secret_name(match.group('name').decode()):
                        continue
                    value = _assignment_value(match, path, source)
                    if value is None or _safe_named_value(match.group('name').decode(), value, path):
                        continue
                elif category == 'credential_url' and _placeholder(match.group('user')) and _placeholder(match.group('password')):
                    continue
                elif category == 'private_network':
                    try:
                        address = ipaddress.ip_address(match.group().decode())
                    except ValueError:
                        continue
                    if any(address in network for network in IP_EXEMPT) or _version_context(raw, match, field_name):
                        continue
                    output_category = 'external_ipv4' if address.is_global else 'private_network'
                elif category == 'private_ipv6':
                    try:
                        address = ipaddress.ip_address(match.group().decode())
                    except ValueError:
                        continue
                    if not address.is_private:
                        continue
                elif category == 'private_path' and not _private_path_context(raw, match, path):
                    continue
                elif category == 'email' and path.startswith(('<commit metadata', '<tag metadata')) and match.group().lower().endswith(b'@users.noreply.github.com'):
                    continue
                found = dict(location)
                if not found:
                    found['line'] = raw.count(b'\n', 0, match.start()) + 1
                add(output_category, found)
        if field_name and _secret_name(field_name) and not _safe_named_value(field_name, raw, path):
            add('assigned_secret_value', location)
        if field_name == 'reviewer' and raw.lower() in {b'jacky', b'conrad'}:
            add('named_reviewer_record', location)

    if _forbidden_path(path):
        add('forbidden_file')
    examine(path.encode('utf-8', 'surrogateescape'), {'line': 0})
    for raw, location, field_name in _record_views(data, path):
        examine(raw, location, field_name)
    return list(issues.values())


def _git_run(arguments, data=None):
    result = subprocess.run(['git', *arguments], cwd=ROOT, input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode:
        raise RuntimeError('Cannot inspect Git history; no diagnostic values are printed')
    return result.stdout


def _batch_object(process, oid):
    process.stdin.write(oid.encode() + b'\n')
    process.stdin.flush()
    header = process.stdout.readline().split()
    if len(header) != 3 or header[0].decode() != oid or not header[2].isdigit():
        raise RuntimeError('Invalid Git batch object header')
    size = int(header[2])
    data = process.stdout.read(size)
    if len(data) != size or process.stdout.read(1) != b'\n':
        raise RuntimeError('Truncated Git batch object')
    return header[1].decode(), data


def _scan_history():
    oids = list(dict.fromkeys(_git_run(['rev-list', '--objects', '--all', '--no-object-names']).decode('ascii').splitlines()))
    if not oids:
        return [], 0
    if not all(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', oid) for oid in oids):
        raise RuntimeError('Invalid Git object inventory')
    metadata = _git_run(['cat-file', '--batch-check'], ''.join(oid + '\n' for oid in oids).encode('ascii'))
    types = {}
    for line in metadata.splitlines():
        fields = line.split()
        if len(fields) != 3 or not fields[2].isdigit():
            raise RuntimeError('Invalid Git object metadata')
        types[fields[0].decode()] = fields[1].decode()
    if set(types) != set(oids):
        raise RuntimeError('Incomplete Git object inventory')
    findings, trees, roots = [], {}, set()
    blob_paths = {oid: set() for oid, kind in types.items() if kind == 'blob'}
    with subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
        for oid, kind in types.items():
            if kind == 'blob':
                continue
            actual, data = _batch_object(process, oid)
            if actual != kind:
                raise RuntimeError('Git object type changed during scan')
            if kind == 'tree':
                entries, offset, width = [], 0, len(oid) // 2
                while offset < len(data):
                    end = data.index(b'\0', offset)
                    mode, name = data[offset:end].split(b' ', 1)
                    child = data[end + 1:end + 1 + width]
                    if len(child) != width:
                        raise RuntimeError('Truncated Git tree object')
                    entries.append((mode, name.decode('utf-8', 'surrogateescape'), child.hex()))
                    offset = end + 1 + width
                trees[oid] = entries
            elif kind == 'commit':
                roots.add(data.split(b'\n', 1)[0].split()[1].decode())
                findings.extend(inspect(data, f'<commit metadata:{oid[:12]}>', True))
            elif kind == 'tag':
                lines = data.splitlines()
                if len(lines) > 1 and lines[1] == b'type tree':
                    roots.add(lines[0].split()[1].decode())
                findings.extend(inspect(data, f'<tag metadata:{oid[:12]}>', True))
        seen, pending = set(), [(tree, '') for tree in roots]
        while pending:
            tree, prefix = pending.pop()
            if (tree, prefix) in seen:
                continue
            seen.add((tree, prefix))
            for mode, name, child in trees[tree]:
                path = prefix + name
                if mode == b'40000':
                    pending.append((child, path + '/'))
                elif mode != b'160000':
                    blob_paths[child].add(path)
        for oid, paths in blob_paths.items():
            kind, data = _batch_object(process, oid)
            if kind != 'blob':
                raise RuntimeError('Git blob type changed during scan')
            for path in sorted(paths) or [f'<git blob:{oid[:12]}>']:
                findings.extend(inspect(data, path, True))
        process.stdin.close()
        if process.wait(timeout=30):
            raise RuntimeError('Git batch scan failed')
    return findings, len(blob_paths)


def scan(history=True):
    findings, count = [], 0
    for directory, directories, names in os.walk(ROOT, followlinks=False):
        directories[:] = sorted(name for name in directories if name not in SKIP_DIRS)
        for name in sorted(names):
            file = Path(directory) / name
            relative = file.relative_to(ROOT).as_posix()
            if file.is_symlink():
                findings.extend(inspect(os.fsencode(os.readlink(file)), relative))
                findings.append({'path': _safe_location(relative), 'category': 'forbidden_file', 'count': 1, 'history': False})
            elif file.is_file():
                findings.extend(inspect(file.read_bytes(), relative))
            else:
                findings.append({'path': _safe_location(relative), 'category': 'unsupported_file', 'count': 1, 'history': False})
            count += 1
    git_blobs = 0
    if history and (ROOT / '.git').exists():
        archived, git_blobs = _scan_history()
        findings.extend(archived)
    return {'status': 'PASS' if not findings else 'FAIL', 'text_files': count, 'files_scanned': count,
            'git_blobs': git_blobs, 'findings': findings,
            'limits': 'Pattern and literal-value checks cover all file extensions and reachable Git objects. Runtime caches are excluded from working-tree traversal. Git history covers reachable refs, not reflogs, unreachable objects or external submodules. Explicit placeholders and regex-definition literals are excluded. Plausible IPv4 literals can also be software versions; review findings. A clean scan is not proof of consent, licensing or absence of every possible secret.'}


if __name__ == '__main__':
    result = scan()
    print(json.dumps(result, indent=2))
    sys.exit(bool(result['findings']))
