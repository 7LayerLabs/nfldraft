"""Bootstrap public collector inputs outside the repository.

Run: python prepare-source-cache.py
Verify existing inputs without network/write access: python prepare-source-cache.py --check

Pinned public CSVs and the reviewed anonymous NFL web-client implementation are
cached under ~/.agent-reach/nfl-player-profiles. Primary school/team evidence for
reviewed college fallbacks is fetched there too. No bearer token is generated,
printed, or saved by this bootstrap. Raw source pages stay outside the Git checkout.
"""
from __future__ import annotations

import argparse
import ast
import base64
import csv
import io
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles'
DRAFT_COMMIT = 'ec10d74c22c32b86c5b74061605be3fd89e07f10'
SDK_COMMIT = '938df901a5d50b3224c438dde817b3e1e48eb3ab'
PUBLIC_INPUTS = [
    ('raw/combine_official.csv',
     f'https://raw.githubusercontent.com/array-carpenter/nfl-draft-data/{DRAFT_COMMIT}/data/combine_official.csv',
     {'year', 'player', 'person_id', 'height', 'weight', 'hand_size', 'arm_length'}),
    ('raw/combine_pro_day.csv',
     f'https://raw.githubusercontent.com/array-carpenter/nfl-draft-data/{DRAFT_COMMIT}/data/combine_pro_day.csv',
     {'Year', 'player', 'College', 'athlete_id', 'Height (in)', 'Weight (lbs)'}),
    ('games.py',
     f'https://raw.githubusercontent.com/sportsdataverse/sportsdataverse-py/{SDK_COMMIT}/sportsdataverse/nfl/nfl_games.py',
     None),
]


def school_evidence():
    """Read literal evidence metadata without importing/running the college collector."""
    tree = ast.parse((PROJECT / 'collect-college.py').read_text(encoding='utf-8'))
    records = []
    for node in tree.body:
        if not isinstance(node, ast.Assign): continue
        if not any(isinstance(target, ast.Name) and target.id == 'SCHOOL_FALLBACK' for target in node.targets): continue
        if not isinstance(node.value, ast.Dict): raise ValueError('Expected college fallback dictionary')
        for record in node.value.values:
            if not isinstance(record, ast.Dict): continue
            fields = {key.value: value.value for key, value in zip(record.keys, record.values)
                      if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)}
            if fields.get('rawFile') and fields.get('url'):
                records.append((f'college/{fields["rawFile"]}', fields['url']))
    return records


def get_public(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'NFLDraftArchive/1.0 public-source-bootstrap'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read(), response.headers.get('Content-Type', '')
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2: raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2: raise
        time.sleep(2 ** attempt)
    raise RuntimeError(f'Unable to fetch public source {url}')


def validate_input(filename, content, required_columns):
    text = content.decode('utf-8-sig')
    if required_columns is not None:
        columns = set(next(csv.reader(io.StringIO(text)), []))
        missing = required_columns - columns
        if missing: raise ValueError(f'{filename}: missing columns {sorted(missing)}')
    else:
        ast.parse(text)
        if 'def nfl_headers_gen' not in text or 'def nfl_token_gen' not in text:
            raise ValueError('Downloaded public NFL client lacks required anonymous authentication functions')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Read-only check; do not download or change anything')
    parser.add_argument('--refresh', action='store_true', help='Re-download public inputs and evidence')
    args = parser.parse_args()
    if args.check and args.refresh: parser.error('--check and --refresh are mutually exclusive')
    missing = []; evidence_failures = []
    for filename, url, required in PUBLIC_INPUTS:
        target = CACHE / filename
        if target.exists() and not args.refresh:
            validate_input(filename, target.read_bytes(), required)
            print(f'OK {filename}')
            continue
        if args.check:
            missing.append(filename); print(f'MISSING {filename}'); continue
        content, content_type = get_public(url)
        validate_input(filename, content, required)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        print(f'PREPARED {filename}')
    for filename, url in school_evidence():
        target = CACHE / filename
        if target.exists() and not args.refresh:
            print(f'OK {filename}'); continue
        if args.check:
            missing.append(filename); print(f'MISSING {filename}'); continue
        try:
            try:
                content, content_type = get_public(url)
                fetched_url = url
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
                # Public Jina Reader is the documented secondary reader for blocked pages.
                fetched_url = 'https://r.jina.ai/' + url
                content, content_type = get_public(fetched_url)
            record = {'url': url, 'fetchedUrl': fetched_url, 'status': 'ok',
                      'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      'contentType': content_type}
            try: record['text'] = content.decode('utf-8')
            except UnicodeDecodeError: record['base64'] = base64.b64encode(content).decode('ascii')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
            print(f'PREPARED {filename}')
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            evidence_failures.append(filename)
            print(f'UNAVAILABLE {filename}: {type(exc).__name__}; collector will mark its fallback unavailable')
    print(f'Source cache: {CACHE}')
    if missing:
        print('Run python prepare-source-cache.py to prepare missing public inputs.')
        raise SystemExit(1)
    if evidence_failures:
        print('Some primary evidence is unavailable; existing generated site data remains usable.')
    print('Ready: collect-workouts.py, then collect-college.py. Bearer tokens stay in memory during collection.')


if __name__ == '__main__': main()
