"""Refresh current NFL team membership and explicit league status for all draft picks.

NFL and ESPN rosters must both cover all 32 teams before a snapshot can publish.
Released/terminated NFL roster rows and historical ESPN athlete team references
never assign a current team. Raw data and anonymous tokens stay outside Git.

Prerequisites: pip install -r requirements.txt; python prepare-source-cache.py
Refresh: python collect-current-teams.py
Rebuild today's already-fetched sources: python collect-current-teams.py --reuse-cache
Force another complete ESPN status refresh: add --refresh-statuses.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime as dt
import importlib.util
import io
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-current-teams'
PROFILE_CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles'
OUTPUT = PROJECT / 'local' / 'data' / 'current-teams.json'
NFL_URL = 'https://api.nfl.com/football/v2/rosters'
ESPN_TEAMS_URL = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams?limit=100'
ESPN_ROSTER_BASE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams'
ESPN_ATHLETE_BASE = 'https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes'
NFLVERSE_PLAYERS_URL = 'https://github.com/nflverse/nflverse-data/releases/download/players/players.csv'
# These codes explicitly retain active, practice or reserve membership. RSR is
# ambiguous/released-from-IR and must be corroborated by a current ESPN team roster.
NFL_MEMBER_STATUSES = {'ACT', 'DEV', 'RES', 'PUP', 'RSN', 'EXE', 'SUS', 'INA', 'NWT', 'NON'}
NFL_NONMEMBER_STATUSES = {'CUT', 'TRC', 'TRD', 'TRT', 'RLS', 'RET', 'RSR'}
NFL_STATUS_LABELS = {'ACT': 'Active', 'DEV': 'Practice squad', 'RES': 'Reserve',
                     'PUP': 'Physically unable to perform', 'RSN': 'Non-football reserve',
                     'EXE': 'Exempt', 'SUS': 'Suspended', 'INA': 'Inactive roster',
                     'NWT': 'Not with team', 'NON': 'Non-football reserve', 'RSR': 'Reserve / out'}
ESPN_STATUS_MAP = {'free-agent': ('free-agent', 'Free agent'), 'retired': ('retired', 'Retired'),
                   'unsigned': ('unsigned', 'Unsigned'), 'inactive': ('inactive', 'Inactive'),
                   'suspended': ('suspended', 'Suspended')}
TEAM_CODES = {'AZ': 'ari', 'ARI': 'ari', 'ARZ': 'ari', 'JAX': 'jax', 'JAC': 'jax',
              'WAS': 'wsh', 'WSH': 'wsh', 'LA': 'lar'}
NAME_ALIASES = {'mitchelltrubisky': 'mitchtrubisky', 'lanohill': 'delanohill',
                'joshallen': 'joshhinesallen', 'takkaristmckinley': 'takkmckinley',
                'gabedavis': 'gabrieldavis', 'camward': 'cameronward',
                'buckyhodges': 'temuchinhodges', 'drewogletree': 'andrewogletree',
                'boogiebasham': 'carlosbasham', 'shaqleonard': 'shaquilleleonard',
                'dariusleonard': 'shaquilleleonard'}
SCHOOL_ALIASES = {'miamifl': 'miami', 'miamiflorida': 'miami', 'olemiss': 'mississippi',
                  'lsu': 'louisianastate', 'usc': 'southerncalifornia', 'uconn': 'connecticut',
                  'ucf': 'centralflorida', 'fiu': 'floridainternational', 'byu': 'brighamyoung',
                  'utep': 'texaselpaso', 'ncstate': 'northcarolinastate', 'pitt': 'pittsburgh',
                  'tcu': 'texaschristian', 'utsa': 'texassanantonio', 'smu': 'southernmethodist',
                  'cal': 'california', 'louisianalafayette': 'louisiana'}


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in value.lower() if not unicodedata.combining(c)))


def name_key(value):
    value = re.sub(r'\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$', '', str(value or ''), flags=re.I)
    key = normalized(value)
    return NAME_ALIASES.get(key, key)


def school_key(value):
    key = normalized(value)
    return SCHOOL_ALIASES.get(key, key)


def team_code(value): return TEAM_CODES.get(value.upper(), value.lower())


def request_json(url, params=None, headers=None):
    for attempt in range(4):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=35)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3: response.raise_for_status()
                retry = response.headers.get('Retry-After', '')
                time.sleep(min(int(retry) if retry.isdigit() else 2 ** attempt, 20)); continue
            response.raise_for_status()
            return {'url': response.url, 'fetchedAt': now(), 'data': response.json()}
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 3: raise
            time.sleep(2 ** attempt)
    raise RuntimeError(f'Unable to fetch {url}')


def save_private(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')


def cached_roster(path, url, asof, reuse, params=None, headers=None):
    if reuse and path.exists():
        record = json.loads(path.read_text(encoding='utf-8'))
        if record['fetchedAt'][:10] != asof:
            raise ValueError(f'Cached source date differs from {asof}; refresh instead of --reuse-cache')
        return record
    record = request_json(url, params=params, headers=headers)
    save_private(path, record)
    return record


def auth_headers():
    path = PROFILE_CACHE / 'games.py'
    if not path.exists(): raise RuntimeError('Run python prepare-source-cache.py to prepare the public anonymous NFL client')
    spec = importlib.util.spec_from_file_location('anonymous_nfl_current_rosters', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.nfl_headers_gen()


def fetch_rosters(season, asof, reuse):
    nfl = cached_roster(CACHE / 'nfl-rosters.json', NFL_URL, asof, reuse,
                        params={'season': season, 'limit': 40}, headers=auth_headers())
    nfl_teams = nfl['data'].get('rosters', [])
    if nfl['data'].get('pagination', {}).get('token'):
        raise ValueError('NFL rosters are paginated; refusing an incomplete 32-team snapshot')
    if len(nfl_teams) != 32 or len({t['team']['id'] for t in nfl_teams}) != 32:
        raise ValueError('NFL roster source does not contain exactly 32 distinct teams')
    if any(t.get('season') != season or not isinstance(t.get('persons'), list) for t in nfl_teams):
        raise ValueError('NFL season or roster schema mismatch')
    teams = cached_roster(CACHE / 'espn-teams.json', ESPN_TEAMS_URL, asof, reuse)
    leagues = [league for sport in teams['data'].get('sports', []) for league in sport.get('leagues', [])]
    rows = [entry['team'] for league in leagues for entry in league.get('teams', [])]
    if len(rows) != 32 or len({t['id'] for t in rows}) != 32:
        raise ValueError('ESPN index does not contain exactly 32 distinct teams')
    def fetch(team):
        record = cached_roster(CACHE / 'espn-rosters' / f'{team["id"]}.json',
                               f'{ESPN_ROSTER_BASE}/{team["id"]}/roster', asof, reuse,
                               params={'season': season, 'limit': 500})
        payload = record['data']
        if str(payload.get('team', {}).get('id')) != str(team['id']): raise ValueError('ESPN team ID mismatch')
        if payload.get('season', {}).get('year') != season: raise ValueError('ESPN roster season mismatch')
        if not isinstance(payload.get('athletes'), list): raise ValueError('ESPN roster is incomplete')
        total = sum(len(group.get('items', [])) for group in payload['athletes'])
        if total < 45: raise ValueError(f'Unexpectedly short ESPN roster: {team["displayName"]}: {total}')
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        espn = list(pool.map(fetch, rows))
    if {team_code(t['team']['abbreviation']) for t in nfl_teams} != {team_code(t['data']['team']['abbreviation']) for t in espn}:
        raise ValueError('NFL and ESPN 32-team sets disagree')
    print(f'Fresh roster scope verified: NFL 32 / ESPN {len(espn)} teams', flush=True)
    return nfl, espn


def draft_entries():
    raw = json.loads((PROJECT / 'drafts.json').read_text(encoding='utf-8'))
    entries = {}
    for year, picks in raw.items():
        for p in picks:
            key = f'{year}-{p[1]}'
            entries[key] = {'id': key, 'year': int(year), 'pick': p[1], 'name': p[4], 'position': p[5], 'college': p[6]}
    return entries


def nflverse_identities(entries, asof, reuse):
    target = CACHE / 'status-players.csv'
    if not reuse or not target.exists():
        response = requests.get(NFLVERSE_PLAYERS_URL, timeout=45); response.raise_for_status()
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(response.content)
    rows = list(csv.DictReader(io.StringIO(target.read_text(encoding='utf-8-sig'))))
    required = {'draft_year', 'draft_pick', 'espn_id', 'smart_id', 'gsis_id', 'display_name'}
    if not rows or not required.issubset(rows[0]): raise ValueError('NFLverse identity schema mismatch')
    candidates = defaultdict(list)
    for row in rows:
        if row.get('draft_year') and row.get('draft_pick'):
            candidates[f'{row["draft_year"]}-{row["draft_pick"]}'].append(row)
    identities = {}
    for key, entry in entries.items():
        matches = candidates.get(key, [])
        if len(matches) != 1: continue
        row = matches[0]
        # The immutable draft year/overall pick is independently checked against
        # ESPN draft metadata below. Names/college disambiguate changed identities.
        if name_key(row.get('display_name')) != name_key(entry['name']):
            schools = {school_key(c) for c in row.get('college_name', '').split(';')}
            if school_key(entry['college']) not in schools: continue
        identities[key] = row
    return identities


def fetch_statuses(entries, identities, asof, reuse, force):
    cache = CACHE / 'status-espn-cache'; cache.mkdir(parents=True, exist_ok=True)
    def fetch(item):
        key, row = item; eid = row.get('espn_id')
        if not eid: return key, None
        path = cache / f'{eid}.json'
        url = f'{ESPN_ATHLETE_BASE}/{eid}?lang=en&region=us'
        stored = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        recent = bool(stored and stored.get('fetchedAt', '')[:10] == asof)
        if recent and not reuse:
            age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(stored['fetchedAt'])
            recent = age.total_seconds() < 900
        try:
            if not stored or force or not recent:
                envelope = request_json(url)
                stored = {'fetchedAt': envelope['fetchedAt'], 'sourceUrl': envelope['url'], 'athlete': envelope['data']}
                save_private(path, stored)
            athlete = stored['athlete']; draft = athlete.get('draft', {})
            verified = (str(athlete.get('id')) == str(eid)
                        and str(draft.get('year', entries[key]['year'])) == str(entries[key]['year'])
                        and str(draft.get('selection', entries[key]['pick'])) == str(entries[key]['pick']))
            if not verified: return key, {'identityVerified': False, 'sourceUrl': url}
            status = athlete.get('status', {})
            league, label = ESPN_STATUS_MAP.get(status.get('type'), ('unrostered/unknown', 'Status unconfirmed'))
            return key, {'identityVerified': True, 'leagueStatus': league, 'statusLabel': label,
                         'statusSourceUrl': f'https://www.espn.com/nfl/player/_/id/{eid}', 'statusAsOf': stored['fetchedAt'][:10],
                         'sourceRawStatus': status, 'athleteId': str(athlete['id']), 'identity': row}
        except requests.RequestException as exc:
            return key, {'identityVerified': False, 'error': type(exc).__name__, 'sourceUrl': url}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(fetch, identities.items()))
    return results


def published_nfl_ids(entries):
    ids = {}
    for key in entries:
        path = PROJECT / 'local' / 'data' / 'profiles' / f'{key}.json'
        if path.exists():
            profile = json.loads(path.read_text(encoding='utf-8'))
            person_id = profile.get('workouts', {}).get('nflPersonId')
            if person_id: ids[key] = person_id
    return ids


def build_mapping(entries, identities, statuses, nfl, espn, asof):
    reviewed = json.loads((PROJECT / 'validation' / 'current-team-status-overrides.json').read_text(encoding='utf-8'))['profiles']
    nfl_by_id = defaultdict(list); nfl_by_gsis = defaultdict(list); nfl_by_name = defaultdict(list)
    espn_by_id = defaultdict(list); espn_by_name = defaultdict(list)
    raw_nfl_counts = Counter(); raw_espn_counts = Counter()
    for roster in nfl['data']['rosters']:
        team = roster['team']; code = team_code(team['abbreviation'])
        for person in roster['persons']:
            raw_nfl_counts[person.get('status')] += 1
            item = {'team': team['fullName'], 'teamCode': code, 'rosterStatus': NFL_STATUS_LABELS.get(person.get('status'), person.get('status')),
                    'sourceUrl': f'https://www.espn.com/nfl/team/roster/_/name/{code}', 'person': person, 'source': 'nfl'}
            nfl_by_id[person['id']].append(item)
            if person.get('gsisId'): nfl_by_gsis[person['gsisId']].append(item)
            nfl_by_name[name_key(person['displayName'])].append(item)
    for envelope in espn:
        payload = envelope['data']; team = payload['team']; code = team_code(team['abbreviation'])
        for group in payload['athletes']:
            for athlete in group.get('items', []):
                raw_espn_counts[group['position']] += 1
                item = {'team': team['displayName'], 'teamCode': code, 'rosterStatus': athlete.get('status', {}).get('name') or group['position'],
                        'sourceUrl': f'https://www.espn.com/nfl/team/roster/_/name/{code}', 'athlete': athlete, 'group': group['position'], 'source': 'espn'}
                espn_by_id[str(athlete['id'])].append(item)
                espn_by_name[name_key(athlete.get('fullName') or athlete.get('displayName'))].append(item)
    published = published_nfl_ids(entries)
    players = {}; ambiguous = []; disagreements = []; status_conflicts = []
    for key, entry in entries.items():
        identity = identities.get(key, {}); status = statuses.get(key) or {}
        person_id = published.get(key) or identity.get('smart_id')
        espn_id = identity.get('espn_id')
        nfl_matches = nfl_by_id.get(person_id, []) if person_id else []
        method = 'NFL person ID from verified draft profile' if nfl_matches else None
        if not nfl_matches and identity.get('gsis_id'):
            nfl_matches = nfl_by_gsis.get(identity['gsis_id'], [])
            if nfl_matches: method = 'NFL GSIS ID + draft year/overall pick'
        if not nfl_matches:
            named = nfl_by_name.get(name_key(entry['name']), [])
            nfl_matches = [r for r in named if school_key(entry['college']) in {school_key(s) for s in r['person'].get('collegeNames', [])}]
            if nfl_matches: method = 'Exact normalized name + college'
        espn_matches = espn_by_id.get(str(espn_id), []) if espn_id and status.get('identityVerified') else []
        if not espn_matches:
            espn_matches = [r for r in espn_by_name.get(name_key(entry['name']), [])
                            if school_key(r['athlete'].get('college', {}).get('name')) == school_key(entry['college'])]
        espn_teams = {r['teamCode'] for r in espn_matches}
        valid_nfl = [r for r in nfl_matches if r['person'].get('status') in NFL_MEMBER_STATUSES
                     or r['person'].get('status') == 'RSR' and r['teamCode'] in espn_teams]
        nfl_teams = {r['teamCode'] for r in valid_nfl}
        chosen = None
        if len(nfl_teams) == 1:
            chosen = sorted(valid_nfl, key=lambda r: 0 if r['person'].get('status') == 'ACT' else 1)[0]
            if espn_teams and espn_teams != nfl_teams:
                disagreements.append({'id': key, 'name': entry['name'], 'nflTeams': sorted(nfl_teams), 'espnTeams': sorted(espn_teams)})
                chosen = None
        elif len(nfl_teams) > 1:
            corroborated = nfl_teams & espn_teams
            if len(corroborated) == 1:
                chosen = next(r for r in valid_nfl if r['teamCode'] in corroborated)
                method += ' + ESPN current roster corroboration'
            else:
                ambiguous.append({'id': key, 'name': entry['name'], 'teams': sorted(nfl_teams), 'reason': 'Multiple live NFL memberships without unique current ESPN corroboration'})
        elif len(espn_teams) == 1:
            chosen = espn_matches[0]; method = 'ESPN athlete ID + independently verified draft identity' if espn_id and status.get('identityVerified') else 'Exact normalized ESPN name + college'
        elif len(espn_teams) > 1:
            ambiguous.append({'id': key, 'name': entry['name'], 'teams': sorted(espn_teams), 'reason': 'Multiple ESPN memberships'})
        record = {'team': None, 'teamCode': None, 'rosterStatus': None, 'athleteId': str(espn_id) if espn_id else None,
                  'sourceUrl': None, 'matchMethod': method or 'No verified current roster membership',
                  'leagueStatus': 'unrostered/unknown', 'statusLabel': 'Status unconfirmed',
                  'statusSourceUrl': None, 'statusAsOf': asof}
        if chosen:
            record.update({field: chosen[field] for field in ['team', 'teamCode', 'rosterStatus', 'sourceUrl']})
            record.update(leagueStatus='rostered', statusLabel=chosen['rosterStatus'], statusSourceUrl=chosen['sourceUrl'])
            if chosen['source'] == 'espn': record['athleteId'] = str(chosen['athlete']['id'])
            if status.get('leagueStatus') in {'free-agent', 'retired', 'unsigned'}:
                status_conflicts.append({'id': key, 'name': entry['name'], 'rosterTeam': chosen['team'], 'athleteStatus': status['leagueStatus']})
        elif status.get('identityVerified'):
            record.update({field: status[field] for field in ['leagueStatus', 'statusLabel', 'statusSourceUrl', 'statusAsOf']})
        override = reviewed.get(key)
        if override:
            if name_key(override['name']) != name_key(entry['name']):
                raise ValueError(f'Reviewed status identity mismatch: {key}')
            if override['leagueStatus'] == 'deceased' and chosen:
                raise ValueError(f'Deceased primary report conflicts with current roster identity: {key}')
            # Current roster proof takes priority over an older retirement report
            # because players can return. Death reports can never be overridden.
            if not chosen:
                record.update(leagueStatus=override['leagueStatus'], statusLabel=override['statusLabel'],
                              statusSourceUrl=override['sourceUrl'], statusAsOf=asof,
                              statusSourcePublishedDate=override.get('sourcePublishedDate'),
                              matchMethod='Reviewed primary report + verified draft identity')
        record['nflPersonId'] = person_id or None
        players[key] = record
    coverage = {'draftSelections': len(entries), 'nflTeamsFetched': 32, 'espnTeamsFetched': 32, 'completeRosterFetch': True,
                'season': nfl['data']['rosters'][0]['season'], 'seasonType': nfl['data']['rosters'][0]['seasonType'],
                'teamMembers': sum(bool(r['team']) for r in players.values()),
                'nflFetchedAt': nfl['fetchedAt'],
                'espnRosterFetchedAtRange': [min(r['fetchedAt'] for r in espn), max(r['fetchedAt'] for r in espn)],
                'primaryStatusReports': len(reviewed),
                'leagueStatuses': dict(Counter(r['leagueStatus'] for r in players.values())),
                'nflRawStatusCounts': dict(raw_nfl_counts), 'espnRosterGroupCounts': dict(raw_espn_counts),
                'ambiguousMatches': ambiguous, 'sourceDisagreements': disagreements, 'athleteStatusConflicts': status_conflicts,
                'statusIdentityFailures': [{'id': k, 'reason': s.get('error') or 'Draft identity mismatch'} for k, s in statuses.items() if s and not s.get('identityVerified')],
                'scope': 'Current listed active, reserve, injured/out and practice-squad players. NFL released/terminated rows and historical athlete team references do not assign teams.',
                'limitations': ['Absence from complete current rosters does not prove retirement.',
                                'Inactive is an explicit ESPN provider status; it does not establish a retirement announcement.',
                                'Unconfirmed status and provider disagreements remain explicit rather than guessed.']}
    return {'schemaVersion': 1, 'asOf': asof, 'fetchedAt': now(),
            'sources': [{'label': f'NFL official {coverage["season"]} team roster data', 'url': 'https://www.nfl.com/teams/', 'extractionUrl': nfl['url']},
                        {'label': 'ESPN current team rosters', 'url': 'https://www.espn.com/nfl/teams', 'extractionUrl': ESPN_TEAMS_URL},
                        {'label': 'ESPN current NFL athlete status', 'url': 'https://www.espn.com/nfl/players', 'extractionUrl': ESPN_ATHLETE_BASE},
                        {'label': 'NFLverse draft identity crosswalk; historical team/status fields are not used for current membership', 'url': NFLVERSE_PLAYERS_URL}],
            'coverage': coverage, 'players': players}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reuse-cache', action='store_true')
    parser.add_argument('--refresh-statuses', action='store_true')
    args = parser.parse_args(); asof = now()[:10]
    today = dt.datetime.now(dt.timezone.utc); season = today.year if today.month >= 3 else today.year - 1
    entries = draft_entries(); nfl, espn = fetch_rosters(season, asof, args.reuse_cache)
    identities = nflverse_identities(entries, asof, args.reuse_cache)
    statuses = fetch_statuses(entries, identities, asof, args.reuse_cache, args.refresh_statuses)
    output = build_mapping(entries, identities, statuses, nfl, espn, asof)
    if len(output['players']) != len(entries): raise ValueError('Incomplete draft coverage; preserving the previous published snapshot')
    if output['coverage']['ambiguousMatches'] or output['coverage']['sourceDisagreements']:
        save_private(CACHE / 'mapping-review.json', output)
        raise ValueError('Unresolved roster identity/provider ambiguity; inspect private mapping-review.json before publishing')
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT.with_suffix('.tmp'); temporary.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')), encoding='utf-8'); temporary.replace(OUTPUT)
    print(json.dumps(output['coverage'], indent=2), flush=True)


if __name__ == '__main__': main()
