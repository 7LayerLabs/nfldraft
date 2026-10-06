"""Reviewed primary-source event observations, separate from mixed combine datasets."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = {}


def report(pid, event, date, status, summary, label, url, readings=()):
    metrics = [{'key': key, 'label': name, 'value': value, 'unit': unit, 'designation': designation}
               for key, name, value, unit, designation in readings]
    data.setdefault(pid, {}).setdefault('publishedWorkouts', []).append(
        {'event': event, 'date': date, 'status': status, 'summary': summary,
         'sourceLabel': label, 'sourceUrl': url, 'metrics': metrics})


report('2017-10', 'Private workout · New York Jets', '2017-04-02', 'Reported completed',
       'Jets workout reported completed; numerical test results were not published.', 'NFL.com · Chase Goodbread',
       'https://www.nfl.com/news/mahomes-to-work-out-for-bills-reportedly-works-out-for-jets-0ap3000000797024')
report('2025-1', 'Miami pro day', '2025-03-24', 'Completed',
       'Throwing workout observed by Titans coaches and front-office staff; no timed drill results in this report.',
       'Tennessee Titans · Jim Wyatt', 'https://www.tennesseetitans.com/news/qb-cam-ward-makes-his-case-to-the-titans-at-miami-s-pro-day')
report('2025-1', 'Private workout · Tennessee Titans', '2025-03-28', 'Scheduled as of source publication',
       'Titans announced a planned Florida workout. This article confirms the schedule, not completion or test results.',
       'Tennessee Titans · Jim Wyatt', 'https://www.tennesseetitans.com/news/qb-cam-ward-makes-his-case-to-the-titans-at-miami-s-pro-day')
report('2026-1', 'Indiana pro day', '2026-04-01', 'Completed',
       'Reported throwing: 53/56 completed. Weight: 236 lb. No running drills.', 'NFL.com · Eric Edholm',
       'https://www.nfl.com/news/top-prospect-fernando-mendoza-shows-of-trademark-accuracy-at-indiana-pro-day',
       [('weight', 'Weight', 236, 'lb', 'reported'), ('throwingCompletions', 'Scripted throwing completions', 53, 'throws', 'reported'),
        ('throwingAttempts', 'Scripted throwing attempts', 56, 'throws', 'reported')])
report('2026-1', 'NFL Scouting Combine', '2026-02', 'Retrospectively reported',
       'Combine weight: 225 lb, reported in the subsequent pro-day article.', 'NFL.com · Eric Edholm',
       'https://www.nfl.com/news/top-prospect-fernando-mendoza-shows-of-trademark-accuracy-at-indiana-pro-day',
       [('weight', 'Combine weight', 225, 'lb', 'reported')])
report('2026-50', 'Indiana pro day', '2026-04-01', 'Completed', '40-yard dash: 4.31 sec, reported pro-day timing.',
       'NFL.com · Eric Edholm', 'https://www.nfl.com/news/top-prospect-fernando-mendoza-shows-of-trademark-accuracy-at-indiana-pro-day',
       [('fortyYardDash', '40-yard dash', 4.31, 's', 'reported')])
report('2021-5', 'LSU pro day', '2021-03-31', 'Completed', '40-yard dash: 4.38 sec; LSU explicitly labels the time unofficial.',
       'LSU Athletics', 'https://lsusports.net/news/2021/03/31/jamarr-chase-runs-4-38u-40-yard-dash-lsu-pro-day',
       [('fortyYardDash', '40-yard dash', 4.38, 's', 'UNOFFICIAL')])
oregon = 'https://goducks.com/news/2021/4/2/football-ducks-spread-wings-at-pro-day'
report('2021-7', 'Oregon pro day', '2021-04-02', 'Completed',
       '331 lb, 76.875 in tall, 30 bench reps, 109 in broad jump. Scout-reported 40 timings ranged 5.09–5.13 sec.',
       'Oregon Athletics · Rob Moseley', oregon,
       [('height', 'Height', 76.875, 'in', 'reported'), ('weight', 'Weight', 331, 'lb', 'reported'),
        ('benchPress', 'Bench press (225 lb)', 30, 'reps', 'reported'), ('broadJump', 'Broad jump', 109, 'in', 'reported'),
        ('fortyYardDash', '40-yard dash lower reported time', 5.09, 's', 'scout-reported'),
        ('fortyYardDash', '40-yard dash upper reported time', 5.13, 's', 'scout-reported')])
report('2021-215', 'Oregon pro day', '2021-04-02', 'Completed', 'Vertical jump: 38 in.',
       'Oregon Athletics · Rob Moseley', oregon, [('verticalJump', 'Vertical jump', 38, 'in', 'reported')])
report('2021-36', 'Oregon pro day', '2021-04-02', 'Completed', 'Broad jump: 126 in.',
       'Oregon Athletics · Rob Moseley', oregon, [('broadJump', 'Broad jump', 126, 'in', 'reported')])
duke = 'https://goduke.com/news/2021/3/29/football-duke-completes-2021-pro-day'
# Only unambiguous published units are converted. The school's ambiguous broad-jump notation is omitted.
for pid, height, weight, hand, arm, span, bench, vertical, forty, shuttle, cone in [
    ('2021-154',69.625,184,9.625,29.125,72.75,13,35.5,4.30,4.44,6.81),
    ('2021-210',73.5,262,9.5,33.125,80.125,28,34.5,4.78,4.35,7.09),
    ('2021-162',75,240,9.25,31.625,78.25,15,35,4.52,4.30,6.72),
    ('2021-118',74.875,244,9.25,33.75,80,18,None,None,None,None)]:
    pairs = [('height','Height',height,'in'),('weight','Weight',weight,'lb'),('handSize','Hand size',hand,'in'),
             ('armLength','Arm length',arm,'in'),('wingspan','Wingspan',span,'in'),('benchPress','Bench press',bench,'reps'),
             ('verticalJump','Vertical jump',vertical,'in'),('fortyYardDash','40-yard dash',forty,'s'),
             ('twentyYardShuttle','Short shuttle',shuttle,'s'),('threeConeDrill','Three-cone drill',cone,'s')]
    report(pid, 'Duke pro day', '2021-03-29', 'Completed',
           'School-published pro-day measurements; timing method was not specified.' if pid != '2021-118' else
           'School-published measurements; hamstring strain limited participation. Running and jump results were not published.',
           'Duke Athletics', duke, [(*p,'school-reported') for p in pairs if p[2] is not None])

nelson_url = 'https://storage.googleapis.com/fightingirish-com/2019/08/42673__m_footbl_2017_18_misc_non_event__Quenton_Nelson_Final_Bio.pdf'
data['2018-6'] = {'careerSummary': 'Notre Dame guard with 37 games and 36 starts. His 2017 season included 13 starts and 883 offensive snaps; the school reports zero sacks, one quarterback hit and three hurries allowed. Career: 2,474 snaps, three sacks and four quarterback hits allowed.',
                  'collegeSources': [{'label': 'Notre Dame · Quenton Nelson final college biography', 'url': nelson_url}],
                  'collegeExperience': [
                      {'year': 2014, 'games': 0, 'starts': 0}, {'year': 2015, 'games': 12, 'starts': 11},
                      {'year': 2016, 'games': 12, 'starts': 12},
                      {'year': 2017, 'games': 13, 'starts': 13, 'snaps': 883, 'sacksAllowed': 0, 'hitsAllowed': 1, 'hurriesAllowed': 3},
                      {'year': 'Career', 'games': 37, 'starts': 36, 'snaps': 2474, 'sacksAllowed': 3, 'hitsAllowed': 4}]
                  }
for row in data['2018-6']['collegeExperience']:
    row.update(sourceUrl=nelson_url, sourceLabel='Notre Dame college biography')
drafts = json.loads((ROOT / 'drafts.json').read_text(encoding='utf-8'))
names = {f'{year}-{r[1]}':r[4] for year, rows in drafts.items() for r in rows}
assert names['2021-215'] == 'Brady Breeze'
assert names['2021-36'] == 'Jevon Holland'
assert set(data) <= set(names)
(ROOT / 'profile-supplements.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Reviewed supplements for {len(data)} players.')
