"""Collect cached, source-labelled draft measurements and short NFL scouting excerpts.

Raw NFL prose stays in the private source cache; publishable excerpts total <=24 words.
Anonymous authentication uses the reviewed public NFL WEB_DESKTOP client implementation
at CACHE/games.py. Tokens remain ephemeral in process memory.

Fresh checkout: pip install -r requirements.txt; python prepare-source-cache.py;
then python collect-workouts.py. All paths resolve from this file and the current
user's home directory, without a dependency on another user's source cache.
"""
from __future__ import annotations

import csv
import html
import importlib.util
import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests

PROJECT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles'
API = 'https://api.nfl.com/football/v2/combine/profiles'
REPO = 'https://github.com/array-carpenter/nfl-draft-data'
METRICS = {
    'height': ('height', 'in'), 'weight': ('weight', 'lb'),
    'handSize': ('hand_size', 'in'), 'armLength': ('arm_length', 'in'),
    'fortyYardDash': ('forty_yard_dash', 's'), 'tenYardSplit': ('ten_yard_split', 's'),
    'twentyYardSplit': ('twenty_yard_split', 's'), 'threeConeDrill': ('three_cone_drill', 's'),
    'twentyYardShuttle': ('twenty_yard_shuttle', 's'), 'sixtyYardShuttle': ('sixty_yard_shuttle', 's'),
    'verticalJump': ('vertical_jump', 'in'), 'broadJump': ('broad_jump', 'in'),
    'benchPress': ('bench_press', 'reps'), 'wingspan': ('wingspan', 'in'),
}
SUPPLEMENTAL = {
    'height': 'Height (in)', 'weight': 'Weight (lbs)', 'handSize': 'Hand Size (in)',
    'armLength': 'Arm Length (in)', 'fortyYardDash': '40 Yard',
    'tenYardSplit': '10-Yard Split', 'twentyYardSplit': '20-Yard Split',
    'threeConeDrill': '3Cone', 'twentyYardShuttle': 'Shuttle',
    'verticalJump': 'Vert Leap (in)', 'broadJump': 'Broad Jump (in)',
    'benchPress': 'Bench Press', 'wingspan': 'Wingspan (in)',
}
SIZE_METRICS = {'height', 'weight', 'handSize', 'armLength', 'wingspan'}
MEASUREMENT_BOUNDS = {
    'height': (50, 90), 'weight': (120, 420), 'handSize': (5, 16),
    'armLength': (20, 45), 'wingspan': (50, 100), 'fortyYardDash': (4, 6.5),
    'tenYardSplit': (1, 2.6), 'twentyYardSplit': (1.5, 4.5),
    'threeConeDrill': (5.5, 9.5), 'twentyYardShuttle': (3, 6.5),
    'sixtyYardShuttle': (9, 14.5), 'verticalJump': (10, 50),
    'broadJump': (65, 155), 'benchPress': (1, 60),
}
FITZ_DRAFT_URL = 'https://www.atlantafalcons.com/news/falcons-select-te-john-fitzpatrick-no-213-overall-in-2022-nfl-draft'
FITZ_SCOUT_URL = 'https://www.atlantafalcons.com/news/the-guy-does-the-dirty-work-falcons-decided-on-john-fitzpatrick-2022-nfl-draft'
ALIASES = {
    'mitchelltrubisky': 'mitchtrubisky', 'lanohill': 'delanohill',
    'joshallen': 'joshhinesallen', 'takkaristmckinley': 'takkmckinley',
    'gabejackson': 'gabrieljackson', 'gabedavis': 'gabrieldavis',
    'joshpalmer': 'joshuapalmer', 'joshdowns': 'joshuadowns',
    'joshkaindoh': 'joshuakaindoh', 'camward': 'cameronward',
    'camrobinson': 'cameronrobinson', 'mikewilliams': 'michaelwilliams',
    'mikehughes': 'michaelhughes', 'mikegesicki': 'michaelgesicki',
    'chigoziemokonkwo': 'chigokonkwo', 'chigokonkwo': 'chigokonkwo',
    'bennysnell': 'benjaminsnell', 'boogiebasham': 'carlosbasham',
    'buckyhodges': 'temuchinhodges', 'drewogletree': 'andrewogletree',
}
SCHOOLS = {
    'miamifl': 'miami', 'miamiflorida': 'miami', 'olemiss': 'mississippi',
    'lsu': 'louisianastate', 'usc': 'southerncalifornia',
    'uconn': 'connecticut', 'ucf': 'centralflorida', 'fiu': 'floridainternational',
    'byu': 'brighamyoung', 'utep': 'texaselpaso', 'texaselpaso': 'texaselpaso',
    'ncstate': 'northcarolinastate', 'pitt': 'pittsburgh', 'tcu': 'texaschristian',
    'utsa': 'texassanantonio', 'smu': 'southernmethodist',
    'louisianalafayette': 'louisiana', 'louisianamonroe': 'louisianamonroe',
    'cal': 'california', 'ohiost': 'ohiostate', 'pennst': 'pennstate',
}


