"""Publish the collected player data as small, addressable local profile files."""
import copy
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
CACHE = Path.home() / '.agent-reach' / 'nfl-player-profiles'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def public_payload(value):
    """Drop private collector file references, including nested college sources."""
    if isinstance(value, dict):
        return {key: public_payload(item) for key, item in value.items() if key != 'rawReference'}
    if isinstance(value, list):
        return [public_payload(item) for item in value]
    return value


def main():
    drafts = read(PROJECT / 'drafts.json')
    workouts = read(CACHE / 'workout-profiles.json')
    college = read(CACHE / 'college-profiles.json')
    supplements = read(PROJECT / 'profile-supplements.json') if (PROJECT / 'profile-supplements.json').exists() else {}
    expected = {f'{year}-{row[1]}' for year, rows in drafts.items() for row in rows}
    assert len(expected) == 2569
    assert expected == set(workouts), 'Workout collection must include every draft pick'
    assert expected == set(college), 'College collection must finish before publication'
    output = PROJECT / 'local' / 'data' / 'profiles'
    output.mkdir(parents=True, exist_ok=True)
    index = {}
    counts = Counter()
    metric_coverage = Counter()
    by_year = {}
    for year, rows in drafts.items():
        year_counts = Counter()
        for row in rows:
            rnd, pick, team, via, name, position, school = row[:7]
            pid = f'{year}-{pick}'
            workout = copy.deepcopy(workouts[pid])
            stats = copy.deepcopy(college[pid])
            extra = supplements.get(pid, {})
            if extra.get('collegeExperience'):
                stats['experience'] = extra['collegeExperience']
                stats['summary'] = extra.get('careerSummary', stats.get('summary'))
                stats['status'] = 'experience-only' if not stats.get('categories') else stats['status']
                stats.setdefault('sources', []).extend(extra.get('collegeSources', []))
            for event in extra.get('publishedWorkouts', []):
                sid = 'published-' + str(len(workout['sources']))
                workout['sources'].append({'id': sid, 'label': event['sourceLabel'], 'url': event['sourceUrl']})
                for metric in event.get('metrics', []):
                    if metric.get('key') and isinstance(metric.get('value'), (int, float)):
                        observation = {k: metric[k] for k in ('value', 'unit', 'designation')}
                        observation.update(event=event['event'], sourceId=sid, date=event.get('date'))
                        workout['measurements'].setdefault(metric['key'], []).append(observation)
            workout['missingMeasurements'] = [k for k in workout.get('missingMeasurements', []) if not workout['measurements'].get(k)]
            workout['availability']['measurementCount'] = len(workout['measurements'])
            # Raw full copyrighted narratives and absolute source-cache paths stay private to the collector.
            workout.get('scouting', {}).pop('rawReference', None)
            workout.get('bio', {}).pop('rawReference', None)
            scouting = workout.get('scouting', {})
            if len((scouting.get('overviewQuote') or '').split()) < 5:
                scouting['overviewQuote'] = None
            if scouting.get('strengthQuote') and scouting.get('weaknessQuote'):
                scouting['overviewQuote'] = None
            scouting['quoteWordCount'] = sum(len((scouting.get(key) or '').split()) for key in ('overviewQuote','strengthQuote','weaknessQuote'))
            metric_coverage.update(workout['measurements'].keys())
            profile = {'id': pid, 'year': int(year), 'round': rnd, 'pick': pick,
                       'team': team, 'via': via, 'name': name, 'position': position,
                       'college': school, 'workouts': workout, 'collegeStats': stats,
                       'careerSummary': stats.get('summary'),
                       'publishedWorkouts': extra.get('publishedWorkouts', []),
                       'privateWorkoutsStatus': 'No private-workout test results in the collected sources.',
                       'collectedAt': datetime.now(timezone.utc).date().isoformat()}
            published = json.dumps(public_payload(profile), ensure_ascii=False, separators=(',', ':'))
            assert '.agent-reach' not in published and 'rawReference' not in published
            (output / f'{pid}.json').write_text(published, encoding='utf-8')
            flags = {'profiles': True, 'measurements': bool(workout['measurements']),
                     'scouting': workout['scouting']['status'] == 'available',
                     'collegeStatistics': bool(stats.get('categories')),
                     'collegeExperience': bool(stats.get('experience')),
                     'publishedWorkoutReports': bool(profile['publishedWorkouts'])}
            for flag, value in flags.items():
                if value:
                    counts[flag] += 1
                    year_counts[flag] += 1
            index[pid] = {'name': name, 'position': position, 'year': int(year), 'pick': pick,
                          'availability': flags, 'collegeStatus': stats['status']}
        by_year[year] = dict(year_counts)
    coverage = {'collectedAt': datetime.now(timezone.utc).isoformat(), 'counts': dict(counts), 'years': by_year,
                'metrics': dict(metric_coverage),
                'collegeStatuses': dict(Counter(p['collegeStatus'] for p in index.values())),
                'notes': ['Every drafted player has an addressable profile. Source coverage differs by player.',
                          'Combine and pro-day observations retain source, event, units and timing designation.',
                          'Mixed-source event types stay unspecified. There was no in-person 2021 combine.',
                          'College figures come from ESPN college records and separately attributed draft-era college biographies. Biography-only tables are partial.',
                          'Private-workout measurements are displayed only when publicly reported. Missing results are never zero.',
                          'Scouting excerpts are short pre-draft source quotations; grades from different years are not normalized.']}
    (PROJECT / 'local' / 'data' / 'profile-index.json').write_text(json.dumps({'coverage': coverage, 'profiles': index}, ensure_ascii=False), encoding='utf-8')
    (PROJECT / 'local' / 'data' / 'coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    (PROJECT / 'profile-coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps(coverage, indent=2))


if __name__ == '__main__':
    main()
