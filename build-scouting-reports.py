"""Build a draft-day report and a current report for every drafted player.

Run after build-career-arcs.py:  python build-scouting-reports.py   (then python build-site.py)

Both reports are assembled from data this archive already holds; they are not scout film grades.
  Draft-day report: NFL.com prospect grade ranked within the draft class and position, pick vs grade
    rank, projection and comparison, athletic-testing percentiles, college production ranked within
    the class at the position, and the short attributed strength/concern excerpts with a link to the
    full published report (full report prose is not republished).
  Current report: league status, role and availability, Approximate Value trend, latest completed
    season ranked against every drafted player-season at the position (2017-2025), comparison with
    the typical player in the same career year, current-season line, and links to ESPN news and PFR.
Writes profile['scoutingReports'] into local/data/profiles/<id>.json.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from career_metrics import GROUPS, IN_PROGRESS_SEASON, LAST_COMPLETED_SEASON, METRICS, groups_for_position, metric_value

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'local' / 'data'
MEASURES = {'height': 'Height', 'weight': 'Weight', 'handSize': 'Hand size', 'armLength': 'Arm length', 'wingspan': 'Wingspan',
            'fortyYardDash': '40-yard dash', 'tenYardSplit': '10-yard split', 'twentyYardSplit': '20-yard split',
            'threeConeDrill': 'Three-cone', 'twentyYardShuttle': '20-yard shuttle', 'sixtyYardShuttle': '60-yard shuttle',
            'verticalJump': 'Vertical jump', 'broadJump': 'Broad jump', 'benchPress': 'Bench press'}
UNITS = {'height': 'in', 'weight': 'lb', 'handSize': 'in', 'armLength': 'in', 'wingspan': 'in', 'fortyYardDash': 's',
         'tenYardSplit': 's', 'twentyYardSplit': 's', 'threeConeDrill': 's', 'twentyYardShuttle': 's', 'sixtyYardShuttle': 's',
         'verticalJump': 'in', 'broadJump': 'in', 'benchPress': 'reps'}
ATHLETIC = {
    'QB': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'verticalJump', 'broadJump', 'handSize', 'height'],
    'RB': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'verticalJump', 'broadJump', 'benchPress', 'weight'],
    'FB': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'benchPress', 'weight'],
    'WR': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'verticalJump', 'broadJump', 'height', 'handSize'],
    'TE': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'verticalJump', 'broadJump', 'armLength', 'weight'],
    'OT': ['armLength', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'broadJump', 'benchPress', 'weight', 'handSize'],
    'OG': ['armLength', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'broadJump', 'benchPress', 'weight', 'handSize'],
    'C': ['armLength', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'broadJump', 'benchPress', 'weight', 'handSize'],
    'DE': ['armLength', 'fortyYardDash', 'tenYardSplit', 'threeConeDrill', 'twentyYardShuttle', 'verticalJump', 'broadJump', 'weight'],
    'OLB': ['armLength', 'fortyYardDash', 'tenYardSplit', 'threeConeDrill', 'verticalJump', 'broadJump', 'weight'],
    'DT': ['armLength', 'tenYardSplit', 'fortyYardDash', 'twentyYardShuttle', 'threeConeDrill', 'benchPress', 'broadJump', 'weight'],
    'NT': ['armLength', 'tenYardSplit', 'benchPress', 'weight'],
    'LB': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'verticalJump', 'broadJump', 'weight'],
    'CB': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'verticalJump', 'broadJump', 'armLength', 'height'],
    'S': ['fortyYardDash', 'tenYardSplit', 'twentyYardShuttle', 'threeConeDrill', 'verticalJump', 'broadJump', 'weight'],
}
ATHLETIC['FS'] = ATHLETIC['S']
ATHLETIC['CB / WR'] = ATHLETIC['CB']
# Primary college production stat per draft position: (category, key, label, lower_is_better)
PRODUCTION = {
    'QB': [('passing', 'passingYards', 'passing yards'), ('passing', 'passingTouchdowns', 'passing TD')],
    'RB': [('rushing', 'rushingYards', 'rushing yards'), ('receiving', 'receivingYards', 'receiving yards')],
    'FB': [('rushing', 'rushingYards', 'rushing yards')],
    'WR': [('receiving', 'receivingYards', 'receiving yards'), ('receiving', 'receivingTouchdowns', 'receiving TD')],
    'CB / WR': [('receiving', 'receivingYards', 'receiving yards'), ('defensive', 'passesDefended', 'passes defended')],
    'TE': [('receiving', 'receivingYards', 'receiving yards'), ('receiving', 'receivingTouchdowns', 'receiving TD')],
    'DE': [('defensive', 'sacks', 'sacks'), ('defensive', 'tacklesForLoss', 'tackles for loss')],
    'OLB': [('defensive', 'sacks', 'sacks'), ('defensive', 'tacklesForLoss', 'tackles for loss')],
    'DT': [('defensive', 'sacks', 'sacks'), ('defensive', 'tacklesForLoss', 'tackles for loss')],
    'NT': [('defensive', 'totalTackles', 'tackles')],
    'LB': [('defensive', 'totalTackles', 'tackles'), ('defensive', 'sacks', 'sacks')],
    'CB': [('defensive', 'passesDefended', 'passes defended'), ('defensive', 'interceptions', 'interceptions')],
    'S': [('defensive', 'totalTackles', 'tackles'), ('defensive', 'interceptions', 'interceptions')],
    'FS': [('defensive', 'totalTackles', 'tackles'), ('defensive', 'interceptions', 'interceptions')],
    'K': [('kicking', 'fieldGoalsMade', 'field goals made')],
    'P': [('punting', 'grossAvgPuntYards', 'gross punting average')],
}
# Current-report candidate metrics per career group
CURRENT = {
    'QB': ['av', 'pass_yds', 'pass_td', 'anya', 'epa_db', 'cmp_pct', 'int', 'sacks_taken', 'rush_yds'],
    'RB': ['av', 'scrim_yds', 'ypc', 'carry_share', 'rec', 'yac_att', 'brk_tkl', 'total_td', 'fum_lost'],
    'FB': ['av', 'snap_share', 'rec', 'carries'],
    'WR': ['av', 'rec_yds', 'target_share', 'catch_pct', 'ypt', 'yac_rec', 'rec_td', 'drop_pct'],
    'TE': ['av', 'rec_yds', 'target_share', 'catch_pct', 'ypt', 'rec_td', 'drop_pct', 'snap_share'],
    'T': ['av', 'gs', 'snap_share', 'holds', 'false_starts'], 'G': ['av', 'gs', 'snap_share', 'holds', 'false_starts'],
    'C': ['av', 'gs', 'snap_share', 'holds', 'false_starts'],
    'DE': ['av', 'sacks', 'pressures', 'tfl', 'qb_hits', 'snap_share', 'missed_tkl_pct'],
    'DT': ['av', 'sacks', 'pressures', 'tfl', 'qb_hits', 'snap_share', 'missed_tkl_pct'],
    'LB': ['av', 'tackles', 'tfl', 'sacks', 'pd', 'missed_tkl_pct', 'rating_allowed'],
    'CB': ['av', 'pd', 'def_int', 'snap_share', 'cmp_allowed_pct', 'rating_allowed', 'missed_tkl_pct'],
    'S': ['av', 'tackles', 'pd', 'def_int', 'snap_share', 'rating_allowed', 'missed_tkl_pct'],
    'K': ['av', 'fg_pct', 'fg50', 'xp_pct'], 'P': ['av', 'net_avg', 'punt_avg', 'in20_pct'], 'LS': ['g'],
}
SINGULAR = {'QB': 'quarterback', 'RB': 'running back', 'FB': 'fullback', 'WR': 'wide receiver', 'TE': 'tight end',
            'T': 'tackle', 'G': 'guard', 'C': 'center', 'DE': 'edge rusher', 'DT': 'interior lineman', 'LB': 'off-ball linebacker',
            'CB': 'cornerback', 'S': 'safety', 'K': 'kicker', 'P': 'punter', 'LS': 'long snapper'}
STARTER_ONLY = {'holds', 'false_starts', 'penalties'}  # compared only among 50%+ snap-share seasons


def ordinal(n):
    n = int(round(n))
    return f'{n}{"th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")}'


def num(text):
    try:
        return float(str(text).replace(',', ''))
    except (TypeError, ValueError):
        return None


def percentile(value, values, lower=False):
    if value is None or not values:
        return None
    below = sum(1 for v in values if v < value)
    ties = sum(1 for v in values if v == value)
    above = len(values) - below - ties
    p = 100 * ((above if lower else below) + ties * .5) / len(values)
    return round(p, 1)


def fmt(key, value):
    spec = METRICS[key]
    if value is None:
        return ''
    if spec[2] == 'pct':
        return f'{value * 100:.1f}%'
    if spec[2] == 'dec1':
        return f'{value:.1f}'
    if spec[2] == 'dec2':
        return f'{value:.2f}'
    return f'{round(value):,}'


def preferred(readings):
    combine = [r for r in readings if r.get('event') == 'NFL Scouting Combine']
    official = [r for r in combine if str(r.get('designation', '')).lower() == 'official']
    return (official or combine or readings or [None])[0]


def draft_report(record, profile, class_records, grades, benchmarks, productions):
    sc = profile['workouts'].get('scouting') or {}
    out = {'author': sc.get('author'), 'sourceUrl': sc.get('sourceUrl'), 'grade': sc.get('grade'),
           'projection': sc.get('projection'), 'comparison': sc.get('comparison'),
           'strengthQuote': sc.get('strengthQuote'), 'weaknessQuote': sc.get('weaknessQuote'), 'overviewQuote': sc.get('overviewQuote')}
    year, pos = record['year'], record['position']
    if sc.get('grade') is not None:
        class_grades = sorted((g for g in grades[year].values() if g is not None), reverse=True)
        pos_grades = sorted((grades[year][r['id']] for r in class_records if r['position'] == pos and grades[year].get(r['id']) is not None), reverse=True)
        out['gradeRankClass'] = 1 + sum(1 for g in class_grades if g > sc['grade'])
        out['classGraded'] = len(class_grades)
        out['gradeRankPosition'] = 1 + sum(1 for g in pos_grades if g > sc['grade'])
        out['positionGraded'] = len(pos_grades)
        out['pickVsGrade'] = out['gradeRankClass'] - record['pick']  # positive: picked earlier than his grade rank
    # Athletic profile
    measurements = profile['workouts'].get('measurements') or {}
    alias = benchmarks['positionAliases'].get(pos, pos)
    bench = benchmarks['positions'].get(alias, {})
    tests = []
    definitions = json.loads((ROOT / 'measurement-definitions.json').read_text(encoding='utf-8'))
    definitions = definitions.get('metrics', definitions)
    for key in ATHLETIC.get(pos, []):
        reading = preferred([r for r in measurements.get(key, []) if r.get('value') not in (None, '', 'N/A')])
        stats = bench.get(key)
        if not reading or not stats or not stats.get('rankable', True) or stats.get('n', 0) < benchmarks.get('minimumRankSample', 20):
            continue
        value = num(reading['value'])
        direction = definitions.get(key, {}).get('direction', 'size')
        pct = percentile(value, stats.get('values', []), lower=direction == 'lower')
        if pct is None:
            continue
        official = reading.get('event') == 'NFL Scouting Combine' and str(reading.get('designation', '')).lower() == 'official'
        tests.append({'key': key, 'label': MEASURES[key], 'value': value, 'unit': UNITS[key], 'percentile': pct,
                      'kind': direction, 'event': reading.get('event'),
                      'crossEvent': bool(stats.get('officialCombineOnly')) and not official})
    out['athletic'] = tests
    # College production ranked within the class at the draft position
    prod = []
    for category, key, label in PRODUCTION.get(pos, []):
        mine = productions.get(record['id'], {}).get((category, key))
        if not mine:
            continue
        peers = [productions.get(r['id'], {}).get((category, key)) for r in class_records if r['position'] == pos]
        finals = [p['final'] for p in peers if p and p['final'] is not None]
        careers = [p['career'] for p in peers if p and p['career'] is not None]
        entry = {'label': label, 'final': mine['final'], 'finalYear': mine['finalYear'], 'career': mine['career'], 'peers': len(peers)}
        if mine['final'] is not None:
            entry['finalRank'] = 1 + sum(1 for v in finals if v > mine['final'])
            entry['finalOf'] = len(finals)
        if mine['career'] is not None:
            entry['careerRank'] = 1 + sum(1 for v in careers if v > mine['career'])
            entry['careerOf'] = len(careers)
        prod.append(entry)
    out['production'] = prod
    out['summary'] = draft_summary(record, out)
    return out


def draft_summary(record, d):
    pos = {'OT': 'tackle', 'OG': 'guard', 'C': 'center', 'CB / WR': 'two-way CB/WR'}.get(record['position'], record['position'])
    parts = []
    if d.get('grade') is not None:
        parts.append(f"NFL.com graded him {d['grade']:.2f}, the {ordinal(d['gradeRankClass'])}-best grade among {d['classGraded']} "
                     f"{record['year']} draftees and {ordinal(d['gradeRankPosition'])} of {d['positionGraded']} at {pos}.")
        delta = d['pickVsGrade']
        if delta >= 25:
            parts.append(f"He went {ordinal(record['pick'])} overall, well ahead of where his grade ranked ({ordinal(d['gradeRankClass'])}): teams liked him more than the published grade.")
        elif delta <= -25:
            parts.append(f"He lasted until pick {record['pick']}, well after his grade rank ({ordinal(d['gradeRankClass'])}): he slid relative to the published grade.")
        else:
            parts.append(f"He went {ordinal(record['pick'])} overall, close to where his grade ranked.")
    else:
        parts.append('No published NFL.com prospect grade was collected for him.')
    if d.get('comparison'):
        parts.append(f"Published comparison: {d['comparison']}.")
    strong = [t for t in d['athletic'] if t['kind'] != 'size' and t['percentile'] >= 80]
    weak = [t for t in d['athletic'] if t['kind'] != 'size' and t['percentile'] <= 20]
    if strong:
        parts.append('Testing standouts: ' + ', '.join(f"{t['label'].lower()} ({ordinal(t['percentile'])} percentile)" for t in strong[:3]) + '.')
    if weak:
        parts.append('Testing concerns: ' + ', '.join(f"{t['label'].lower()} ({ordinal(t['percentile'])} percentile)" for t in weak[:2]) + '.')
    if d['athletic'] and not strong and not weak:
        parts.append('Testing was middle of the pack for his position, with no result in the top or bottom 20%.')
    if not d['athletic']:
        parts.append('No rankable athletic testing on record.')
    lead = next((p for p in d['production'] if p.get('finalRank')), None)
    if lead:
        rank = lead['finalRank']
        if rank <= 3 and lead['finalOf'] >= 5:
            parts.append(f"College production: his final season ({lead['finalYear']}) ranked {ordinal(rank)} in {lead['label']} among the {lead['finalOf']} {pos}s in his class with stats.")
        else:
            parts.append(f"College production: {lead['final']:,.0f} {lead['label']} in {lead['finalYear']}, {ordinal(rank)} of {lead['finalOf']} {pos}s in his class with stats.")
    return ' '.join(parts)


def college_productions(profiles):
    out = {}
    for pid, profile in profiles.items():
        entries = {}
        year = int(pid.split('-')[0])
        for category in (profile.get('collegeStats') or {}).get('categories', []):
            seasons = [s for s in category.get('seasons', []) if isinstance(s.get('year'), int) and s['year'] < year]
            for column in category.get('columns', []):
                key = column['key'] if isinstance(column, dict) else column
                values = [(s['year'], num(s.get('values', {}).get(key))) for s in seasons]
                values = [(y, v) for y, v in values if v is not None]
                career = num((category.get('career') or {}).get('values', {}).get(key))
                if values or career is not None:
                    final_year, final = max(values) if values else (None, None)
                    entries[(category['key'], key)] = {'final': final, 'finalYear': final_year, 'career': career}
        out[pid] = entries
    return out


def reference_values(group_data):
    """All completed player-seasons for the group: count metrics need 8+ games, rates need their qualifier."""
    cols = group_data['gridColumns']
    refs = defaultdict(list)
    for player in group_data['players']:
        for row in player['s']:
            season = dict(zip(cols, row))
            if season['inProgress'] or not season['g']:
                continue
            for metric in group_data['metrics']:
                value = season.get(metric)
                if value is None:
                    continue
                if METRICS[metric][3] == 'count' and season['g'] < 8:
                    continue
                if metric in STARTER_ONLY and (season.get('snap_share') or 0) < .5:
                    continue
                refs[metric].append(value)
    return refs


def current_report(record, career_seasons, current_team, group, group_data, refs, live):
    spec = GROUPS[group]
    side = spec['side']
    seasons = career_seasons
    played = [s for s in seasons if s['g'] > 0]
    out = {'group': group, 'groupLabel': spec['label'], 'asOf': live['asOf'], 'season': IN_PROGRESS_SEASON, 'throughWeek': live['throughWeek'],
           'status': current_team.get('team') or current_team.get('statusLabel') or 'Status unconfirmed',
           'onRoster': bool(current_team.get('team')), 'rosterStatus': current_team.get('rosterStatus'),
           'statusSourceUrl': current_team.get('statusSourceUrl') or current_team.get('sourceUrl')}
    if current_team.get('athleteId'):
        out['espnUrl'] = f"https://www.espn.com/nfl/player/_/id/{current_team['athleteId']}"
    out['av'] = [{'season': s['season'], 'cy': s['cy'], 'av': s.get('av'), 'g': s['g'], 'gs': s.get('gs'),
                  'pb': bool(s.get('pro_bowl')), 'ap': bool(s.get('all_pro'))} for s in seasons]
    completed = [s for s in played if s['season'] <= LAST_COMPLETED_SEASON]
    if not played:
        where = ('On the ' + out['status'] + ' roster' + (f" ({out['rosterStatus'].lower()})" if out.get('rosterStatus') else '')) \
            if out['onRoster'] else ('Current team or status not confirmed in the latest roster check' if out['status'] == 'Status unconfirmed' else 'Current status: ' + out['status'].lower())
        out['summary'] = f"Has not appeared in a regular-season NFL game through {IN_PROGRESS_SEASON} Week {live['throughWeek']}. {where}."
        out['state'] = 'not-played'
        return out
    flat = {s['season']: flatten_side(s, side) for s in seasons}
    latest = completed[-1] if completed else None
    live_season = next((s for s in seasons if s.get('inProgress')), None)
    if live_season and live_season['g'] > 0:
        ls = flat[live_season['season']]
        out['thisSeason'] = {'g': ls['g'], 'gs': ls.get('gs'), 'snapShare': ls.get('snap_share'),
                             'line': [{'key': k, 'label': METRICS[k][1], 'value': ls.get(k), 'text': fmt(k, metric_value(k, ls, 'played'))}
                                      for k in CURRENT[group] if k != 'av' and metric_value(k, ls, 'played') not in (None, 0)][:5]}
    avs = [(s.get('av'), s['season']) for s in completed if s.get('av') is not None]
    if avs:
        peak, peak_season = max(avs, key=lambda x: (x[0], -x[1]))
        out['peakAv'] = {'av': peak, 'season': peak_season}
    if latest:
        f = flat[latest['season']]
        out['latest'] = {'season': latest['season'], 'cy': latest['cy'], 'g': latest['g'], 'gs': latest.get('gs'), 'av': latest.get('av')}
        ranks = []
        for metric in CURRENT[group]:
            if metric not in group_data['metrics']:
                continue
            value = metric_value(metric, f, 'played')
            if value is None or (METRICS[metric][3] == 'count' and latest['g'] < 8 and metric not in ('av',)):
                continue
            if metric in STARTER_ONLY and (f.get('snap_share') or 0) < .5:
                continue
            pct = percentile(value, refs.get(metric, []), lower=metric in {'int', 'sacks_taken', 'fum_lost', 'drop_pct', 'holds', 'false_starts', 'missed_tkl_pct', 'cmp_allowed_pct', 'rating_allowed'})
            if pct is None:
                continue
            ranks.append({'key': metric, 'label': METRICS[metric][0], 'value': value, 'text': fmt(metric, value), 'percentile': pct})
        out['ranks'] = ranks
        out['strengths'] = sorted([r for r in ranks if r['percentile'] >= 75], key=lambda r: -r['percentile'])[:4]
        out['concerns'] = sorted([r for r in ranks if r['percentile'] <= 25], key=lambda r: r['percentile'])[:3]
        # Typical player in the same career year (players who played), position default metric
        main = group_data['default']
        cy_stats = group_data['buckets']['all']['stats'].get(main, {})
        basis = cy_stats.get('played') or cy_stats.get('all') or []
        year_row = next((y for y in basis if y['cy'] == latest['cy']), None)
        mine = metric_value(main, f, 'played')
        if year_row and year_row.get('median') is not None and mine is not None and year_row.get('n', 0) >= 10:
            out['careerYear'] = {'metric': main, 'label': METRICS[main][0], 'cy': latest['cy'], 'value': mine, 'text': fmt(main, mine),
                                 'median': year_row['median'], 'medianText': fmt(main, year_row['median']), 'n': year_row['n']}
    # Availability concern: missed time in the latest completed season
    if latest and latest['g'] < 12 and latest['season'] >= 2021:
        out['availability'] = f"Played {latest['g']} of 17 games in {latest['season']}."
    out['state'] = state(out, played)
    out['summary'] = current_summary(record, out, played, completed)
    return out


def flatten_side(season, side):
    s = {k: v for k, v in season.items() if k != 'usage'}
    usage = (season.get('usage') or {}).get(side) or {}
    s['snap_share'] = usage.get('share', 0)
    s['snap50'] = usage.get('g50', 0)
    s['side_snaps'] = usage.get('snaps', 0)
    if usage.get('active') is not None and usage.get('games'):
        s['snap_active'] = usage['active']
    return s


def state(out, played):
    last = played[-1]['season']
    if not out['onRoster'] and last < LAST_COMPLETED_SEASON:
        return 'out'
    peak = out.get('peakAv')
    latest = out.get('latest')
    if not peak or not latest or latest.get('av') is None:
        return 'early'
    if latest['cy'] <= 2 and peak['av'] < 8:
        return 'developing'
    if latest['av'] >= peak['av'] and latest['season'] == peak['season']:
        return 'rising'
    if latest['av'] >= .75 * peak['av']:
        return 'near-peak'
    return 'below-peak'


def current_summary(record, out, played, completed):
    parts = []
    group = out['groupLabel'].lower()
    seasons_played = len([s for s in completed])
    games = sum(s['g'] for s in completed)
    starts = sum(s.get('gs') or 0 for s in completed)
    status = out['status']
    if out['onRoster']:
        parts.append(f"Year {IN_PROGRESS_SEASON - record['year'] + 1} pro, currently with the {status}" +
                     (f" ({out['rosterStatus'].lower()})" if out.get('rosterStatus') and out['rosterStatus'].lower() not in ('active',) else '') + '.')
    else:
        parts.append(f"Current status: {status.lower()}. Last NFL action came in {played[-1]['season']}.")
    parts.append(f"{games} career games and {starts} starts over {seasons_played} completed {'season' if seasons_played == 1 else 'seasons'}" +
                 (f", plus {out['thisSeason']['g']} so far in {out['season']}" if out.get('thisSeason') else '') + '.')
    peak = out.get('peakAv')
    latest = out.get('latest')
    s = out['state']
    if peak and latest and latest.get('av') is not None:
        trend = {'rising': f"His {latest['season']} season ({latest['av']} AV) was his best yet.",
                 'near-peak': f"Producing near his peak: {latest['av']} AV in {latest['season']} against a career-best {peak['av']} in {peak['season']}.",
                 'below-peak': f"Trending down from his peak: {latest['av']} AV in {latest['season']} against a career-best {peak['av']} in {peak['season']}.",
                 'developing': f"Still developing: {latest['av']} AV in {latest['season']}.",
                 'out': f"Career-best season: {peak['av']} AV in {peak['season']}.", 'early': ''}[s]
        if trend:
            parts.append(trend)
    if out.get('strengths'):
        parts.append('Strengths in ' + str(latest['season']) + ': ' + ', '.join(f"{r['label'].lower()} {r['text']} ({ordinal(r['percentile'])} percentile)" for r in out['strengths'][:3]) + '.')
    if out.get('concerns'):
        parts.append('Weak spots: ' + ', '.join(f"{r['label'].lower()} {r['text']} ({ordinal(r['percentile'])} percentile)" for r in out['concerns'][:2]) + '.')
    if out.get('availability'):
        parts.append(out['availability'])
    cyr = out.get('careerYear')
    if cyr and out['state'] != 'out':
        diff = cyr['value'] - cyr['median']
        word = 'above' if diff > 0 else 'below' if diff < 0 else 'level with'
        parts.append(f"Versus the typical Year-{cyr['cy']} {SINGULAR[out['group']]} who played: {cyr['text']} {cyr['label'].lower()} against a median of {cyr['medianText']}" +
                     (f" ({word})." if word == 'level with' else f", {word} the norm."))
    return ' '.join(p for p in parts if p)


def main():
    drafts = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
    careers = json.loads((DATA / 'nfl-careers.json').read_text(encoding='utf-8'))
    benchmarks = json.loads((DATA / 'measurement-benchmarks.json').read_text(encoding='utf-8'))
    records = [{'id': f'{y}-{row[1]}', 'year': int(y), 'round': row[0], 'pick': row[1], 'team': row[2], 'name': row[4],
                'position': row[5], 'college': row[6]} for y, picks in drafts.items() for row in picks]
    profiles = {r['id']: json.loads((DATA / 'profiles' / f"{r['id']}.json").read_text(encoding='utf-8')) for r in records}
    grades = defaultdict(dict)
    for r in records:
        grades[r['year']][r['id']] = (profiles[r['id']]['workouts'].get('scouting') or {}).get('grade')
    by_class = defaultdict(list)
    for r in records:
        by_class[r['year']].append(r)
    productions = college_productions(profiles)
    groups = {}
    refs = {}
    for path in (DATA / 'careers').glob('*.json'):
        if path.stem == 'index':
            continue
        groups[path.stem] = json.loads(path.read_text(encoding='utf-8'))
        refs[path.stem] = reference_values(groups[path.stem])
    live = {'asOf': careers['asOf'], 'throughWeek': careers['inProgress']['throughWeek']}
    counts = defaultdict(int)
    for r in records:
        profile = profiles[r['id']]
        career = careers['players'][r['id']]
        group = groups_for_position(r['position'], career.get('nflRole'))[0]
        draft = draft_report(r, profile, by_class[r['year']], grades, benchmarks, productions)
        current = current_report(r, career['seasons'], profile.get('currentTeam') or {}, group, groups[group], refs[group], live)
        current['pfrUrl'] = career.get('pfrUrl')
        profile['scoutingReports'] = {'draft': draft, 'current': current,
                                      'note': 'Built from published grades, testing, college and NFL statistics in this archive. Not a film evaluation; full published scouting prose is linked, not reproduced.'}
        counts['grade'] += draft.get('grade') is not None
        counts['athletic'] += bool(draft['athletic'])
        counts['production'] += bool(draft['production'])
        counts['state:' + current['state']] += 1
        file = DATA / 'profiles' / f"{r['id']}.json"
        published = json.dumps(profile, ensure_ascii=False, separators=(',', ':'))
        if published != file.read_text(encoding='utf-8'):
            file.write_text(published, encoding='utf-8', newline='\n')
    print('Scouting reports built:', dict(counts))


if __name__ == '__main__':
    main()
