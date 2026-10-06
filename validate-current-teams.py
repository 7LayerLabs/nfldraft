"""Validate the published roster/status snapshot and, when present, raw source evidence.

Run python validate-current-teams.py. Add --require-source-cache after collecting
to require independent row-by-row reconciliation with the private NFL/ESPN cache.
This performs no network calls and writes only a compact public validation report.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-current-teams'


def load(path): return json.loads(path.read_text(encoding='utf-8'))


def check(condition, message):
    if not condition: raise AssertionError(message)


def validate(require_source_cache=False):
    spec = importlib.util.spec_from_file_location('current_team_collector', PROJECT / 'collect-current-teams.py')
    collector = importlib.util.module_from_spec(spec); spec.loader.exec_module(collector)
    payload = load(PROJECT / 'local/data/current-teams.json')
    entries = collector.draft_entries(); players = payload['players']; coverage = payload['coverage']
    check(set(players) == set(entries) and len(players) == 2569, 'Draft key coverage must be complete and exact')
    check(coverage['completeRosterFetch'] and coverage['nflTeamsFetched'] == coverage['espnTeamsFetched'] == 32,
          'Incomplete 32-team snapshot')
    check(not any(coverage.get(k) for k in ['ambiguousMatches', 'sourceDisagreements', 'statusIdentityFailures']),
          'Unresolved source/identity discrepancies')
    check(payload['fetchedAt'][:10] == payload['asOf'], 'Published observation dates disagree')
    check(coverage['nflFetchedAt'][:10] == payload['asOf'], 'NFL source date mismatch')
    check(all(d[:10] == payload['asOf'] for d in coverage['espnRosterFetchedAtRange']), 'ESPN source date mismatch')
    valid_codes = {'ari','atl','bal','buf','car','chi','cin','cle','dal','den','det','gb','hou','ind','jax','kc',
                   'lac','lar','lv','mia','min','ne','no','nyg','nyj','phi','pit','sea','sf','tb','ten','wsh'}
    athlete_ids = defaultdict(list); nfl_ids = defaultdict(list)
    overrides = load(PROJECT / 'validation/current-team-status-overrides.json')['profiles']
    for key, record in players.items():
        check(record['statusLabel'] and not record['statusLabel'].startswith('--'), f'Invalid status label: {key}')
        check(record['statusAsOf'] == payload['asOf'], f'Per-player status observation date mismatch: {key}')
        for field in ['sourceUrl', 'statusSourceUrl']:
            url = record.get(field)
            check(not url or url.startswith('https://') and 'api.nfl.com' not in url and 'api.espn.com' not in url,
                  f'Public source link is not a usable webpage: {key}')
        if record['team']:
            check(record['teamCode'] in valid_codes and record['leagueStatus'] == 'rostered' and record['sourceUrl'],
                  f'Incomplete live team evidence: {key}')
        else:
            check(record['teamCode'] is None and record['rosterStatus'] is None, f'Historical team leaked: {key}')
            check(record['leagueStatus'] == 'unrostered/unknown' or record['statusSourceUrl'], f'Unsupported status: {key}')
        if record['leagueStatus'] in {'retired','deceased'}:
            check(key in overrides and overrides[key]['sourceUrl'] == record['statusSourceUrl'], f'Unreviewed retirement/death: {key}')
        if record.get('athleteId'): athlete_ids[record['athleteId']].append(key)
        if record.get('nflPersonId'): nfl_ids[record['nflPersonId']].append(key)
    check(not any(len(v) > 1 for v in athlete_ids.values()), 'ESPN ID assigned to multiple draft identities')
    check(not any(len(v) > 1 for v in nfl_ids.values()), 'NFL ID assigned to multiple draft identities')
    check(dict(Counter(r['leagueStatus'] for r in players.values())) == coverage['leagueStatuses'], 'Status totals mismatch')
    check(sum(bool(r['team']) for r in players.values()) == coverage['teamMembers'], 'Roster total mismatch')

    # A deliberately incomplete NFL response must reject publication before any
    # ESPN requests or output mutation. This tests the actual collection guard.
    before = (PROJECT / 'local/data/current-teams.json').read_bytes()
    original_cached, original_auth = collector.cached_roster, collector.auth_headers
    collector.auth_headers = lambda: {}
    collector.cached_roster = lambda *a, **kw: {'data': {'rosters': [{'team': {'id': str(i)}} for i in range(31)]}}
    try:
        try: collector.fetch_rosters(coverage['season'], payload['asOf'], True)
        except ValueError as exc: check('32 distinct teams' in str(exc), 'Wrong incomplete-fetch rejection')
        else: raise AssertionError('31-team source did not reject')
    finally:
        collector.cached_roster, collector.auth_headers = original_cached, original_auth
    check((PROJECT / 'local/data/current-teams.json').read_bytes() == before, 'Failed collection changed publication')

    source_verified = False
    if (CACHE / 'nfl-rosters.json').exists() and (CACHE / 'espn-rosters').exists():
        nfl = load(CACHE / 'nfl-rosters.json'); espn = [load(p) for p in (CACHE / 'espn-rosters').glob('*.json')]
        check(len(nfl['data']['rosters']) == len(espn) == 32, 'Private source cache is incomplete')
        check(nfl['fetchedAt'][:10] == payload['asOf'] and all(e['fetchedAt'][:10] == payload['asOf'] for e in espn),
              'Private source cache dates disagree')
        nfl_members = defaultdict(list); espn_members = defaultdict(list)
        for roster in nfl['data']['rosters']:
            code = collector.team_code(roster['team']['abbreviation'])
            for person in roster['persons']: nfl_members[person['id']].append((code, person['status']))
        for envelope in espn:
            code = collector.team_code(envelope['data']['team']['abbreviation'])
            for group in envelope['data']['athletes']:
                for athlete in group.get('items', []): espn_members[str(athlete['id'])].append((code, group['position']))
        for key, record in players.items():
            nfl_rows = nfl_members.get(record.get('nflPersonId'), [])
            espn_rows = espn_members.get(record.get('athleteId'), [])
            if record['team']:
                code = record['teamCode']
                live_nfl = any(c == code and (s in collector.NFL_MEMBER_STATUSES or s == 'RSR' and any(ec == code for ec, _ in espn_rows)) for c, s in nfl_rows)
                check(live_nfl or any(c == code for c, _ in espn_rows), f'Membership lacks current roster evidence: {key}')
            if record['leagueStatus'] in {'free-agent','inactive','unsigned','suspended'}:
                athlete = load(CACHE / 'status-espn-cache' / f'{record["athleteId"]}.json')['athlete']
                check(athlete['status']['type'] == record['leagueStatus'], f'Individual status evidence mismatch: {key}')
                draft = athlete.get('draft', {})
                check(str(draft.get('year')) == str(entries[key]['year']) and str(draft.get('selection')) == str(entries[key]['pick']),
                      f'Individual draft identity evidence mismatch: {key}')
        source_verified = True
    check(source_verified or not require_source_cache, 'Required private source cache is unavailable')

    # Dated regression examples cover trades, reserves, practice squad, retirement,
    # deceased players and the ambiguous names that previously caused bad joins.
    fixtures = {
        '2017-8': ('sf','rostered','3117251'), '2017-10': ('kc','rostered','3139477'),
        '2018-1': ('tb','rostered','3052587'), '2018-3': ('sea','rostered','3912547'),
        '2018-44': ('sf','rostered','3127306'),
        '2017-32': (None,'retired','3917676'), '2017-249': (None,'retired','3919596'),
        '2019-15': (None,'deceased','4040616'),
        '2019-79': ('no','rostered','4046536'), '2019-188': (None,'free-agent','3916074'),
        '2021-107': ('ten','rostered','4240657'), '2021-154': ('phi','rostered','4240456'),
        '2023-70': ('phi','rostered','4567123'), '2023-77': ('lar','rostered','4875196'),
        '2022-24': ('dal','rostered','4568652')}
    if payload['asOf'] == '2026-10-06':
        for key, expected in fixtures.items():
            actual = players[key]
            check((actual['teamCode'],actual['leagueStatus'],actual['athleteId']) == expected, f'Dated fixture failed: {key}')
        check(players['2018-44']['rosterStatus'].lower() == 'practice squad', 'Practice-squad fixture missing')
        check(players['2019-16']['rosterStatus'] == 'Reserve', 'Reserve fixture missing')
        check(players['2017-5']['leagueStatus'] != 'retired', 'Corey Davis comeback was ignored')
        check(players['2019-60']['leagueStatus'] != 'retired', 'Nasir Adderley comeback was ignored')
    report = {'passed': True, 'asOf': payload['asOf'], 'players': len(players), 'teams': 32,
              'privateSourceEvidenceVerified': source_verified, 'incompleteFetchPreservesPublication': True,
              'leagueStatuses': coverage['leagueStatuses'], 'datedRegressionExamples': list(fixtures),
              'unknownStatuses': [{'id': k,'name': entries[k]['name']} for k,r in players.items() if r['leagueStatus'] == 'unrostered/unknown']}
    target = PROJECT / 'validation/current-teams-validation.json'
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-source-cache', action='store_true')
    validate(parser.parse_args().require_source_cache)