def norm(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    return re.sub(r'[^a-z0-9]', '', ''.join(c for c in value.lower() if not unicodedata.combining(c)))


def name_key(value):
    value = re.sub(r'\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$', '', str(value or ''), flags=re.I)
    key = norm(value)
    return ALIASES.get(key, key)


def school_key(value):
    key = norm(value)
    return SCHOOLS.get(key, key)


def group(pos):
    pos = str(pos or '').upper()
    if pos in {'OG', 'G', 'OT', 'T', 'C', 'OL', 'IOL'}: return 'OL'
    if pos in {'S', 'SAF', 'SS', 'FS', 'CB', 'DB'}: return 'DB'
    if pos in {'LB', 'ILB', 'OLB', 'DE', 'EDGE', 'DT', 'DL', 'NT', 'ED'}: return 'FRONT7'
    if pos in {'RB', 'FB', 'HB'}: return 'BACK'
    return pos


def clean_text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))).strip()


def excerpt(value, budget=12):
    # One contiguous passage: never combine disconnected passages into a quote.
    text = clean_text(value)
    if not text or budget < 1: return None
    # Prefer a complete short scouting bullet or sentence over a clipped thought.
    bullets = [clean_text(v) for v in re.findall(r'<li\b[^>]*>(.*?)</li>', str(value or ''), re.I | re.S)]
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for passage in [*bullets, *sentences]:
        if passage and len(passage.split()) <= budget:
            return passage
    words = text.split()
    return ' '.join(words[:budget]) + ('…' if len(words) > budget else '')


def number(value):
    if value is None or str(value).strip() in {'', '--', 'NA', 'NaN', 'nan'}: return None
    try:
        n = float(value)
        if not (0 < n < 1000): return None
        return int(n) if n.is_integer() else n
    except (ValueError, TypeError): return None


