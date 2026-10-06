from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

out = Path(__file__).parent / 'local' / 'assets' / 'teams'
out.mkdir(parents=True, exist_ok=True)
teams = ['ari','atl','bal','buf','car','chi','cin','cle','dal','den','det','gb','hou','ind','jax','kc','lac','lar','lv','mia','min','ne','no','nyg','nyj','phi','pit','sea','sf','tb','ten','wsh']
def download(team):
    target = out / f'{team}.png'
    if target.exists():
        return team
    response = requests.get(f'https://a.espncdn.com/i/teamlogos/nfl/500/{team}.png', timeout=25)
    response.raise_for_status()
    assert response.content.startswith(b'\x89PNG'), team
    target.write_bytes(response.content)
    return team
with ThreadPoolExecutor(max_workers=6) as pool:
    print('Team logos downloaded:', len(list(pool.map(download, teams))))
