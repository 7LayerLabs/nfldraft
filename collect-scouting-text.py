"""Cache the full NFL.com pre-draft prospect narratives for every drafted player (private, outside Git).

Run: python prepare-source-cache.py   (once)
     python collect-scouting-text.py

The narratives are copyrighted. They are stored only in the private source cache and used as input
for original write-ups; the published site keeps short attributed excerpts and links to the report.
Output: ~/.agent-reach/nfl-player-profiles/scouting-text.json  {draftId: {overview, strengths, weaknesses, bio, ...}}
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles'


def workouts_module():
    spec = importlib.util.spec_from_file_location('collect_workouts', ROOT / 'collect-workouts.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    w = workouts_module()
    auth = w.load_auth()
    drafts = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
    out = {}
    missing = []
    for year in sorted(drafts, key=int):
        profiles = w.fetch_year(int(year), auth)  # combine profiles carry the narrative fields
        by_person = {p['person']['id']: p for p in profiles if p.get('person')}
        for row in drafts[year]:
            pid = f'{year}-{row[1]}'
            profile = json.loads((ROOT / 'local' / 'data' / 'profiles' / f'{pid}.json').read_text(encoding='utf-8'))
            person = (profile.get('workouts') or {}).get('nflPersonId')
            record = by_person.get(person)
            if not record:
                missing.append(pid)
                continue
            text = {key: w.clean_text(record.get(key)) for key in ('overview', 'strengths', 'weaknesses', 'bio', 'sourcesTellUs')}
            bullets = {key: [w.clean_text(b) for b in re.findall(r'<li\b[^>]*>(.*?)</li>', str(record.get(key) or ''), re.I | re.S)]
                       for key in ('strengths', 'weaknesses')}
            out[pid] = {**{k: v for k, v in text.items() if v}, 'strengthBullets': bullets['strengths'],
                        'weaknessBullets': bullets['weaknesses'], 'grade': record.get('grade'),
                        'author': (record.get('author') or {}).get('displayName') if isinstance(record.get('author'), dict) else record.get('author')}
    path = CACHE / 'scouting-text.json'
    path.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    with_text = sum(1 for v in out.values() if v.get('overview') or v.get('strengths') or v.get('weaknesses'))
    print(f'Cached narratives for {with_text} of 2,569 players ({len(missing)} without an NFL.com profile match) -> {path}')


if __name__ == '__main__':
    main()