def read_csv(filename):
    with (CACHE / 'raw' / filename).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def load_auth():
    if not (CACHE / 'games.py').exists():
        raise RuntimeError('Public NFL client is missing. Run python prepare-source-cache.py first.')
    spec = importlib.util.spec_from_file_location('public_nfl_auth', CACHE / 'games.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_year(year, auth, prospect=False):
    folder = CACHE / 'nfl-years'; folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{year}.json'
    stored = {}
    if path.exists():
        stored = json.loads(path.read_text(encoding='utf-8'))
        if stored.get('prospectsComplete' if prospect else 'complete'):
            return stored['prospectProfiles' if prospect else 'combineProfiles']
    endpoint = API.replace('/combine/', '/prospects/') if prospect else API
    records = []; token = None; seen = set()
    while True:
        params = {'year': year, 'limit': 1000}
        if token: params['pageToken'] = token
        for attempt in range(5):
            response = requests.get(endpoint, params=params, headers=auth.nfl_headers_gen(), timeout=45)
            if response.status_code == 401 and attempt == 0:
                auth.nfl_clear_token_cache(); continue
            if response.status_code in {429, 500, 502, 503, 504}:
                delay = response.headers.get('Retry-After', '')
                time.sleep(min(float(delay) if delay.isdigit() else 2 ** attempt, 30)); continue
            response.raise_for_status(); break
        else: raise RuntimeError(f'NFL API repeatedly failed for year {year}')
        data = response.json(); page = data.get('profiles' if prospect else 'combineProfiles')
        if not isinstance(page, list): raise ValueError(f'Invalid NFL response for year {year}')
        records.extend(page)
        token = data.get('pagination', {}).get('token')
        if not token or not page: break
        if token in seen: raise ValueError(f'NFL pagination repeated for year {year}')
        seen.add(token); time.sleep(.3)
    stored.update({'year': year, 'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    stored['prospectsSourceUrl' if prospect else 'sourceUrl'] = endpoint
    stored['prospectsComplete' if prospect else 'complete'] = True
    stored['prospectProfiles' if prospect else 'combineProfiles'] = records
    path.write_text(json.dumps(stored, ensure_ascii=False), encoding='utf-8')
    print(f'NFL {year} {"prospect" if prospect else "combine"}: {len(records)} profiles', flush=True)
    return records


def identity(record, kind):
    if kind == 'nfl':
        person = record['person']
        return [person.get('displayName'), ' '.join([person.get('firstName') or '', person.get('lastName') or ''])], person.get('collegeNames') or [], record.get('position')
    if kind == 'official':
        return [record.get('player'), ' '.join([record.get('first_name') or '', record.get('last_name') or ''])], [record.get('college')], record.get('position')
    return [record.get('player')], [record.get('College')], record.get('POS')


def make_index(records, kind):
    names = defaultdict(list); initials = defaultdict(list); ids = {}
    for record in records:
        variants, schools, pos = identity(record, kind)
        year = int(float(record.get('year') or record.get('Year')))
        for key in {name_key(v) for v in variants if v}:
            names[(year, key)].append(record)
        for v in variants:
            tokens = re.findall(r'[\w]+', re.sub(r'\s+(?:Jr\.?|Sr\.?|II|III|IV)$', '', str(v or ''), flags=re.I))
            if len(tokens) >= 2:
                initials[(year, norm(tokens[0])[0], norm(tokens[-1]))].append(record)
        personid = (record.get('person') or {}).get('id') or record.get('person_id')
        if personid: ids[(year, personid)] = record
    return names, initials, ids


def match(year, name, college, pos, idx, kind, known_id=None, overall=None):
    names, initials, ids = idx
    if known_id and (year, known_id) in ids: return ids[(year, known_id)], 'person-id'
    candidates = names.get((year, name_key(name)), [])
    if candidates:
        candidates = list({id(v): v for v in candidates}.values())
        by_pick = [v for v in candidates if overall is not None and v.get('draftOverallPick') == overall]
        if len(by_pick) == 1: return by_pick[0], 'normalized-name-official-pick'
        compatible = [v for v in candidates if group(identity(v, kind)[2]) == group(pos)]
        school_candidates = [v for v in candidates if school_key(college) in {school_key(s) for s in identity(v, kind)[1]}]
        # Draft roles can differ from college/combine roles (WR->TE, SAF->LB, CB/WR).
        # A unique exact name plus the same school safely corroborates those changes.
        if len(school_candidates) == 1: return school_candidates[0], 'normalized-name-college'
        if len(compatible) == 1: return compatible[0], 'normalized-name-position'
        if len(candidates) == 1 and not identity(candidates[0], kind)[2]: return candidates[0], 'normalized-name'
        return None, 'ambiguous-or-position-mismatch'
    tokens = re.findall(r'[\w]+', re.sub(r'\s+(?:Jr\.?|Sr\.?|II|III|IV)$', '', name, flags=re.I))
    if len(tokens) < 2: return None, 'not-matched'
    candidates = initials.get((year, norm(tokens[0])[0], norm(tokens[-1])), [])
    candidates = list({id(v): v for v in candidates}.values())
    compatible = [v for v in candidates if group(identity(v, kind)[2]) == group(pos)
                  and school_key(college) in {school_key(s) for s in identity(v, kind)[1]}]
    if len(compatible) == 1: return compatible[0], 'initial-lastname-college-position'
    return None, 'not-matched'


def source_url(nfl):
    person = nfl['person']; slug = re.sub(r'[^a-z0-9]+', '-', person['displayName'].lower()).strip('-')
    return f'https://www.nfl.com/prospects/{slug}/{person["id"]}'


def main():
    for filename in ['combine_official.csv', 'combine_pro_day.csv']:
        if not (CACHE / 'raw' / filename).exists():
            raise RuntimeError(f'Public input {filename} is missing. Run python prepare-source-cache.py first.')
    drafts = json.loads((PROJECT / 'drafts.json').read_text(encoding='utf-8'))
    auth = load_auth(); nfl_rows = []; combine_snapshots = {}; prospect_snapshots = {}
    for year in sorted(map(int, drafts)):
        combined = fetch_year(year, auth)
        prospects = fetch_year(year, auth, prospect=True)
        for row in combined: combine_snapshots[(year, row['person']['id'])] = row
        for row in prospects: prospect_snapshots[(year, row['person']['id'])] = row
        merged = {r['person']['id']: dict(r) for r in combined}
        for record in prospects:
            personid = record['person']['id']
            if personid not in merged: merged[personid] = dict(record)
            else: merged[personid].update({k: v for k, v in record.items() if v is not None and v != ''})
            if merged[personid].get('detailAuthor'):
                merged[personid]['profileAuthor'] = merged[personid]['detailAuthor']
        nfl_rows.extend(merged.values())
        yearpath = CACHE / 'nfl-years' / f'{year}.json'
        rawyear = json.loads(yearpath.read_text(encoding='utf-8'))
        rawyear['mergedProfiles'] = list(merged.values())
        yearpath.write_text(json.dumps(rawyear, ensure_ascii=False), encoding='utf-8')
    official_rows = read_csv('combine_official.csv')
    supplemental_rows = read_csv('combine_pro_day.csv')
    indexes = {kind: make_index(rows, kind) for kind, rows in [('nfl', nfl_rows), ('official', official_rows), ('supplemental', supplemental_rows)]}
    profiles = {}; counts = Counter(); byyear = defaultdict(Counter); unmatched = []; invalid = []
    for yearstr, picks in drafts.items():
        year = int(yearstr)
        for pick in picks:
            rnd, overall, team, via, name, pos, college = pick[:7]
            profile_id = f'{year}-{overall}'
            official, official_method = match(year, name, college, pos, indexes['official'], 'official')
            known_id = official.get('person_id') if official else None
            nfl, nfl_method = match(year, name, college, pos, indexes['nfl'], 'nfl', known_id, overall)
            supplemental, supplemental_method = match(year, name, college, pos, indexes['supplemental'], 'supplemental')
            sources = []; measurements = defaultdict(list); rejected = []
            def add(metric, value, sourceid, event, designation='not-reported'):
                raw_value = value
                if isinstance(value, dict):
                    designation = value.get('designation') or 'not-reported'
                    value = value.get('seconds', value.get('inches', value.get('repetitions')))
                value = number(value)
                if value is not None:
                    lower, upper = MEASUREMENT_BOUNDS[metric]
                    if not lower <= value <= upper:
                        rejection = {'metric': metric, 'rawValue': raw_value, 'unit': METRICS[metric][1],
                                     'event': event, 'designation': designation, 'sourceId': sourceid,
                                     'reason': f'Outside validation bounds {lower}–{upper} {METRICS[metric][1]}; no unit or drill conversion inferred.'}
                        rejected.append(rejection)
                        invalid.append({'profileId': profile_id, 'name': name, **rejection})
                        return
                    measurements[metric].append({'value': value, 'unit': METRICS[metric][1],
                                                 'event': event, 'designation': designation, 'sourceId': sourceid})
            nfl_url = source_url(nfl) if nfl else None
            raw_combine = combine_snapshots.get((year, nfl['person']['id'])) if nfl else None
            raw_prospect = prospect_snapshots.get((year, nfl['person']['id'])) if nfl else None
            event = ('Pro day / workout (2021)' if year == 2021 else
                     'NFL Scouting Combine' if raw_combine and raw_combine.get('combineAttendance') is True else
                     'NFL prospect measurements (event unspecified)')
            if nfl:
                sources.append({'id': 'nfl', 'label': 'NFL official prospect profile', 'url': nfl_url})
                if raw_combine:
                    for metric in METRICS:
                        # Attendance cannot prove the event of a later-updated size value.
                        measurement_event = 'NFL prospect size (event unspecified)' if metric in SIZE_METRICS and year != 2021 else event
                        add(metric, raw_combine.get(metric), 'nfl', measurement_event)
                    if raw_combine.get('proFortyYardDash'):
                        add('fortyYardDash', raw_combine['proFortyYardDash'], 'nfl', 'Pro day')
                if raw_prospect:
                    differences = [metric for metric in METRICS if raw_prospect.get(metric) is not None
                                   and (not raw_combine or raw_prospect.get(metric) != raw_combine.get(metric))]
                    if differences or raw_prospect.get('proFortyYardDash') != (raw_combine or {}).get('proFortyYardDash'):
                        sources.append({'id': 'nfl-prospect', 'label': 'NFL updated prospect measurements; event unspecified', 'url': nfl_url})
                        for metric in differences: add(metric, raw_prospect.get(metric), 'nfl-prospect', 'NFL prospect measurements (event unspecified)')
                        if raw_prospect.get('proFortyYardDash') and raw_prospect.get('proFortyYardDash') != (raw_combine or {}).get('proFortyYardDash'):
                            add('fortyYardDash', raw_prospect['proFortyYardDash'], 'nfl-prospect', 'Pro day')
            if official:
                sources.append({'id': 'official-csv', 'label': 'Public NFL API measurement dataset; size event unspecified', 'url': REPO + '/blob/master/data/combine_official.csv'})
                for metric, (field, unit) in METRICS.items():
                    csv_event = 'NFL API measurements (event unspecified)'
                    original = (raw_combine or {}).get(metric)
                    if year == 2021:
                        csv_event = 'Pro day / workout (2021)'
                    elif metric in SIZE_METRICS:
                        csv_event = 'NFL prospect size (event unspecified)'
                    elif isinstance(original, dict):
                        original_value = original.get('seconds', original.get('inches', original.get('repetitions')))
                        if number(official.get(field)) == number(original_value):
                            csv_event = event
                    add(metric, official.get(field), 'official-csv', csv_event)
                # Dataset values stay separate from current API values; no event is inferred.
                for metric in SIZE_METRICS:
                    if metric in measurements: measurements[metric].sort(key=lambda value: 0 if value['sourceId'] == 'official-csv' else 1)
            if supplemental:
                sources.append({'id': 'supplemental', 'label': 'Combined combine / pro-day dataset; event unspecified', 'url': REPO + '/blob/master/data/combine_pro_day.csv'})
                for metric, field in SUPPLEMENTAL.items(): add(metric, supplemental.get(field), 'supplemental', 'Combine / pro day (event unspecified)')
            strength = excerpt(nfl.get('strengths')) if nfl else None
            weakness = excerpt(nfl.get('weaknesses')) if nfl else None
            quote_words = len((strength or '').split()) + len((weakness or '').split())
            overview = excerpt(nfl.get('overview'), 24 - quote_words) if nfl and quote_words < 24 else None
            narrative = bool(nfl and any(nfl.get(field) for field in ['overview', 'strengths', 'weaknesses']))
            rawref = f'{CACHE.as_posix()}/nfl-years/{year}.json#person.id={nfl["person"]["id"]}' if nfl else None
            scouting = {'status': 'available' if narrative else 'not-reported',
                        'author': nfl.get('profileAuthor') if nfl else None,
                        'grade': nfl.get('grade') if nfl else official.get('grade') if official else None,
                        'projection': nfl.get('draftProjection') if nfl else official.get('draft_projection') if official else None,
                        'comparison': nfl.get('nflComparison') if nfl else official.get('nfl_comparison') if official else None,
                        'strengthQuote': strength, 'weaknessQuote': weakness,
                        'overviewQuote': overview,
                        'quoteWordCount': quote_words + len((overview or '').split()),
                        'sourceUrl': nfl_url, 'rawReference': rawref,
                        'sourceAvailable': {f: bool(nfl and nfl.get(f)) for f in ['overview', 'strengths', 'weaknesses']}}
            if profile_id == '2022-213':
                # Vetted primary team reports, April 30 and June 28, 2022.
                sources.extend([{'id': 'falcons-draft', 'label': 'Falcons 2022 draft-day player profile', 'url': FITZ_DRAFT_URL},
                                {'id': 'falcons-scout', 'label': 'Falcons area-scout evaluation, June 2022', 'url': FITZ_SCOUT_URL}])
                add('height', 79, 'falcons-draft', 'Draft-day listed size (2022)')
                add('weight', 262, 'falcons-draft', 'Draft-day profile size card (2022)')
                # The article body and later scout story list 250; preserve the discrepancy.
                add('weight', 250, 'falcons-scout', 'June 2022 team article listed size')
                scouting.update({'status': 'available', 'author': 'Shepley Heard, Falcons area scout; Tori McElhaney, team reporter',
                                 'strengthQuote': "He's big, physical, tough, nasty, always trying to finish guys.",
                                 'weaknessQuote': "He's not going to dazzle in the pass game",
                                 'overviewQuote': None, 'sourceUrl': FITZ_SCOUT_URL,
                                 'sourceAvailable': {'overview': True, 'strengths': True, 'weaknesses': True},
                                 'sourceType': 'NFL team scouting article',
                                 'strengthAttribution': 'Shepley Heard, Falcons area scout',
                                 'weaknessAttribution': 'Tori McElhaney, team reporter'})
                scouting['quoteWordCount'] = len(scouting['strengthQuote'].split()) + len(scouting['weaknessQuote'].split())
                narrative = True
            assert scouting['quoteWordCount'] <= 24
            for field in ['grade']:
                if scouting[field] in {'', None}: scouting[field] = None
                else:
                    try: scouting[field] = float(scouting[field])
                    except (ValueError, TypeError): scouting[field] = None
            profile = {'id': profile_id, 'year': year, 'pick': overall, 'name': name,
                       'position': pos, 'college': college, 'nflPersonId': nfl['person']['id'] if nfl else known_id,
                       'sources': sources, 'measurements': dict(measurements),
                       'rejectedMeasurements': rejected,
                       'missingMeasurements': [m for m in METRICS if m not in measurements],
                       'scouting': scouting,
                       'bio': {'status': 'available' if nfl and nfl.get('bio') else 'not-reported', 'rawReference': rawref, 'sourceUrl': nfl_url},
                       'availability': {'nflProfile': bool(nfl), 'measurementCount': len(measurements), 'scouting': narrative, 'bio': bool(nfl and nfl.get('bio'))},
                       'identityMatches': {'nfl': nfl_method, 'official': official_method, 'supplemental': supplemental_method}}
            profiles[profile_id] = profile
            for flag in ['nflProfile', 'scouting', 'bio']:
                if profile['availability'][flag]: counts[flag] += 1; byyear[yearstr][flag] += 1
            if measurements: counts['withMeasurements'] += 1; byyear[yearstr]['withMeasurements'] += 1
            for metric in measurements: counts[f'metric:{metric}'] += 1
            if not nfl: unmatched.append({'id': profile_id, 'name': name, 'college': college, 'position': pos, 'method': nfl_method})
            counts['profiles'] += 1; byyear[yearstr]['profiles'] += 1
    assert len(profiles) == sum(map(len, drafts.values()))
    coverage = {'counts': dict(counts), 'years': dict(byyear), 'unmatchedNFL': unmatched,
                'invalidObservations': invalid, 'measurementValidationBounds': MEASUREMENT_BOUNDS,
                'copyright': 'NFL text restricted to two contiguous excerpts totaling at most 24 words per player; full text stays in raw source cache.',
                'notes': ['Measurements are independent source observations. Conflicting numbers are retained.',
                          'Supplemental combined values have no verified event or timing designation.',
                          '2021 records are labelled pro day / workout, not Scouting Combine.',
                          'No unpublished private workout results are inferred.']}
    (CACHE / 'workout-profiles.json').write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
    (CACHE / 'workout-coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(coverage['counts'], indent=2), flush=True)
    print(f'Unmatched NFL profiles: {len(unmatched)}', flush=True)


if __name__ == '__main__': main()
