"""Offline saved-data checks; verify archives before disposable recomputation."""
import argparse
import ast
import csv
import json
import tempfile
from pathlib import Path

from common import ROOT, save, sha
from reproduce_automatic import reproduce as automatic
from reproduce_human import reproduce as human
from reproduce_judge_diagnostics import reproduce as judge
from reproduce_exploratory import reproduce as exploratory


def verify_manifests():
    """Check archived bytes without normalizing or rewriting any input."""
    count = 0
    with (ROOT / 'manifests/files.csv').open(encoding='utf-8', newline='') as stream:
        for record in csv.DictReader(stream):
            path = record['path']
            if sha((ROOT / path).read_bytes()) != record['sha256']:
                raise ValueError(f'Archived SHA-256 mismatch: {path}')
            count += 1
    for line in (ROOT / 'manifests/sha256.txt').read_text(encoding='utf-8').splitlines():
        expected, path = line.split('  ', 1)
        if sha((ROOT / path).read_bytes()) != expected:
            raise ValueError(f'Archived SHA-256 mismatch: {path}')
    return {'status': 'PASS', 'files': count}


def recompute(output, manifest):
    results = {}
    checks = [
        ('automatic', 'automatic.json', automatic),
        ('human', 'human.json', human),
        ('judge', 'judge-diagnostics.json', judge),
        ('exploratory', 'exploratory.json', exploratory),
    ]
    for key, name, produce in checks:
        result = produce()
        save(output / name, result)
        archived = json.loads((ROOT / 'verification' / name).read_text(encoding='utf-8-sig'))
        regenerated = json.loads((output / name).read_text(encoding='utf-8'))
        # JSON values, including numbers and nested structure, must agree exactly.
        # Archived CRLF and newly serialized LF are intentionally not compared as bytes.
        if regenerated != archived:
            raise ValueError(f'Recomputed JSON differs from archive: verification/{name}')
        results[key] = result
    results['manifest'] = manifest
    results['derived_comparison'] = {'status': 'PASS', 'files': len(checks), 'method': 'Parsed JSON equality'}
    for path in ROOT.rglob('*.py'):
        if 'runs' not in path.relative_to(ROOT).parts:
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    results['syntax'] = {'status': 'PASS'}
    results['not_verified'] = [
        'Fresh GPU training and generated outputs',
        'Original adapter weights and immutable model/dataset/Judge revisions',
        'External-developer preference generalisation and per-finding Judge accuracy',
    ]
    save(output / 'verification-report.json', results)
    return results


def verify(output_dir=None):
    # Check all immutable bytes first, including archived verification snapshots.
    manifest = verify_manifests()
    if output_dir is None:
        with tempfile.TemporaryDirectory(prefix='better-code-rl-verify-') as directory:
            return recompute(Path(directory), manifest)
    output = Path(output_dir).resolve()
    root = ROOT.resolve()
    if output == root or root in output.parents and output.parts[len(root.parts)] != 'runs':
        raise ValueError('Output must be under runs/ or outside the repository')
    # Refuse existing directories so an explicit output cannot overwrite evidence.
    output.mkdir(parents=True, exist_ok=False)
    return recompute(output, manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', help='Keep LF JSON in a new directory under runs/ or outside the repository; default: temporary output, removed afterward')
    args = parser.parse_args(argv)
    results = verify(args.output_dir)
    print(json.dumps({
        'status': 'PASS (saved-data checks only)',
        'heldout_rows': results['automatic']['heldout_rows'],
        'training_rows': results['automatic']['training_rows'],
        'formal_human_responses': results['human']['responses'],
        'unique_pairs': results['human']['unique_pairs'],
        'kappa': results['human']['overlap']['kappa'],
        'derived_comparison': results['derived_comparison'],
        'output_dir': str(Path(args.output_dir).resolve()) if args.output_dir else None,
        'not_verified': results['not_verified'],
    }, indent=2))


if __name__ == '__main__':
    main()
