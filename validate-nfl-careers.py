"""Validate NFL career data: identities, season sequences, PFR spot checks and PFR career totals.

Run: python validate-nfl-careers.py
Compares each player's summed season rows with the career totals on PFR draft pages
(nflverse draft_picks release in the source cache). Writes validation/nfl-careers-validation.json.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from career_metrics import IN_PROGRESS_SEASON

ROOT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles' / 'nflverse'

# Published Pro Football Reference regular-season lines (draft id, season, field, value)
SPOT_CHECKS = [
    ('2017-10', 2018, 'pass_yds', 5097), ('2017-10', 2018, 'pass_td', 50), ('2017-10', 2018, 'int', 12),
    ('2017-10', 2018, 'gs', 16), ('2017-10', 2018, 'qb_wins', 12), ('2017-10', 2018, 'rating', 113.8),
    ('2017-10', 2018, 'anya', 8.89),
    ('2020-22', 2020, 'rec', 88), ('2020-22', 2020, 'rec_yds', 1400), ('2020-22', 2020, 'targets', 125),
    ('2021-5', 2021, 'rec', 81), ('2021-5', 2021, 'rec_yds', 1455), ('2021-5', 2021, 'rec_td', 13),
    ('2023-177', 2023, 'rec', 105), ('2023-177', 2023, 'rec_yds', 1486), ('2023-177', 2023, 'targets', 160),
    ('2018-2', 2018, 'carries', 261), ('2018-2', 2018, 'rush_yds', 1307), ('2018-2', 2018, 'rush_td', 11),
    ('2018-2', 2018, 'rec', 91), ('2018-2', 2018, 'rec_yds', 721),
    ('2017-30', 2021, 'sacks', 22.5), ('2021-12', 2021, 'sacks', 13), ('2017-1', 2023, 'sacks', 14),
    ('2022-4', 2022, 'pd', 20), ('2022-4', 2022, 'def_int', 2),
    ('2018-7', 2020, 'pass_yds', 4544), ('2018-7', 2020, 'pass_td', 37), ('2018-7', 2020, 'rush_yds', 421),
    ('2017-233', 2019, 'fgm', 34), ('2017-233', 2019, 'fga', 38),
    ('2017-2', 2017, 'gs', 12), ('2017-2', 2017, 'qb_wins', 4),
]
TOTALS = [('pass_attempts', 'att'), ('pass_completions', 'cmp'), ('pass_yards', 'pass_yds'), ('pass_tds', 'pass_td'),
          ('pass_ints', 'int'), ('rush_atts', 'carries'), ('rush_yards', 'rush_yds'), ('rush_tds', 'rush_td'),
          ('receptions', 'rec'), ('rec_yards', 'rec_yds'), ('rec_tds', 'rec_td'), ('def_ints', 'def_int'),
          ('def_sacks', 'sacks'), ('games', 'g'), ('probowls', 'pro_bowl'), ('allpro', 'all_pro')]
PFR_ONLY = {'pro_bowl', 'all_pro'}  # need the browser-collected PFR file


def main():
    drafts = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
    careers = json.loads((ROOT / 'local' / 'data' / 'nfl-careers.json').read_text(encoding='utf-8'))
    ids = {f'{y}-{row[1]}': (int(y), row[4]) for y, rows in drafts.items() for row in rows}
    failures = []
    assert set(careers['players']) == set(ids), 'Career players do not match the 2,569 draft selections'
    for pid, (year, name) in ids.items():
        seasons = careers['players'][pid]['seasons']
        expected = list(range(year, IN_PROGRESS_SEASON + 1))
        if [s['season'] for s in seasons] != expected or [s['cy'] for s in seasons] != [s - year + 1 for s in expected]:
            failures.append(f'{pid} {name}: season sequence')
        if any(s['g'] < 0 or (s.get('snap50') or 0) > s['g'] for s in seasons):
            failures.append(f'{pid} {name}: impossible games')
        for s in seasons:
            for side, usage in (s.get('usage') or {}).items():
                if usage.get('share', 0) > 1.001 or (usage.get('active') or 0) > 1.001:
                    failures.append(f'{pid} {name} {s["season"]}: {side} snap share above 100%')
    spot = []
    for pid, season, key, value in SPOT_CHECKS:
        row = next(s for s in careers['players'][pid]['seasons'] if s['season'] == season)
        ok = row.get(key) is not None and abs(row[key] - value) < 0.051
        spot.append({'id': pid, 'player': ids[pid][1], 'season': season, 'field': key, 'pfr': value, 'collected': row.get(key), 'ok': ok})
        if not ok:
            failures.append(f'Spot check {ids[pid][1]} {season} {key}: PFR {value}, collected {row.get(key)}')
    picks = {}
    with (CACHE / 'draft_picks.csv').open(encoding='utf-8') as handle:
        for row in csv.DictReader(handle):
            picks[f'{row["season"]}-{row["pick"]}'] = row
    # PFR draft-page totals were scraped part-way through the in-progress season (a week or so behind the
    # weekly stats), so only careers that ended before it are a strict test; active players are informational.
    totals = {}
    has_pfr = bool(careers.get('pfrBrowser'))
    for pfr_key, key in TOTALS:
        if key in PFR_ONLY and not has_pfr:
            continue
        result = {}
        for scope in ('finished', 'active'):
            checked = exact = close = 0
            worst = []
            for pid in ids:
                raw, last = picks[pid].get(pfr_key), picks[pid].get('to')
                if raw in ('', 'NA', None) or last in ('', 'NA', None):
                    continue
                # nflverse's last-season field can lag a comeback, so 2026 games also mark a career active
                active = int(last) >= IN_PROGRESS_SEASON or any(s['g'] for s in careers['players'][pid]['seasons'] if s['season'] == IN_PROGRESS_SEASON)
                if active != (scope == 'active'):
                    continue
                pfr = float(raw)
                ours = sum((s.get(key) or 0) + (s.get(key + '_st') or 0 if key in PFR_ONLY else 0) for s in careers['players'][pid]['seasons'])
                checked += 1
                diff = ours - pfr
                exact += abs(diff) < 0.01
                close += abs(diff) <= max(1, abs(pfr) * 0.02)
                worst.append((abs(diff), pid, ids[pid][1], pfr, ours))
            worst.sort(reverse=True)
            result[scope] = {'players': checked, 'exact': exact, 'within2pct': close,
                             'largest': [{'id': w[1], 'player': w[2], 'pfr': w[3], 'collected': w[4]} for w in worst[:5]]}
        totals[key] = {'pfrField': pfr_key, **result}
        f = result['finished']
        if f['players'] and f['within2pct'] / f['players'] < 0.98:
            failures.append(f'Career {key}: only {f["within2pct"]}/{f["players"]} finished careers within 2% of PFR totals')
    # PFR weighted career AV: best season x1.00, next x0.95, then 0.90 ... (rounded)
    if has_pfr:
        checked = close = 0
        worst = []
        for pid in ids:
            raw, last = picks[pid].get('w_av'), picks[pid].get('to')
            if raw in ('', 'NA', None) or last in ('', 'NA', None) or int(last) >= IN_PROGRESS_SEASON or                     any(s['g'] for s in careers['players'][pid]['seasons'] if s['season'] == IN_PROGRESS_SEASON):
                continue
            values = sorted((s.get('av') or 0 for s in careers['players'][pid]['seasons']), reverse=True)
            ours = round(sum(v * max(0, 1 - .05 * i) for i, v in enumerate(values)))
            checked += 1
            close += abs(ours - float(raw)) <= 1
            worst.append((abs(ours - float(raw)), ids[pid][1], float(raw), ours))
        worst.sort(reverse=True)
        totals['weighted_av'] = {'pfrField': 'w_av', 'finished': {'players': checked, 'exact': close, 'within2pct': close,
                                 'largest': [{'player': w[1], 'pfr': w[2], 'collected': w[3]} for w in worst[:5]]},
                                 'active': {'players': 0, 'exact': 0, 'within2pct': 0, 'largest': []}}
        if checked and close / checked < .95:
            failures.append(f'Weighted AV: only {close}/{checked} finished careers within 1 of PFR')
    report = {'asOf': careers['asOf'], 'players': len(ids), 'spotChecks': spot, 'careerTotalsVsPfr': totals,
              'identity': {k: v for k, v in careers['identity'].items() if k != 'advancedRowConflicts'},
              'advancedRowConflicts': len(careers['identity']['advancedRowConflicts']), 'failures': failures}
    out = ROOT / 'validation' / 'nfl-careers-validation.json'
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8', newline='\n')
    print(f'Spot checks: {sum(s["ok"] for s in spot)}/{len(spot)} match PFR')
    print('Career totals vs PFR draft pages (finished careers = strict; active = PFR snapshot lags the weekly stats):')
    for key, t in totals.items():
        f, a = t['finished'], t['active']
        print(f'  {key:9} finished exact {f["exact"]:4}/{f["players"]:4} (within 2% {f["within2pct"]:4})   active within 2% {a["within2pct"]:4}/{a["players"]:4}   worst finished: ' +
              ', '.join(f'{w["player"]} {w["pfr"]:g} vs {w["collected"]:g}' for w in f['largest'][:2]))
    if failures:
        print('FAILURES:\n  ' + '\n  '.join(failures[:40]))
        return 1
    print('All NFL career validations passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
