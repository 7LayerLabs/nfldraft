"""Collect regular-season NFL career statistics for every drafted player, 2017-2026.

Run: python collect-nfl-careers.py            (downloads missing inputs, rebuilds output)
     python collect-nfl-careers.py --refresh  (re-downloads every input, e.g. weekly in season)
     python collect-nfl-careers.py --refresh-current  (re-downloads only in-progress season and cumulative files)

Inputs are public nflverse releases cached under ~/.agent-reach/nfl-player-profiles/nflverse:
player season/week statistics (NFL play-by-play), PFR snap counts, PFR advanced
passing/rushing/receiving/defense tables (2018+), schedules with starting QBs, the
player ID table and PFR draft-page records. Pro Football Reference blocks automated
requests, so PFR data arrives through these nflverse redistributions.

Output: local/data/nfl-careers.json with one row per career year, from the draft season
through the in-progress season, including seasons with no games.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

from career_metrics import FIRST_DRAFT, IN_PROGRESS_SEASON, LAST_COMPLETED_SEASON, derive

ROOT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles' / 'nflverse'
OUTPUT = ROOT / 'local' / 'data' / 'nfl-careers.json'
RELEASES = 'https://github.com/nflverse/nflverse-data/releases/download/'
SEASONS = list(range(FIRST_DRAFT, IN_PROGRESS_SEASON + 1))

INPUTS = {
    'draft_picks.csv': ('draft_picks/draft_picks.csv', 'PFR draft-page records with PFR/GSIS IDs and PFR career totals'),
    'players.csv': ('players/players.csv', 'nflverse player ID crosswalk'),
    'games.csv': ('schedules/games.csv', 'NFL schedules, results and starting quarterbacks'),
    'advstats_season_def.csv': ('pfr_advstats/advstats_season_def.csv', 'PFR advanced defense, 2018+'),
    'advstats_season_rec.csv': ('pfr_advstats/advstats_season_rec.csv', 'PFR advanced receiving, 2018+'),
    'advstats_season_rush.csv': ('pfr_advstats/advstats_season_rush.csv', 'PFR advanced rushing, 2018+'),
    'advstats_season_pass.csv': ('pfr_advstats/advstats_season_pass.csv', 'PFR advanced passing, 2018+'),
}
for season in SEASONS:
    INPUTS[f'stats_player_reg_{season}.csv'] = (f'stats_player/stats_player_reg_{season}.csv', f'{season} regular-season player statistics')
    INPUTS[f'stats_player_week_{season}.csv'] = (f'stats_player/stats_player_week_{season}.csv', f'{season} weekly player statistics')
    INPUTS[f'snap_counts_{season}.csv'] = (f'snap_counts/snap_counts_{season}.csv', f'{season} PFR snap counts')
    INPUTS[f'play_by_play_{season}.csv.gz'] = (f'pbp/play_by_play_{season}.csv.gz', f'{season} NFL play-by-play (penalty detail)')
CURRENT_FILES = {name for name in INPUTS if str(IN_PROGRESS_SEASON) in name or not re.search(r'_\d{4}\.csv(\.gz)?$', name)}
# Collected from pro-football-reference.com in a real browser session (team rosters, Pro Bowl and
# All-Pro pages, award pages); see collect-pfr-browser.js. Optional: without it, games/starts fall back
# to snap counts and published starts, and honors/AV are omitted.
PFR_FILE = CACHE.parent / 'pfr' / 'pfr-rosters-honors.json'
AWARDS = {'ap-nfl-mvp-award': 'AP MVP', 'ap-offensive-player-of-the-year': 'AP Offensive Player of the Year',
          'ap-defensive-player-of-the-year': 'AP Defensive Player of the Year',
          'ap-offensive-rookie-of-the-year-award': 'AP Offensive Rookie of the Year',
          'ap-defensive-rookie-of-the-year-award': 'AP Defensive Rookie of the Year',
          'ap-comeback-player-award': 'AP Comeback Player of the Year', 'super-bowl-mvp-award': 'Super Bowl MVP',
          'walter-payton-man-of-the-year': 'Walter Payton Man of the Year'}
PENALTIES = {'Offensive Holding': 'holds', 'False Start': 'false_starts', 'Defensive Pass Interference': 'dpi',
             'Defensive Holding': 'def_holds', 'Roughing the Passer': 'rtp', 'Defensive Offside': 'offsides',
             'Neutral Zone Infraction': 'offsides', 'Encroachment': 'offsides', 'Illegal Use of Hands': 'hands',
             'Offensive Pass Interference': 'opi', 'Unnecessary Roughness': 'roughness', 'Face Mask': 'face_masks'}


def fetch(name, refresh):
    target = CACHE / name
    if target.exists() and not refresh:
        return target
    url = RELEASES + INPUTS[name][0]
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'NFLDraftArchive/1.0 career-collector'})
            with urllib.request.urlopen(request, timeout=120) as response:
                content = response.read()
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 3:
                raise RuntimeError(f'Unable to download {url}: {exc}')
            time.sleep(2 ** attempt)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    print(f'DOWNLOADED {name} ({len(content):,} bytes)')
    return target


def rows(name):
    with (CACHE / name).open(encoding='utf-8', newline='') as handle:
        return list(csv.DictReader(handle))


def num(value):
    if value in (None, '', 'NA', 'NaN', 'nan'):
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def add(target, key, value):
    if value is not None:
        target[key] = (target.get(key) or 0) + value


def div(a, b):
    return a / b if a is not None and b else None


def norm_name(value):
    text = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z]', '', re.sub(r'\b(jr|sr|ii|iii|iv|v)\b\.?', '', text))


def load_picks():
    data = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
    records = []
    for year, picks in data.items():
        for row in picks:
            round_, pick, team, via, name, position, college = row[:7]
            records.append({'id': f'{year}-{pick}', 'year': int(year), 'round': round_, 'pick': pick,
                            'team': team, 'name': name, 'position': position, 'college': college})
    assert len(records) == 2569
    return records


def resolve_ids(records):
    draft = {(int(r['season']), int(r['pick'])): r for r in rows('draft_picks.csv') if int(r['season']) >= FIRST_DRAFT}
    players = rows('players.csv')
    by_pfr = {p['pfr_id']: p for p in players if p['pfr_id']}
    by_gsis = {p['gsis_id']: p for p in players if p['gsis_id']}
    report = {'pfrMatched': 0, 'gsisFromDraft': 0, 'gsisFromCrosswalk': 0, 'gsisMissing': [], 'nicknameMatches': []}
    ids = {}
    for record in records:
        source = draft.get((record['year'], record['pick']))
        if not source:
            raise SystemExit(f'No PFR draft record for {record["id"]} {record["name"]}')
        pfr = source['pfr_player_id']
        gsis = source['gsis_id'] or by_pfr.get(pfr, {}).get('gsis_id', '')
        if source['gsis_id']:
            report['gsisFromDraft'] += 1
        elif gsis:
            report['gsisFromCrosswalk'] += 1
        else:
            report['gsisMissing'].append(record['id'])
        if pfr:
            report['pfrMatched'] += 1
        if norm_name(source['pfr_player_name'])[:4] != norm_name(record['name'])[:4]:
            report['nicknameMatches'].append({'id': record['id'], 'archive': record['name'], 'pfr': source['pfr_player_name']})
        crosswalk = by_pfr.get(pfr) or by_gsis.get(gsis) or {}
        birth = crosswalk.get('birth_date') or ''
        ids[record['id']] = {'pfr': pfr, 'gsis': gsis, 'birthYear': int(birth[:4]) if birth[:4].isdigit() else None,
                             'pfrName': source['pfr_player_name'], 'role': crosswalk.get('pff_position') or None}
    return ids, report


def load_advanced(birth_years):
    """One row per (pfr_id, season) per advanced table, choosing multi-team totals.

    nflverse occasionally attaches two different players to one PFR ID; rows whose age
    contradicts the drafted player's birth year are discarded.
    """
    tables = {}
    conflicts = []
    for name, key in (('def', 'advstats_season_def.csv'), ('rec', 'advstats_season_rec.csv'),
                      ('rush', 'advstats_season_rush.csv'), ('pass', 'advstats_season_pass.csv')):
        grouped = defaultdict(list)
        for row in rows(key):
            if row.get('pfr_id') and row['pfr_id'] in birth_years:
                grouped[(row['pfr_id'], int(row['season']))].append(row)
        resolved = {}
        for (pfr, season), candidates in grouped.items():
            birth = birth_years[pfr]
            if birth and all(c.get('age') for c in candidates):
                kept = [c for c in candidates if abs(int(float(c['age'])) - (season - birth)) <= 1]
                if len(kept) != len(candidates):
                    conflicts.append({'table': name, 'pfrId': pfr, 'season': season, 'discarded': len(candidates) - len(kept)})
                candidates = kept
            if not candidates:
                continue
            team_key = 'tm' if 'tm' in candidates[0] else 'team'
            totals = [c for c in candidates if re.fullmatch(r'\dTM', c.get(team_key, ''))]
            resolved[(pfr, season)] = totals[0] if totals else max(candidates, key=lambda c: num(c.get('g') or c.get('pass_attempts')) or 0)
        tables[name] = resolved
    return tables, conflicts


def load_snaps():
    """Per-player weekly snaps and per-team weekly snap totals for regular seasons."""
    player_weeks = defaultdict(list)  # (pfr, season) -> [(week, team, {side: (snaps, pct)})]
    estimates = defaultdict(list)     # (season, week, team, side) -> derived team totals
    team_weeks = defaultdict(set)
    for season in SEASONS:
        for row in rows(f'snap_counts_{season}.csv'):
            if row['game_type'] != 'REG':
                continue
            week, team = int(row['week']), row['team']
            team_weeks[(season, team)].add(week)
            sides = {}
            for side, prefix in (('off', 'offense'), ('def', 'defense'), ('st', 'st')):
                snaps, pct = num(row[prefix + '_snaps']) or 0, num(row[prefix + '_pct']) or 0
                sides[side] = (snaps, pct)
                if pct >= .3 and snaps:
                    estimates[(season, week, team, side)].append(snaps / pct)
            if row['pfr_player_id']:
                player_weeks[(row['pfr_player_id'], season)].append((week, team, sides))
    team_totals = {key: round(statistics.median(values)) for key, values in estimates.items()}
    return player_weeks, team_totals, team_weeks


def usage_for(weeks, season, team_totals, team_weeks):
    if not weeks:
        return None, []
    weeks = sorted(weeks)
    teams = []
    for _, team, _ in weeks:
        if team not in teams:
            teams.append(team)
    usage = {}
    for side in ('off', 'def', 'st'):
        snaps = sum(s[side][0] for _, _, s in weeks)
        active_den = sum(team_totals.get((season, w, t, side), 0) for w, t, s in weeks)
        # Each week of the season belongs to the team of the latest appearance on or before it.
        season_den = 0
        all_weeks = sorted({w for t in teams for w in team_weeks[(season, t)]})
        for week in all_weeks:
            owner = weeks[0][1]
            for w, t, _ in weeks:
                if w <= week:
                    owner = t
            if week in team_weeks[(season, owner)]:
                season_den += team_totals.get((season, week, owner, side), 0)
        usage[side] = {'snaps': snaps, 'share': div(snaps, season_den) or 0, 'active': div(snaps, active_den),
                       'g50': sum(1 for _, _, s in weeks if s[side][1] >= .5),
                       'games': sum(1 for _, _, s in weeks if s[side][0] > 0)}
    usage['games'] = sum(1 for _, _, s in weeks if any(s[side][0] for side in s))
    return usage, teams


def load_qb_starts():
    starts = defaultdict(lambda: {'gs': 0, 'w': 0, 'l': 0, 't': 0})
    for game in rows('games.csv'):
        if game['game_type'] != 'REG' or not game['season'].isdigit() or int(game['season']) < FIRST_DRAFT:
            continue
        if game['result'] in ('', 'NA'):
            continue
        home, away = num(game['home_score']), num(game['away_score'])
        for qb, scored, allowed in ((game['home_qb_id'], home, away), (game['away_qb_id'], away, home)):
            if not qb or qb == 'NA':
                continue
            record = starts[(qb, int(game['season']))]
            record['gs'] += 1
            record['w' if scored > allowed else 'l' if scored < allowed else 't'] += 1
    return starts


def load_week_shares():
    """Carry share = player carries / team carries in weeks the player recorded a stat."""
    team_carries = defaultdict(int)
    player = defaultdict(list)
    through_week = 0
    for season in SEASONS:
        for row in rows(f'stats_player_week_{season}.csv'):
            if row.get('season_type') != 'REG':
                continue
            week = int(row['week'])
            carries = num(row['carries']) or 0
            team_carries[(season, week, row['team'])] += carries
            player[(row['player_id'], season)].append((week, row['team'], carries))
            if season == IN_PROGRESS_SEASON:
                through_week = max(through_week, week)
    shares = {}
    for key, weeks in player.items():
        denominator = sum(team_carries[(key[1], w, t)] for w, t, _ in weeks)
        shares[key] = div(sum(c for _, _, c in weeks), denominator)
    return shares, through_week


def season_row(season, draft_year, stat, usage, teams, adv, qb, carry_share, is_qb):
    s = {'season': season, 'cy': season - draft_year + 1}
    if season == IN_PROGRESS_SEASON:
        s['inProgress'] = True
    games = max(usage['games'] if usage else 0, int(num(stat.get('games')) or 0) if stat else 0)
    s['g'] = games
    if teams:
        s['teams'] = teams
    elif stat and stat.get('recent_team'):
        s['teams'] = [stat['recent_team']]
    if usage:
        s['usage'] = {side: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in usage[side].items() if v is not None}
                      for side in ('off', 'def', 'st')}
    if stat:
        g = lambda key: num(stat.get(key))
        mapping = {'cmp': 'completions', 'att': 'attempts', 'pass_yds': 'passing_yards', 'pass_td': 'passing_tds',
                   'int': 'passing_interceptions', 'sacks_taken': 'sacks_suffered', 'sack_yds': 'sack_yards_lost',
                   'pass_epa': 'passing_epa', 'cpoe': 'passing_cpoe', 'carries': 'carries', 'rush_yds': 'rushing_yards',
                   'rush_td': 'rushing_tds', 'targets': 'targets', 'rec': 'receptions', 'rec_yds': 'receiving_yards',
                   'rec_td': 'receiving_tds', 'rec_fd': 'receiving_first_downs', 'air_yards': 'receiving_air_yards',
                   'yac': 'receiving_yards_after_catch', 'target_share': 'target_share', 'air_share': 'air_yards_share',
                   'wopr': 'wopr', 'tfl': 'def_tackles_for_loss', 'sacks': 'def_sacks', 'qb_hits': 'def_qb_hits',
                   'ff': 'def_fumbles_forced', 'pd': 'def_pass_defended', 'def_int': 'def_interceptions',
                   'penalties': 'penalties', 'penalty_yds': 'penalty_yards', 'fgm': 'fg_made', 'fga': 'fg_att',
                   'fg_long': 'fg_long', 'xpm': 'pat_made', 'xpa': 'pat_att', 'punts': 'pt_att', 'punt_yds': 'pt_yards',
                   'punt_net_yds': 'pt_net_yards', 'in20': 'pt_inside_20', 'kr': 'kickoff_returns',
                   'kr_yds': 'kickoff_return_yards', 'pr': 'punt_returns', 'pr_yds': 'punt_return_yards',
                   'ppr': 'fantasy_points_ppr'}
        for key, column in mapping.items():
            value = g(column)
            if value not in (None, 0):
                s[key] = value
        tackles = sum(g(k) or 0 for k in ('def_tackles_solo', 'def_tackles_with_assist', 'def_tackle_assists'))
        if tackles:
            s['tackles'] = tackles
        fumbles = sum(g(k) or 0 for k in ('rushing_fumbles_lost', 'receiving_fumbles_lost', 'sack_fumbles_lost'))
        if fumbles:
            s['fum_lost'] = fumbles
        fg50 = (g('fg_made_50_59') or 0) + (g('fg_made_60_') or 0)
        if fg50:
            s['fg50'] = fg50
    if carry_share is not None and s.get('carries'):
        s['carry_share'] = round(carry_share, 4)
    # PFR advanced tables (2018+)
    starts = []
    if adv.get('def'):
        d = adv['def']
        for key, column in (('pressures', 'prss'), ('hurries', 'hrry'), ('tgt_allowed', 'tgt'), ('cmp_allowed', 'cmp'),
                            ('yds_allowed', 'yds'), ('td_allowed', 'td'), ('m_tkl', 'm_tkl')):
            value = num(d.get(column))
            if value is not None:
                s[key] = value
        if num(d.get('rat')) is not None and num(d.get('tgt')):
            s['rating_allowed'] = num(d['rat'])
        comb, missed = num(d.get('comb')) or 0, num(d.get('m_tkl')) or 0
        if comb + missed:
            s['tackle_att'] = comb + missed
            s['missed_tkl_pct'] = round(missed / (comb + missed), 4)
        starts.append(num(d.get('gs')))
    if adv.get('rec'):
        r = adv['rec']
        if num(r.get('adot')) is not None:
            s['adot'] = num(r['adot'])
        if num(r.get('drop')) is not None:
            s['drops'] = num(r['drop'])
        add(s, 'brk_tkl', num(r.get('brk_tkl')))
        starts.append(num(r.get('gs')))
    if adv.get('rush'):
        r = adv['rush']
        if num(r.get('yac_att')) is not None:
            s['yac_att'] = num(r['yac_att'])
        add(s, 'brk_tkl', num(r.get('brk_tkl')))
        starts.append(num(r.get('gs')))
    if adv.get('pass'):
        p = adv['pass']
        for key, column in (('on_tgt_pct', 'on_tgt_pct'), ('pressure_pct', 'pressure_pct')):
            value = num(p.get(column))
            if value is not None:
                s[key] = round(value / 100, 4)
    if is_qb:
        s['gs'] = qb['gs'] if qb else 0
        if qb and qb['gs']:
            s['qb_wins'], s['qb_losses'], s['qb_ties'] = qb['w'], qb['l'], qb['t']
            s['win_pct'] = round((qb['w'] + .5 * qb['t']) / qb['gs'], 4)
    else:
        known = [v for v in starts if v is not None]
        if known:
            s['gs'] = max(known)
            s['gsSource'] = 'pfr-advanced'
        elif season >= 2018 and games == 0:
            s['gs'] = 0
    derive(s)
    return s


def load_penalties():
    """Accepted regular-season penalties by player and type from play-by-play."""
    import gzip
    counts = defaultdict(lambda: defaultdict(int))
    for season in SEASONS:
        with gzip.open(CACHE / f'play_by_play_{season}.csv.gz', 'rt', encoding='utf-8', newline='') as handle:
            for row in csv.DictReader(handle):
                if row['season_type'] != 'REG' or row['penalty'] != '1' or row['penalty_player_id'] in ('', 'NA'):
                    continue
                key = PENALTIES.get(row['penalty_type'])
                if key:
                    counts[(row['penalty_player_id'], season)][key] += 1
    return counts


def load_pfr():
    if not PFR_FILE.exists():
        return None
    data = json.loads(PFR_FILE.read_text(encoding='utf-8'))
    rosters = defaultdict(lambda: {'g': 0, 'gs': 0, 'av': None, 'pos': [], 'teams': []})
    for pid, season, team, pos, g, gs, av, age in data['rosters']:
        r = rosters[(pid, int(season))]
        r['g'] += int(num(g) or 0)
        r['gs'] += int(num(gs) or 0)
        if num(av) is not None:  # PFR leaves AV blank until a season is complete
            r['av'] = (r['av'] or 0) + int(num(av))
        for value, key in ((pos, 'pos'), (team, 'teams')):
            if value and value not in r[key]:
                r[key].append(value)
    honors = defaultdict(dict)
    special = {'KR', 'PR', 'RET', 'ST'}  # return / coverage-unit honors, kept apart from positional honors
    for pid, season, pos, team, mark, text in data['probowl']:
        h = honors[(pid, int(season))]
        h['pro_bowl_st' if pos in special else 'pro_bowl'] = 1
        if pos not in special:
            h['pbAlternate'] = h.get('pbAlternate', True) and mark == '+'
    for pid, season, pos, team, mark, text in data['allpro']:
        h = honors[(pid, int(season))]
        suffix = '_st' if pos in special else ''
        if 'AP: 1st Tm' in text:
            h['all_pro' + suffix] = 1
        elif 'AP: 2nd Tm' in text and not suffix:
            h['all_pro_2nd'] = 1
    for award, season, pid in data['awards']:
        honors[(pid, int(season))].setdefault('awards', []).append(AWARDS.get(award, award))
    return {'rosters': rosters, 'honors': honors, 'collectedAt': data.get('finishedAt') or data.get('startedAt'),
            'pages': data.get('total'), 'errors': data.get('errors', [])}


def apply_pfr(row, roster, honors, penalties):
    if roster:
        snap_games = row['g']
        row['g'] = roster['g'] if roster['g'] or not snap_games else snap_games
        if row.get('inProgress'):
            # The PFR file is a point-in-time pull; weekly nflverse refreshes may be further along.
            row['g'] = max(roster['g'], snap_games)
        if snap_games != row['g']:
            row['gSnaps'] = snap_games
        row['gs'] = roster['gs']
        row['gsSource'] = 'pfr-roster'
        if roster['av'] is not None:
            row['av'] = roster['av']
        row['pfrPos'] = '/'.join(roster['pos'])
    if honors:
        for key in ('pro_bowl', 'all_pro', 'all_pro_2nd', 'pro_bowl_st', 'all_pro_st'):
            if honors.get(key):
                row[key] = 1
        if honors.get('pro_bowl') and honors.get('pbAlternate'):
            row['pbAlternate'] = True
        if honors.get('awards'):
            row['awards'] = sorted(set(honors['awards']))
    for key, value in (penalties or {}).items():
        row[key] = value


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--refresh', action='store_true', help='Re-download every nflverse input')
    parser.add_argument('--refresh-current', action='store_true', help='Re-download in-progress season and cumulative inputs')
    args = parser.parse_args()
    manifest = []
    for name, (path, label) in INPUTS.items():
        target = fetch(name, args.refresh or (args.refresh_current and name in CURRENT_FILES))
        content = target.read_bytes()
        manifest.append({'file': name, 'label': label, 'url': RELEASES + path, 'bytes': len(content),
                         'sha256': hashlib.sha256(content).hexdigest(),
                         'downloadedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(target.stat().st_mtime))})
    records = load_picks()
    ids, id_report = resolve_ids(records)
    birth_years = {v['pfr']: v['birthYear'] for v in ids.values() if v['pfr']}
    print('Loading PFR advanced tables...')
    advanced, conflicts = load_advanced(birth_years)
    print('Loading PFR snap counts...')
    player_weeks, team_totals, team_weeks = load_snaps()
    print('Loading schedules and weekly shares...')
    qb_starts = load_qb_starts()
    carry_shares, through_week = load_week_shares()
    print('Loading play-by-play penalties...')
    penalties = load_penalties()
    pfr = load_pfr()
    print('PFR roster/honors file:', 'loaded' if pfr else 'not found (games/starts from snap counts; no AV/honors)')
    season_stats = {}
    for season in SEASONS:
        for row in rows(f'stats_player_reg_{season}.csv'):
            season_stats[(row['player_id'], season)] = row
    players = {}
    coverage = {'playersWithAnyGame': 0, 'playerSeasons': 0, 'playedSeasons': 0, 'statsWithoutSnaps': 0}
    for record in records:
        ident = ids[record['id']]
        seasons = []
        for season in range(record['year'], IN_PROGRESS_SEASON + 1):
            usage, teams = usage_for(player_weeks.get((ident['pfr'], season), []), season, team_totals, team_weeks)
            stat = season_stats.get((ident['gsis'], season)) if ident['gsis'] else None
            adv = {name: table.get((ident['pfr'], season)) for name, table in advanced.items()}
            row = season_row(season, record['year'], stat, usage, teams, adv,
                             qb_starts.get((ident['gsis'], season)), carry_shares.get((ident['gsis'], season)),
                             record['position'] == 'QB')
            apply_pfr(row, pfr['rosters'].get((ident['pfr'], season)) if pfr else None,
                      pfr['honors'].get((ident['pfr'], season)) if pfr else None,
                      penalties.get((ident['gsis'], season)) if ident['gsis'] else None)
            if stat and not usage and row['g']:
                coverage['statsWithoutSnaps'] += 1
            coverage['playerSeasons'] += 1
            coverage['playedSeasons'] += row['g'] > 0
            seasons.append(row)
        if any(s['g'] for s in seasons):
            coverage['playersWithAnyGame'] += 1
        players[record['id']] = {'pfrId': ident['pfr'], 'gsisId': ident['gsis'] or None, 'nflRole': ident['role'],
                                 'pfrUrl': f'https://www.pro-football-reference.com/players/{ident["pfr"][0]}/{ident["pfr"]}.htm' if ident['pfr'] else None,
                                 'seasons': seasons}
    output = {
        'asOf': time.strftime('%Y-%m-%d'),
        'completedSeasons': [s for s in SEASONS if s <= LAST_COMPLETED_SEASON],
        'inProgress': {'season': IN_PROGRESS_SEASON, 'throughWeek': through_week},
        'basis': 'Regular season only. Career year 1 is the draft season. Every season from the draft season through the in-progress season is listed, including seasons with no games.',
        'sourceNote': 'Games played, games started, Approximate Value and honors come from Pro Football Reference pages collected in a browser session. Box-score statistics come from NFL play-by-play via nflverse, with PFR snap counts, advanced charting and draft-page records from nflverse redistributions.',
        'sources': manifest,
        'identity': {**id_report, 'advancedRowConflicts': conflicts},
        'pfrBrowser': ({'collectedAt': pfr['collectedAt'], 'pages': pfr['pages'], 'errors': pfr['errors'],
                        'note': 'Games, games started, Approximate Value, positions, Pro Bowl, All-Pro and awards from pro-football-reference.com team roster, Pro Bowl, All-Pro and award pages.'} if pfr else None),
        'coverage': coverage,
        'players': players,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
    print(f'Wrote {OUTPUT.relative_to(ROOT)}: {len(players)} players, {coverage["playerSeasons"]} player-seasons '
          f'({coverage["playedSeasons"]} with games), {coverage["playersWithAnyGame"]} players with NFL games; '
          f'{IN_PROGRESS_SEASON} through Week {through_week}; {OUTPUT.stat().st_size:,} bytes')
    print(f'IDs: PFR {id_report["pfrMatched"]}/2569, GSIS draft {id_report["gsisFromDraft"]}, crosswalk {id_report["gsisFromCrosswalk"]}, missing {len(id_report["gsisMissing"])}; advanced conflicts {len(conflicts)}')


if __name__ == '__main__':
    sys.exit(main())
