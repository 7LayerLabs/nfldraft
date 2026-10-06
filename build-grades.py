"""Archive grades on one 5.0-8.0 scale: draft grade (pre-draft only), hindsight grade, current grade.

Run after build-career-arcs.py:  python build-grades.py   (then build-scouting-reports.py, build-site.py)

Scale (the same tiers for all three grades)
  7.50-8.00 Rare, All-Pro caliber      6.30-6.49 Average starter
  7.00-7.49 Pro Bowl caliber           6.10-6.29 Spot starter / top backup
  6.70-6.99 High-end starter           6.00-6.09 Backup / special teams
  6.50-6.69 Quality starter            5.70-5.99 Fringe roster
                                       5.00-5.69 Did not stick

Hindsight grade: peak value delivered = mean of the player's best k seasons of Approximate Value
  (k = min(3, completed seasons since the draft; seasons without games count as 0), ranked against
  the 2017-2022 classes at the same position group, and the percentile mapped to the scale.
  Pro Bowls, AP All-Pro selections and major awards set floors. Classes with fewer than three
  completed seasons are provisional; the in-progress class has none.
Current grade: recent value = weighted AV of the last three completed seasons (0.6/0.3/0.1), ranked
  against every 2017-2025 season played at the position group and mapped the same way; honors in the latest season set floors; players not on a roster are capped at
  5.80; current-season rookies carry their draft grade until a season is complete.
Archive draft grade: one ridge regression across positions on information available before the draft
  (NFL.com grade percentile within the class, athletic-testing percentile, college production
  percentile within the class and position), trained on hindsight grades of the 2017-2021 classes.
  Those classes are graded out of sample (leave-one-class-out); later classes use the full fit.
  Predictions are spread to the family's hindsight distribution by rank (quantile mapping).
Writes local/data/grades.json and profile['grades'].
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from career_metrics import IN_PROGRESS_SEASON, LAST_COMPLETED_SEASON, groups_for_position

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'local' / 'data'
TIERS = [(7.5, 'Rare, All-Pro caliber'), (7.0, 'Pro Bowl caliber'), (6.7, 'High-end starter'), (6.5, 'Quality starter'),
         (6.3, 'Average starter'), (6.1, 'Spot starter / top backup'), (6.0, 'Backup / special teams'),
         (5.7, 'Fringe roster'), (0, 'Did not stick')]
# Percentile within the position group -> grade. Top 2.5% = Rare, next 4.5% = Pro Bowl caliber,
# next 6% high-end starter, next 7% quality starter, ... bottom 25% did not stick.
ANCHORS = [(0, 5.0), (25, 5.7), (40, 5.95), (50, 6.05), (60, 6.2), (70, 6.35), (80, 6.55), (87, 6.75), (93, 7.0), (97.5, 7.5), (100, 7.98)]
REFERENCE_CLASSES = (2017, 2022)  # four or more completed seasons: a full three-season peak
FAMILY = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE', 'T': 'OL', 'G': 'OL', 'C': 'OL', 'DE': 'EDGE',
          'DT': 'IDL', 'LB': 'LB', 'CB': 'CB', 'S': 'S', 'K': 'ST', 'P': 'ST', 'LS': 'ST'}
MAJOR = {'AP MVP', 'AP Offensive Player of the Year', 'AP Defensive Player of the Year'}
ROOKIE = {'AP Offensive Rookie of the Year', 'AP Defensive Rookie of the Year'}


def tier(grade):
    if grade is None:
        return None
    return next(label for floor, label in TIERS if grade >= floor - 1e-9)


def to_grade(value):
    if value <= ANCHORS[0][0]:
        return ANCHORS[0][1]
    for (x0, y0), (x1, y1) in zip(ANCHORS, ANCHORS[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return min(8.0, ANCHORS[-1][1] + (value - ANCHORS[-1][0]) * 0.01)


def percentile_in(value, reference):
    if not reference:
        return 50.0
    below = sum(1 for v in reference if v < value)
    ties = sum(1 for v in reference if v == value)
    return 100 * (below + ties / 2) / len(reference)


def honors_floor(seasons):
    pro_bowls = sum(1 for s in seasons if s.get('pro_bowl'))
    all_pros = sum(1 for s in seasons if s.get('all_pro'))
    awards = {a for s in seasons for a in s.get('awards', [])}
    floor = 0
    if pro_bowls >= 1:
        floor = 6.8
    if pro_bowls >= 3:
        floor = 7.1
    if all_pros >= 1:
        floor = max(floor, 7.3)
    if all_pros >= 2:
        floor = max(floor, 7.6)
    if awards & MAJOR:
        floor = max(floor, 7.7)
    if awards & ROOKIE:
        floor = max(floor, 6.9)
    return floor


def ranks(values):
    order = np.argsort(values, kind='mergesort')
    out = np.empty(len(values))
    out[order] = np.arange(len(values))
    # average ties
    vals = np.asarray(values)
    for v in np.unique(vals):
        idx = np.where(vals == v)[0]
        out[idx] = out[idx].mean()
    return out


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    return float(np.corrcoef(ra, rb)[0, 1])


def pct_rank(value, values):
    values = [v for v in values if v is not None]
    if value is None or not values:
        return None
    below = sum(1 for v in values if v < value)
    ties = sum(1 for v in values if v == value)
    return 100 * (below + ties / 2) / len(values)


def main():
    drafts = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
    careers = json.loads((DATA / 'nfl-careers.json').read_text(encoding='utf-8'))
    records = [{'id': f'{y}-{row[1]}', 'year': int(y), 'round': row[0], 'pick': row[1], 'name': row[4], 'position': row[5]}
               for y, picks in drafts.items() for row in picks]
    profiles = {r['id']: json.loads((DATA / 'profiles' / f"{r['id']}.json").read_text(encoding='utf-8')) for r in records}
    for r in records:
        r['group'] = groups_for_position(r['position'], careers['players'][r['id']].get('nflRole'))[0]
        r['family'] = FAMILY[r['group']]
        r['seasons'] = careers['players'][r['id']]['seasons']

    def peak_value(r):
        completed = [s for s in r['seasons'] if s['season'] <= LAST_COMPLETED_SEASON]
        if not completed:
            return None, 0
        k = min(3, len(completed))
        avs = sorted(((s.get('av') or 0) if s['g'] else 0 for s in completed), reverse=True)
        return sum(avs[:k]) / k, len(completed)

    # Reference distributions per position group
    peak_ref = defaultdict(list)
    season_ref = defaultdict(list)
    for r in records:
        value, n = peak_value(r)
        if value is not None and REFERENCE_CLASSES[0] <= r['year'] <= REFERENCE_CLASSES[1]:
            peak_ref[r['group']].append(value)
        for s in r['seasons']:
            if s['season'] <= LAST_COMPLETED_SEASON and s['g'] > 0 and s.get('av') is not None:
                season_ref[r['group']].append(s['av'])
    factor = {g: len(v) for g, v in peak_ref.items()}  # reference sizes, reported for transparency

    # Hindsight grades
    for r in records:
        completed = [s for s in r['seasons'] if s['season'] <= LAST_COMPLETED_SEASON]
        value, n = peak_value(r)
        if value is None:
            r['hindsight'] = None
            continue
        k = min(3, len(completed))
        avs = sorted(((s.get('av') or 0) if s['g'] else 0 for s in completed), reverse=True)
        r['hindsightPercentile'] = round(percentile_in(value, peak_ref[r['group']]), 1)
        grade = max(to_grade(r['hindsightPercentile']), honors_floor(completed))
        if not any(s['g'] for s in completed):
            grade = min(grade, 5.3)
        r['hindsight'] = round(grade, 2)
        r['hindsightPeakAv'] = round(sum(avs[:k]) / k, 1)
        r['hindsightProvisional'] = len(completed) < 3

    # Pre-draft features
    by_class_pos = defaultdict(list)
    for r in records:
        by_class_pos[(r['year'], r['position'])].append(r)
    class_grades = defaultdict(list)
    for r in records:
        g = (profiles[r['id']]['workouts'].get('scouting') or {}).get('grade') or None  # 0.0 = not graded
        r['nflGrade'] = g
        if g is not None:
            class_grades[r['year']].append(g)
    for r in records:
        report = (profiles[r['id']].get('scoutingReports') or {}).get('draft') or {}
        r['f_nfl'] = pct_rank(r['nflGrade'], class_grades[r['year']])
        tests = [t['percentile'] for t in report.get('athletic', []) if t['kind'] != 'size']
        r['f_ath'] = float(np.mean(tests)) if tests else None
        prod = report.get('production') or []
        vals = []
        for p in prod[:2]:
            if p.get('finalRank') and p.get('finalOf'):
                vals.append(100 * (1 - (p['finalRank'] - 1) / max(1, p['finalOf'])))
            if p.get('careerRank') and p.get('careerOf'):
                vals.append(100 * (1 - (p['careerRank'] - 1) / max(1, p['careerOf'])))
        r['f_prod'] = float(np.mean(vals)) if vals else None

    def design(rows):
        x = []
        for r in rows:
            feats = []
            for key in ('f_nfl', 'f_ath', 'f_prod'):
                v = r[key]
                feats += [(v if v is not None else 50.0) / 100.0, 1.0 if v is None else 0.0]
            x.append([1.0] + feats)
        return np.array(x)

    def fit(rows, lam=2.0):
        x = design(rows)
        y = np.array([r['hindsight'] for r in rows])
        penalty = lam * np.eye(x.shape[1])
        penalty[0, 0] = 0
        return np.linalg.solve(x.T @ x + penalty, x.T @ y)

    train_classes = range(2017, 2022)
    # One pooled model across positions (per-position models overfit the small samples);
    # each 2017-2021 class is predicted by a model that never saw that class's outcomes.
    graded = [r for r in records if r['hindsight'] is not None]
    train = [r for r in graded if r['year'] in train_classes]
    full = fit(train)
    weights_report = {'pooled': {'trainingPlayers': len(train), 'intercept': round(float(full[0]), 3),
                                 'nflGradePct': round(float(full[1]), 3), 'athleticPct': round(float(full[3]), 3),
                                 'productionPct': round(float(full[5]), 3)}}
    fold = {year: fit([t for t in train if t['year'] != year]) for year in train_classes}
    for r in records:
        beta = fold[r['year']] if r['year'] in train_classes else full
        r['rawDraft'] = float(design([r])[0] @ beta)
    # Spread predictions to each family's hindsight distribution (2017-2021 outcomes) by rank
    for family in sorted(set(r['family'] for r in records)):
        members = [r for r in records if r['family'] == family]
        outcomes = np.sort([r['hindsight'] for r in train if r['family'] == family])
        rr = ranks([r['rawDraft'] for r in members])
        for r, rank in zip(members, rr):
            r['draftGrade'] = round(float(np.quantile(outcomes, (rank + .5) / len(members))), 2)

    # Current grades
    for r in records:
        profile = profiles[r['id']]
        team = profile.get('currentTeam') or {}
        completed = [s for s in r['seasons'] if s['season'] <= LAST_COMPLETED_SEASON]
        if not completed:
            r['current'] = r.get('draftGrade')
            r['currentBasis'] = 'draft grade (no completed NFL season yet)'
            continue
        recent = list(reversed(completed[-3:]))
        weights = [.6, .3, .1][:len(recent)]
        value = sum(w * ((s.get('av') or 0) if s['g'] else 0) for w, s in zip(weights, recent)) / sum(weights)
        grade = to_grade(percentile_in(value, season_ref[r['group']]))
        latest = completed[-1]
        if latest.get('all_pro'):
            grade = max(grade, 7.3)
        elif latest.get('pro_bowl'):
            grade = max(grade, 6.8)
        live = next((s for s in r['seasons'] if s.get('inProgress')), None)
        status = (team.get('statusLabel') or '').lower()
        if not team.get('team'):
            if 'retire' in status or 'deceased' in status:
                r['current'] = None
                r['currentBasis'] = team.get('statusLabel')
                continue
            grade = min(grade, 5.8)
            basis = 'not on a roster (' + (team.get('statusLabel') or 'status unconfirmed').lower() + ')'
        else:
            basis = 'last three seasons of AV'
            usage = ((live or {}).get('usage') or {})
            share = max((u.get('share') or 0) for u in usage.values()) if usage else 0
            if live and live['g'] >= 2 and share >= .6:
                grade += .05
                basis += ', every-down role in ' + str(IN_PROGRESS_SEASON)
        r['current'] = round(min(8.0, grade), 2)
        r['currentBasis'] = basis

    # Accuracy check on 2017-2021: who ranks careers better, NFL.com grade or the archive draft grade?
    evaluation = {}
    for family in sorted(set(r['family'] for r in records)) + ['ALL']:
        rows = [r for r in records if (family == 'ALL' or r['family'] == family) and r['year'] in train_classes
                and r['hindsight'] is not None and r['nflGrade'] is not None and r.get('draftGrade') is not None]
        if len(rows) < 15:
            continue
        if family == 'ALL':
            nfl = [r['f_nfl'] for r in rows]
            ours = [r['rawDraft'] for r in rows]
        else:
            nfl = [r['nflGrade'] for r in rows]
            ours = [r['draftGrade'] for r in rows]
        evaluation[family] = {'players': len(rows), 'nflSpearman': round(spearman(nfl, [r['hindsight'] for r in rows]), 3),
                              'archiveSpearman': round(spearman(ours, [r['hindsight'] for r in rows]), 3),
                              'pickSpearman': round(spearman([-r['pick'] for r in rows], [r['hindsight'] for r in rows]), 3)}

    out = {'scale': [{'min': floor, 'label': label} for floor, label in TIERS], 'percentileAnchors': ANCHORS,
           'referencePlayers': factor, 'weights': weights_report,
           'evaluation2017to2021': evaluation, 'players': {}}
    for r in records:
        grades = {
            'nfl': r['nflGrade'],
            'draft': r.get('draftGrade'), 'draftTier': tier(r.get('draftGrade')),
            'draftInputs': {'nflGradePct': None if r['f_nfl'] is None else round(r['f_nfl'], 1),
                            'athleticPct': None if r['f_ath'] is None else round(r['f_ath'], 1),
                            'productionPct': None if r['f_prod'] is None else round(r['f_prod'], 1)},
            'draftOutOfSample': r['year'] in train_classes,
            'hindsight': r['hindsight'], 'hindsightTier': tier(r['hindsight']),
            'hindsightPeakAv': r.get('hindsightPeakAv'), 'hindsightProvisional': r.get('hindsightProvisional'),
            'current': r.get('current'), 'currentTier': tier(r.get('current')), 'currentBasis': r.get('currentBasis'),
            'family': r['family'], 'group': r['group'],
        }
        out['players'][r['id']] = grades
        profile = profiles[r['id']]
        profile['grades'] = grades
        file = DATA / 'profiles' / f"{r['id']}.json"
        published = json.dumps(profile, ensure_ascii=False, separators=(',', ':'))
        if published != file.read_text(encoding='utf-8'):
            file.write_text(published, encoding='utf-8', newline='\n')
    (DATA / 'grades.json').write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
    compact = {'scale': out['scale'], 'evaluation2017to2021': evaluation, 'weights': weights_report,
               'columns': ['nfl', 'draft', 'hindsight', 'current', 'provisional', 'family'],
               'players': {r['id']: [r['nflGrade'], r.get('draftGrade'), r['hindsight'], r.get('current'),
                                     1 if r.get('hindsightProvisional') else 0, r['family']] for r in records}}
    (DATA / 'grades-compact.json').write_text(json.dumps(compact, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
    print('Reference players per group:', dict(sorted(factor.items())))
    print('Who ranks 2017-2021 careers better (Spearman with hindsight grade):')
    for family, e in evaluation.items():
        print(f"  {family:4} n={e['players']:4}  NFL.com {e['nflSpearman']:+.3f}  archive {e['archiveSpearman']:+.3f}  draft slot {e['pickSpearman']:+.3f}")


if __name__ == '__main__':
    main()
