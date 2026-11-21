"""Secret Scanner for pre-commit / pre-push hygiene."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    '.venv', 'venv', 'node_modules', 'dist', 'projects',
    '.pytest_cache', '__pycache__', '.git', 'temp', 'tmp', 'cache'
}

PATTERNS = [
    ('GitHub Token', re.compile(r'ghp_[A-Za-z0-9]{20,40}|github_pat_[A-Za-z0-9_]{50,90}')),
    ('Google/Gemini API Key', re.compile(r'AIza[0-9A-Za-z-_]{35}')),
    ('OAuth Bearer Token', re.compile(r'ya29\.[0-9A-Za-z-_]+')),
    ('Private Key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('AWS Secret Key', re.compile(r'(?i)aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}')),
    ('Generic Secret/Token Assignment', re.compile(r'(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key|password)\s*[:=]\s*[\'"][A-Za-z0-9_\-\.]{16,}[\'"]'))
]

def scan():
    findings = []
    scanned_files = 0

    for p in ROOT.rglob('*'):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in {'.mp4', '.mkv', '.mov', '.webm', '.avi', '.wav', '.mp3', '.jpg', '.jpeg', '.png', '.pyc', '.pyd', '.dll', '.exe', '.so', '.tar', '.gz', '.zip', '.ico'}:
            continue

        scanned_files += 1
        try:
            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                for line_no, line in enumerate(f, 1):
                    if p.name == '.env.example':
                        continue
                    for name, pat in PATTERNS:
                        if pat.search(line):
                            findings.append((str(p.relative_to(ROOT)), line_no, name))
        except Exception:
            pass

    print(f"Scanned {scanned_files} files.")
    print(f"Total findings: {len(findings)}")
    for file_rel, line_no, name in findings:
        print(f"  [ALERT] {name} in {file_rel}:{line_no}")
    return findings

if __name__ == '__main__':
    scan()
