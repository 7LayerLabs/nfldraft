import json
import csv
from hashlib import sha256
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).parent
data=json.loads((root/'drafts.json').read_text(encoding='utf-8'))
assert sum(map(len,data.values())) == 2569
current_teams=json.loads((root/'local'/'data'/'current-teams.json').read_text(encoding='utf-8'))
expected_ids={f'{year}-{row[1]}' for year,rows in data.items() for row in rows}
assert set(current_teams['players']) == expected_ids
assert current_teams['asOf']
template=(root/'site-template.html').read_text(encoding='utf-8')
serialized=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
memberships=json.dumps(current_teams,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
page=template.replace('__NFL_DRAFT_DATA__',serialized).replace('__NFL_CURRENT_TEAMS__',memberships)
for marker,asset in (('__PROFILE_STYLE_VERSION__','profile-ui.css'),('__PROFILE_SCRIPT_VERSION__','profile-ui.js'),('__CAREER_STYLE_VERSION__','career-ui.css'),('__CAREER_SCRIPT_VERSION__','career-ui.js')):
    page=page.replace(marker,sha256((root/asset).read_bytes()).hexdigest()[:12])
assert '__NFL_DRAFT_DATA__' not in page and '__NFL_CURRENT_TEAMS__' not in page and '_VERSION__' not in page
(root/'local'/'index.html').write_text(page,encoding='utf-8')
def membership_label(entry):
    return entry.get('team') or '-- '+(entry.get('statusLabel') or 'Status unconfirmed')

with (root/'nfl-drafts-2017-2026.csv').open(encoding='utf-8-sig',newline='') as source:
    selections=list(csv.reader(source))
with (root/'local'/'nfl-drafts-2017-2026.csv').open('w',encoding='utf-8',newline='') as destination:
    writer=csv.writer(destination)
    writer.writerow(selections[0]+['Current team','Current team/status as of'])
    for row in selections[1:]:
        entry=current_teams['players'][f'{row[0]}-{row[2]}']
        writer.writerow(row+[membership_label(entry),current_teams['asOf']])
for asset in ('profile-ui.js', 'profile-ui.css', 'career-ui.js', 'career-ui.css'):
    if (root/asset).exists():
        shutil.copy2(root/asset,root/'local'/asset)
(root/'local'/'data'/'measurement-definitions.json').write_text(
    (root/'measurement-definitions.json').read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
profiles = sorted((root/'local'/'data'/'profiles').glob('*.json'))
assert len(profiles) == 2569
for file in profiles:
    original=file.read_text(encoding='utf-8')
    profile=json.loads(original)
    profile['currentTeam']={**current_teams['players'][profile['id']], 'asOf':current_teams['asOf']}
    published=json.dumps(profile,ensure_ascii=False,separators=(',',':'))
    if published != original:
        file.write_text(published,encoding='utf-8',newline='\n')
with ZipFile(root/'local'/'player-profiles-2017-2026.zip', 'w', compression=ZIP_DEFLATED) as archive:
    for profile in profiles:
        archive.write(profile, f'profiles/{profile.name}')
    for name in ('coverage.json', 'measurement-benchmarks.json', 'measurement-definitions.json', 'current-teams.json', 'nfl-careers.json'):
        archive.write(root/'local'/'data'/name, name)
    for career_file in sorted((root/'local'/'data'/'careers').glob('*.json')):
        archive.write(career_file, f'careers/{career_file.name}')
    archive.writestr('README.txt', 'NFL Draft Archive: 2,569 players, 2017-2026.\nEach filename is draft-year plus overall pick.\nCurrent team and league status are a dated source snapshot, distinct from drafted team. Current-teams.json preserves membership/status evidence.\nMeasurements preserve source, event, unit and designation. Missing data is not zero.\nCollege statistics retain provider labels and coverage; biography tables may be partial.\nBenchmarks describe this archive: one observation per drafted player, positional samples, minimum 20 for ranking.\nTimed/jump/bench reference groups use official combine results when available. Body sizes use reported measurements.\nNo unpublished private-workout results are inferred. Full source prose is excluded.\nNFL careers: regular season, Year 1 = draft season, one row per season through the in-progress season (nfl-careers.json); careers/ holds position career-arc trends and player grids.\n')
print('Built NFL Draft Archive:',len(page.encode('utf-8')),'bytes, 2,569 selections')
