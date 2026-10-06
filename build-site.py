import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).parent
data=json.loads((root/'drafts.json').read_text(encoding='utf-8'))
assert sum(map(len,data.values())) == 2569
template=(root/'site-template.html').read_text(encoding='utf-8')
serialized=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
page=template.replace('__NFL_DRAFT_DATA__',serialized)
assert '__NFL_DRAFT_DATA__' not in page
(root/'local'/'index.html').write_text(page,encoding='utf-8')
shutil.copy2(root/'nfl-drafts-2017-2026.csv',root/'local'/'nfl-drafts-2017-2026.csv')
for asset in ('profile-ui.js', 'profile-ui.css'):
    if (root/asset).exists():
        shutil.copy2(root/asset,root/'local'/asset)
shutil.copy2(root/'measurement-definitions.json', root/'local'/'data'/'measurement-definitions.json')
profiles = sorted((root/'local'/'data'/'profiles').glob('*.json'))
assert len(profiles) == 2569
with ZipFile(root/'local'/'player-profiles-2017-2026.zip', 'w', compression=ZIP_DEFLATED) as archive:
    for profile in profiles:
        archive.write(profile, f'profiles/{profile.name}')
    for name in ('coverage.json', 'measurement-benchmarks.json', 'measurement-definitions.json'):
        archive.write(root/'local'/'data'/name, name)
    archive.writestr('README.txt', 'NFL Draft Archive: 2,569 players, 2017-2026.\nEach filename is draft-year plus overall pick.\nMeasurements preserve source, event, unit and designation. Missing data is not zero.\nCollege statistics retain provider labels and coverage; biography tables may be partial.\nBenchmarks describe this archive: one observation per drafted player, positional samples, minimum 20 for ranking.\nTimed/jump/bench reference groups use official combine results when available. Body sizes use reported measurements.\nNo unpublished private-workout results are inferred. Full source prose is excluded.\n')
print('Built NFL Draft Archive:',len(page.encode('utf-8')),'bytes, 2,569 selections')
