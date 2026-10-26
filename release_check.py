"""Check explicit public files and hashes; optionally export without Git history."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent
PATTERNS = {
    'private_path': r'/(?:Users|Volumes|home)/',
    'private_key': r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    'service_token': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9]{20,})\b',
    'credential_assignment': r'''(?i)(?:api_key|api_secret|password|access_token)\s*[:=]\s*["'][^"'\s]{8,}["']''',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    'network_or_broker_import': r'(?m)^\s*(?:from|import)\s+(?:requests|httpx|urllib|socket|alpaca|yfinance|qlib)\b',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', type=Path)
    args = parser.parse_args()
    names = (ROOT / 'PUBLIC_FILES.txt').read_text().splitlines()
    if len(names) != len(set(names)) or not names:
        raise ValueError('Manifest must be nonempty and unique')
    hashes = json.loads((ROOT / 'SHA256SUMS.json').read_text())
    if set(hashes) != set(names) - {'SHA256SUMS.json'}:
        raise ValueError('Hash inventory differs from allowlist')
    findings = []
    for name in names:
        path = ROOT / name
        if Path(name).is_absolute() or '..' in Path(name).parts or path.is_symlink():
            raise ValueError(f'Unsafe manifest path: {name}')
        if not path.is_file() or path.resolve() != path.absolute():
            raise ValueError(f'Not an ordinary local file: {name}')
        raw = path.read_bytes()
        if name in hashes and hashlib.sha256(raw).hexdigest() != hashes[name]:
            raise ValueError(f'Hash mismatch: {name}')
        for number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
            for category, pattern in PATTERNS.items():
                if re.search(pattern, line):
                    findings.append({'file': name, 'line': number, 'category': category})
    if findings:
        print(json.dumps(findings, indent=2))
        raise SystemExit('Review required: pattern findings; contents not printed')
    print(f'PASS: {len(names)} allowlisted text files; hashes match; no configured pattern findings')
    if args.export:
        destination = args.export.resolve()
        if destination == ROOT or ROOT in destination.parents:
            raise ValueError('Export outside this candidate directory')
        destination.mkdir(parents=True, exist_ok=False)
        for name in names:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        print('Exported allowlisted files only; no repository history')


if __name__ == '__main__':
    main()
