from hashlib import sha256
from pathlib import Path
import re
import requests

root=Path(__file__).parent/'local'/'assets'/'fonts'
root.mkdir(parents=True,exist_ok=True)
url='https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600;700&display=swap'
response=requests.get(url,timeout=25)
response.raise_for_status()
css=response.text
for font_url in dict.fromkeys(re.findall(r'url\((https://[^)]+)\)',css)):
    target=root/(sha256(font_url.encode()).hexdigest()[:14]+'.woff2')
    if not target.exists():
        font=requests.get(font_url,timeout=25)
        font.raise_for_status()
        target.write_bytes(font.content)
    css=css.replace(font_url,target.name)
(root/'fonts.css').write_text(css,encoding='utf-8')
for family in ('barlow', 'barlowcondensed'):
    license_file = root / f'{family}-OFL.txt'
    if not license_file.exists():
        license_response = requests.get(f'https://raw.githubusercontent.com/google/fonts/main/ofl/{family}/OFL.txt', timeout=25)
        license_response.raise_for_status()
        license_file.write_text(license_response.text, encoding='utf-8')
print('Downloaded fonts:',len(list(root.glob('*.woff2'))))
