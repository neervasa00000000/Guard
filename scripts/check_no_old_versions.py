#!/usr/bin/env python3
"""Fail if any file name, folder name, or text in code/docs/configs still names an old release.

Run from the repository root:  python3 scripts/check_no_old_versions.py
Scans `git ls-files` (plus untracked, not ignored). Data files (*.csv, *.csv.gz, *.gz, images)
are scanned by NAME only, because their cells are archived measurements that must not change.
results/reruns/recovered_sources/ is scanned by name only: verbatim, hash-listed copies of
older source files (see its manifest.json).
"""
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = re.compile(
    r"v1[._-][0-9]+(?:-artifact)?|\bv[0-9]+\.[0-9]+-artifact\b|-artifact\b|\bv9[._]?[0-9]+|exp-v[0-9]|"
    r"release-v[0-9]|review4|fontmatched|_v[0-9]+\b|\bv1[0-9]\b|v14_|\bV1_[0-9]|run_v[0-9]+|results/v[0-9]+\b|"
    r"earlier (?:draft|tag)s?|previous (?:draft|version)|v931|v932|v935|v918"
)
# Legitimate: GitHub Action versions, TileSeal file formats GRD1-3 and their verify_v1/verify_v2
# functions, the TLS flag, and the Docker image name that the verbatim recovered Dockerfile.forms
# builds FROM (results/reruns/recovered_sources/ may not be edited).
ALLOW = re.compile(r"actions/(?:checkout|setup-python)@v\d|GRD[123]|grd3|verify_v[12]\b|tlsv1\.2|guard-e1-review4")
NAME_ONLY_SUFFIX = ('.csv', '.gz', '.png', '.jpg', '.pdf', '.otf', '.ttf', '.npy', '.pkl')
NAME_ONLY_PREFIX = ('results/reruns/recovered_sources/',)
SELF = 'scripts/check_no_old_versions.py'

files = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
                       cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
hits = []
for f in files:
    if f == SELF or not (ROOT / f).is_file():
        continue
    for m in OLD.finditer(f):
        hits.append(f"{f}: (name) {m.group(0)}")
    if f.endswith(NAME_ONLY_SUFFIX) or f.startswith(NAME_ONLY_PREFIX):
        continue
    try:
        text = (ROOT / f).read_text()
    except UnicodeDecodeError:
        continue
    for n, line in enumerate(text.splitlines(), 1):
        for m in OLD.finditer(line):
            if ALLOW.search(line[max(0, m.start() - 20):m.end() + 20]):
                continue
            hits.append(f"{f}:{n}: {m.group(0)}  | {line.strip()[:140]}")
for h in hits:
    print(h)
print(f"OLD-VERSION HITS: {len(hits)}")
sys.exit(1 if hits else 0)
