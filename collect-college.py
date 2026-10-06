"""Collect attributed college careers for every draft row; cache failures and successes.

Run from any directory. Uses public ESPN athlete statistics, with historical game
box exports only for identity resolution. Box-score aggregates are never presented
as complete seasons. No credentials or third-party dependencies are required.
"""
import concurrent.futures as futures
import csv
import gzip
import html
import io
import json
import pathlib
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.parse
from collections import Counter, defaultdict

PROJECT = pathlib.Path(__file__).resolve().parent
ROOT = pathlib.Path.home() / '.agent-reach' / 'nfl-player-profiles'
CACHE = ROOT / 'college'
RAW = ROOT / 'raw'
CACHE.mkdir(parents=True, exist_ok=True)
API = 'https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/{}/stats'
BOX = 'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_player_box/player_box_{}.csv.gz'
LOCK = threading.Lock()


def normalized(value):
    value = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode().lower()
    value = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', value)
    return re.sub(r'[^a-z0-9]', '', value)


SCHOOL_ALIASES = {
    'miamifl': 'miami', 'miamiflorida': 'miami', 'miamioh': 'miamiohio',
    'southerncalifornia': 'usc', 'california': 'cal', 'pittsburgh': 'pitt',
    'mississippi': 'olemiss', 'connecticut': 'uconn', 'massachusetts': 'umass',
    'brighamyoung': 'byu', 'centralflorida': 'ucf', 'texaschristian': 'tcu',
    'southernmethodist': 'smu', 'louisianasoutheastern': 'southeasternlouisiana',
    'louisianalafayette': 'louisiana', 'louisianastate': 'lsu',
    'northcarolinastate': 'ncstate', 'californiadavis': 'ucdavis',
    'utmartin': 'tennesseemartin', 'texaselpaso': 'utep', 'texassanantonio': 'utsa',
    'sanantonio': 'utsa', 'southernmississippi': 'southernmiss',
    'arkansaspinebluff': 'arkansaspinebluff', 'stfrancispa': 'saintfrancis',
    'stfrancis': 'saintfrancis', 'appstate': 'appalachianstate',
    'bowlinggreenstate': 'bowlinggreen', 'northerniowa': 'northerniowa',
    'mcneesestate': 'mcneese', 'nichollsstate': 'nicholls',
    'selouisiana': 'southeasternlouisiana', 'prairieviewam': 'prairieview',
    'pvam': 'prairieview', 'samhoustonstate': 'samhouston',
}
NAME_ALIASES = {
    'nathangerry': ['Nate Gerry'], 'matthewdayes': ['Matt Dayes'],
    'shaquilleleonard': ['Darius Leonard'], 'gregoryrousseau': ['Greg Rousseau'],
    'patricksurtain': ['Pat Surtain', 'Patrick Surtain'],
    'dwayneeskridge': ['Dee Eskridge', 'DWayne Eskridge'],
    'brodricmartin': ['Brodrick Martin'],
}

# Numeric facts transcribed from each player's cached, official NFL draft-time
# college biography. Explicit dates remain dates; undated class-year statements
# remain labelled seasons. These are partial source reports, never inferred totals.
BIO_FALLBACK = {
    '2017-45': [('receiving', 2014, None, dict(receptions=2, receivingYards=85)),
                ('receiving', None, 'Next college season', dict(receptions=70, receivingYards=803, receivingTouchdowns=10)),
                ('receiving', 2016, None, dict(receptions=57, receivingYards=867, receivingTouchdowns=16))],
    '2017-59': [('defensive', 2015, None, dict(tacklesForLoss=9.5, sacks=6.5)),
                ('defensive', None, 'Final college season', dict(tacklesForLoss=21.5, sacks=11))],
    '2017-83': [('defensive', 2013, None, dict(totalTackles=13, tacklesForLoss=3, sacks=2.5)),
                ('defensive', None, 'Junior season', dict(totalTackles=52, tacklesForLoss=15.5, sacks=8)),
                ('defensive', 2016, None, dict(totalTackles=58, tacklesForLoss=19.5, sacks=14))],
    '2017-121': [('rushing', 2016, None, dict(rushingYards=1420, rushingTouchdowns=10, gamesPlayed=9))],
    '2017-174': [('receiving', 2014, None, dict(receptions=32, receivingYards=348, receivingTouchdowns=2, gamesStarted=7)),
                 ('receiving', 2016, None, dict(receptions=56, receivingYards=776, receivingTouchdowns=10))],
    '2017-181': [('defensive', 2015, None, dict(totalTackles=52, tacklesForLoss=17.5, sacks=12)),
                 ('defensive', 2016, None, dict(totalTackles=67, tacklesForLoss=20, sacks=13.5))],
    '2017-196': [('defensive', 2015, None, dict(totalTackles=54, tacklesForLoss=8.5, sacks=5))],
    '2017-203': [('rushing', 2014, None, dict(rushingAttempts=234, rushingYards=1534, rushingTouchdowns=20)),
                 ('rushing', 2015, None, dict(rushingAttempts=222, rushingYards=1346, rushingTouchdowns=16)),
                 ('rushing', 2016, None, dict(rushingAttempts=183, rushingYards=1156, rushingTouchdowns=16)),
                 ('receiving', 2016, None, dict(receptions=20, receivingYards=190, receivingTouchdowns=2))],
    '2018-36': [('defensive', 2014, None, dict(totalTackles=86, tacklesForLoss=14, sacks=5, fumblesForced=2)),
                ('defensive', 2016, None, dict(totalTackles=124, tacklesForLoss=14.5, sacks=3.5, interceptions=2, passesBrokenUp=3, fumblesForced=4))],
    '2018-57': [('defensive', 2016, None, dict(totalTackles=56, tacklesForLoss=24.5, sacks=13, fumblesForced=3, gamesStarted=13)),
                ('defensive', None, 'Senior season', dict(totalTackles=60, tacklesForLoss=19, sacks=6, passesBrokenUp=6, kicksBlocked=4))],
    '2018-72': [('defensive', 2015, None, dict(totalTackles=69, tacklesForLoss=5, sacks=3, gamesPlayed=12, gamesStarted=12)),
                ('defensive', 2017, None, dict(totalTackles=38, tacklesForLoss=12.5, sacks=4))],
    '2018-108': [('passing', 2015, None, dict(completionPct=61.6, passingYards=3598, passingTouchdowns=19, interceptions=15)),
                 ('passing', 2016, None, dict(completionPct=63, passingYards=3022, passingTouchdowns=24, interceptions=8)),
                 ('passing', 2017, None, dict(completionPct=64.9, passingYards=3737, passingTouchdowns=28, interceptions=12))],
    '2018-135': [('defensive', 2015, None, dict(totalTackles=32, tacklesForLoss=8.5, sacks=6, gamesStarted=4, gamesPlayed=11)),
                 ('defensive', 2016, None, dict(totalTackles=32, tacklesForLoss=14.5, sacks=8, fumblesForced=4)),
                 ('defensive', 2017, None, dict(totalTackles=55, tacklesForLoss=13.5, sacks=3.5, gamesStarted=10, gamesPlayed=11))],
    '2018-145': [('defensive', 2016, None, dict(totalTackles=25, tacklesForLoss=7.5, sacks=5, passesBrokenUp=5, gamesStarted=9, gamesPlayed=10)),
                 ('defensive', None, 'Senior season', dict(totalTackles=56, tacklesForLoss=6.5, sacks=5.5, interceptions=1, passesBrokenUp=4, gamesStarted=11))],
    '2018-151': [('defensive', 2016, None, dict(totalTackles=55, tacklesForLoss=5.5, interceptions=2, passesBrokenUp=13, gamesStarted=11, gamesPlayed=12)),
                 ('defensive', 2017, None, dict(totalTackles=57, tacklesForLoss=4.5, interceptions=2, passesBrokenUp=12))],
    '2018-154': [('defensive', 2015, None, dict(totalTackles=40, interceptions=1, passesBrokenUp=3, gamesStarted=1, gamesPlayed=15)),
                 ('defensive', 2016, None, dict(totalTackles=80, tacklesForLoss=11.5, interceptions=1, passesBrokenUp=4)),
                 ('defensive', None, 'Senior season', dict(totalTackles=39, interceptions=1, passesBrokenUp=11))],
    '2018-200': [('defensive', 2015, None, dict(totalTackles=8, gamesPlayed=3)),
                 ('defensive', None, 'Senior season', dict(totalTackles=50, tacklesForLoss=9, sacks=3, gamesPlayed=10))],
    '2018-204': [('rushing', 2016, None, dict(rushingAttempts=168, rushingYards=1214, rushingTouchdowns=18)),
                 ('rushing', None, 'Final college season', dict(rushingAttempts=212, rushingYards=1638, rushingTouchdowns=17)),
                 ('receiving', None, 'Final college season', dict(receptions=21, receivingYards=225, receivingTouchdowns=3))],
    '2018-248': [('defensive', 2016, None, dict(totalTackles=50, tacklesForLoss=13, sacks=4, gamesPlayed=11, gamesStarted=10)),
                 ('defensive', None, 'Senior season', dict(totalTackles=53, tacklesForLoss=13.5, sacks=6, interceptions=1, passesBrokenUp=3, fumblesForced=3))],
    '2019-84': [('defensive', 2015, None, dict(totalTackles=27, tacklesForLoss=4.5, sacks=2.5, gamesPlayed=13)),
                ('defensive', 2017, None, dict(totalTackles=57, tacklesForLoss=12, sacks=7.5, passesBrokenUp=3, gamesPlayed=12, gamesStarted=12))],
    '2019-98': [('defensive', 2015, None, dict(totalTackles=31, tacklesForLoss=3, gamesStarted=3, gamesPlayed=11)),
                ('defensive', 2018, None, dict(totalTackles=111, tacklesForLoss=9.5, interceptions=2))],
    '2019-135': [('defensive', 2017, None, dict(totalTackles=73, tacklesForLoss=23, sacks=6.5)),
                 ('defensive', 2018, None, dict(totalTackles=67, tacklesForLoss=16.5, sacks=3, fumblesForced=2))],
    '2019-164': [('defensive', 2016, None, dict(totalTackles=68, tacklesForLoss=13, sacks=6, fumblesForced=5)),
                 ('defensive', 2017, None, dict(totalTackles=41, tacklesForLoss=8.5, gamesPlayed=5)),
                 ('defensive', 2018, None, dict(totalTackles=106, tacklesForLoss=12.5, sacks=5))],
    '2019-180': [('defensive', 2017, None, dict(totalTackles=54, passesBrokenUp=7, gamesStarted=12)),
                 ('defensive', 2018, None, dict(totalTackles=50, tacklesForLoss=3, interceptions=3, passesBrokenUp=4, fumblesForced=2, kicksBlocked=3))],
    '2019-225': [('defensive', 2016, None, dict(totalTackles=26, tacklesForLoss=6.5, sacks=2, gamesPlayed=12)),
                 ('defensive', 2017, None, dict(totalTackles=40, tacklesForLoss=15.5, sacks=6.5, fumblesForced=4, gamesStarted=12)),
                 ('defensive', None, 'Final college season', dict(totalTackles=50, tacklesForLoss=19, sacks=10.5, gamesPlayed=12, gamesStarted=11))],
    '2019-238': [('defensive', None, 'Senior season', dict(totalTackles=55, tacklesForLoss=8, interceptions=3, passesBrokenUp=9)),
                 ('receiving', 2016, None, dict(receptions=22, receivingYards=240, receivingTouchdowns=2, gamesPlayed=11, gamesStarted=11))],
    '2019-244': [('defensive', 2017, None, dict(totalTackles=80, tacklesForLoss=16, sacks=6, passesBrokenUp=4, fumblesForced=2)),
                 ('defensive', 2018, None, dict(totalTackles=60, tacklesForLoss=16, sacks=7, passesBrokenUp=3)),
                 ('receiving', 2017, None, dict(receptions=7, receivingYards=156, receivingTouchdowns=2))],
    '2020-37': [('defensive', 2017, None, dict(totalTackles=87, tacklesForLoss=4.5, interceptions=1, passesBrokenUp=6, gamesStarted=10)),
                ('defensive', 2018, None, dict(totalTackles=76, interceptions=3, passesBrokenUp=10, fumblesForced=2)),
                ('defensive', None, 'Senior season', dict(totalTackles=31, tacklesForLoss=1, interceptions=2, passesBrokenUp=4, gamesStarted=7))],
    '2020-64': [('defensive', 2016, None, dict(totalTackles=51, interceptions=3, passesBrokenUp=2, gamesStarted=6, gamesPlayed=8)),
                ('defensive', 2019, None, dict(totalTackles=71, tacklesForLoss=2.5, interceptions=4, passesBrokenUp=3))],
    '2020-254': [('defensive', 2018, None, dict(totalTackles=48, tacklesForLoss=12, sacks=7.5, gamesStarted=7, gamesPlayed=15)),
                 ('defensive', 2019, None, dict(totalTackles=48, tacklesForLoss=19, sacks=13.5, passesBrokenUp=5, gamesStarted=15))],
    '2021-116': [('defensive', None, 'Sophomore season', dict(totalTackles=19, tacklesForLoss=10.5, sacks=7.5, gamesPlayed=13)),
                 ('defensive', None, 'Junior season', dict(totalTackles=63, tacklesForLoss=21.5, sacks=14, fumblesForced=5, gamesPlayed=15))],
    '2021-130': [('defensive', 2018, None, dict(totalTackles=25, tacklesForLoss=3, interceptions=4, passesBrokenUp=6, gamesPlayed=11, gamesStarted=8)),
                 ('defensive', 2020, None, dict(totalTackles=27, passesBrokenUp=3, gamesStarted=7))],
    '2021-168': [('receiving', None, 'Junior season', dict(receptions=40, receivingYards=894, receivingTouchdowns=15, gamesPlayed=13, gamesStarted=12))],
    '2021-229': [('receiving', 2017, None, dict(receptions=1, receivingYards=6, gamesPlayed=7)),
                 ('receiving', 2019, None, dict(receptions=78, receivingYards=1319, receivingTouchdowns=19, gamesPlayed=11, gamesStarted=11))],
    '2021-252': [('defensive', 2017, None, dict(totalTackles=44, tacklesForLoss=9, sacks=6, fumblesForced=5, gamesPlayed=7, gamesStarted=5)),
                 ('defensive', 2019, None, dict(totalTackles=69, tacklesForLoss=20.5, sacks=14, fumblesForced=7, passesBrokenUp=5, gamesPlayed=11, gamesStarted=10))],
    '2022-58': [('defensive', 2019, None, dict(totalTackles=54, tacklesForLoss=11.5, sacks=6.5, interceptions=1, passesBrokenUp=5)),
                ('defensive', 2021, None, dict(totalTackles=147, tacklesForLoss=14, sacks=2, interceptions=2, passesBrokenUp=7, gamesStarted=15))],
    '2022-135': [('defensive', 2021, None, dict(totalTackles=31, interceptions=3, passesBrokenUp=6, gamesStarted=9))],
    '2022-157': [('defensive', 2018, None, dict(totalTackles=44, tacklesForLoss=1.5, interceptions=3, passesBrokenUp=8, fumblesForced=2)),
                 ('defensive', 2019, None, dict(totalTackles=23, tacklesForLoss=2.5, interceptions=3, passesBrokenUp=8, fumblesForced=2)),
                 ('defensive', 2021, 'Spring 2021', dict(totalTackles=46, tacklesForLoss=3, interceptions=1, passesBrokenUp=6, fumblesForced=2, gamesStarted=10)),
                 ('defensive', 2021, 'Fall 2021', dict(totalTackles=50, tacklesForLoss=2, interceptions=3, passesBrokenUp=5, kicksBlocked=1, gamesStarted=12))],
    '2022-159': [('defensive', 2019, None, dict(totalTackles=18, gamesStarted=7, gamesPlayed=11)),
                 ('defensive', None, '2020–21 fall/spring combined', dict(totalTackles=27, tacklesForLoss=6, sacks=1.5, kicksBlocked=1, gamesPlayed=10)),
                 ('defensive', 2021, 'Fall 2021', dict(totalTackles=43, tacklesForLoss=6.5, sacks=1.5, passesBrokenUp=2, kicksBlocked=3))],
    '2022-185': [('defensive', 2019, None, dict(totalTackles=31, interceptions=1, passesBrokenUp=5, gamesStarted=7, gamesPlayed=10)),
                 ('defensive', 2021, 'Spring 2021', dict(totalTackles=18, interceptions=1, passesBrokenUp=4, gamesStarted=4)),
                 ('defensive', None, 'Final fall season', dict(totalTackles=39, interceptions=7, passesBrokenUp=18, gamesPlayed=13, gamesStarted=13))],
    '2022-197': [('defensive', 2018, None, dict(totalTackles=42, tacklesForLoss=1.5, interceptions=1, passesBrokenUp=5, gamesStarted=11, gamesPlayed=13)),
                 ('defensive', 2021, None, dict(totalTackles=46, tacklesForLoss=3, passesBrokenUp=7, gamesStarted=11))],
    '2022-200': [('defensive', 2017, None, dict(totalTackles=24, tacklesForLoss=6, sacks=1, interceptions=1, gamesStarted=3, gamesPlayed=12)),
                 ('defensive', 2018, None, dict(totalTackles=50, tacklesForLoss=13, sacks=6, gamesPlayed=13)),
                 ('defensive', None, 'Senior season', dict(totalTackles=61, tacklesForLoss=18, sacks=6.5, gamesStarted=13))],
    '2022-233': [('receiving', 2018, None, dict(receptions=7, receivingYards=122, receivingTouchdowns=2)),
                 ('receiving', 2019, None, dict(receptions=25, receivingYards=515, receivingTouchdowns=8, gamesStarted=11, gamesPlayed=14)),
                 ('receiving', 2021, None, dict(receptions=25, receivingYards=303, receivingTouchdowns=4, gamesStarted=5))],
    '2022-235': [('defensive', 2018, None, dict(totalTackles=5, gamesPlayed=11)),
                 ('defensive', 2021, None, dict(totalTackles=77, tacklesForLoss=24.5, sacks=16.5, passesBrokenUp=3, fumblesForced=2, gamesStarted=15))],
    '2022-244': [('defensive', 2021, None, dict(totalTackles=37, interceptions=1, passesBrokenUp=15, kicksBlocked=1, gamesStarted=14))],
    '2023-76': [('defensive', 2018, None, dict(totalTackles=6, gamesPlayed=5)),
                ('defensive', 2019, None, dict(totalTackles=18, interceptions=1, gamesPlayed=11, gamesStarted=2)),
                ('defensive', 2022, None, dict(totalTackles=76, tacklesForLoss=6.5, interceptions=2, passesBrokenUp=4, kicksBlocked=1, gamesStarted=13))],
    '2023-77': [('defensive', None, 'First Tennessee season', dict(tacklesForLoss=11.5, sacks=5.5, gamesPlayed=11, gamesStarted=8)),
                ('defensive', None, 'Senior Tennessee season', dict(totalTackles=37, tacklesForLoss=12, sacks=7))],
    '2023-96': [('defensive', 2021, None, dict(totalTackles=31, tacklesForLoss=4.5, sacks=2.5, gamesPlayed=14, gamesStarted=1)),
                ('defensive', None, 'Senior season at Western Kentucky', dict(totalTackles=31, sacks=1.5, passesBrokenUp=2, gamesPlayed=14, gamesStarted=14))],
    '2023-166': [('defensive', 2020, None, dict(totalTackles=28, tacklesForLoss=8.5, sacks=6, interceptions=1, gamesStarted=10)),
                 ('defensive', 2021, None, dict(totalTackles=26, tacklesForLoss=12.5, sacks=9.5, passesBrokenUp=2, fumblesForced=2, gamesStarted=12)),
                 ('defensive', 2022, None, dict(totalTackles=25, tacklesForLoss=6.5, sacks=5, fumblesForced=3, gamesStarted=11))],
    '2023-218': [('defensive', 2018, None, dict(totalTackles=24, tacklesForLoss=2, gamesPlayed=12)),
                 ('defensive', 2021, 'Spring 2021', dict(totalTackles=11, tacklesForLoss=2, gamesPlayed=4)),
                 ('defensive', 2021, 'Fall 2021', dict(totalTackles=25, tacklesForLoss=6, sacks=4, gamesPlayed=12, gamesStarted=10)),
                 ('defensive', 2022, None, dict(totalTackles=34, tacklesForLoss=5.5, sacks=1.5, kicksBlocked=1, gamesPlayed=11, gamesStarted=10))],
    '2023-223': [('punting', 2020, None, dict(punts=17, puntYards=717, grossAvgPuntYards=42.2, puntsInside20=5, touchbacks=1)),
                 ('punting', 2021, None, dict(punts=42, puntYards=1785, grossAvgPuntYards=42.5, puntsInside20=25, touchbacks=5)),
                 ('punting', None, 'Senior season', dict(punts=77, puntYards=3518, grossAvgPuntYards=45.7, puntsInside20=39, touchbacks=13))],
    '2023-240': [('defensive', 2021, None, dict(totalTackles=54, tacklesForLoss=12, sacks=5, gamesStarted=14)),
                 ('defensive', 2022, None, dict(totalTackles=20, tacklesForLoss=8.5, sacks=5, gamesPlayed=4, gamesStarted=3))],
    '2024-94': [('defensive', 2022, None, dict(totalTackles=87, tacklesForLoss=11.5, sacks=7, fumblesForced=3, passesBrokenUp=2, gamesStarted=11)),
                ('defensive', 2023, None, dict(totalTackles=46, tacklesForLoss=9, sacks=6.5, interceptions=1, passesBrokenUp=2, fumblesForced=2, gamesStarted=10))],
    '2024-199': [('defensive', 2022, None, dict(totalTackles=32, tacklesForLoss=5, passesBrokenUp=2, fumblesForced=2, gamesPlayed=10)),
                 ('defensive', 2023, None, dict(totalTackles=43, tacklesForLoss=6.5, sacks=3.5, gamesPlayed=11))],
    '2024-227': [('defensive', 2022, None, dict(totalTackles=44, tacklesForLoss=4, sacks=1, interceptions=3, passesBrokenUp=6, fumblesForced=4, gamesStarted=6)),
                 ('defensive', 2023, None, dict(totalTackles=58, tacklesForLoss=4, interceptions=1, passesBrokenUp=6, gamesStarted=13))],
}

BIO_LABELS = {
    'totalTackles': 'TOT', 'tacklesForLoss': 'TFL', 'sacks': 'SACK', 'interceptions': 'INT',
    'passesBrokenUp': 'PBU', 'fumblesForced': 'FF', 'kicksBlocked': 'BLK',
    'gamesPlayed': 'GP', 'gamesStarted': 'GS', 'receptions': 'REC',
    'receivingYards': 'YDS', 'receivingTouchdowns': 'TD', 'rushingAttempts': 'CAR',
    'rushingYards': 'YDS', 'rushingTouchdowns': 'TD', 'passingYards': 'YDS',
    'passingTouchdowns': 'TD', 'completionPct': 'CMP%', 'punts': 'PUNTS',
    'puntYards': 'YDS', 'grossAvgPuntYards': 'AVG', 'puntsInside20': 'IN20', 'touchbacks': 'TB',
    'soloTackles': 'SOLO', 'assistTackles': 'AST', 'fumblesRecovered': 'FR', 'hurries': 'QBH',
    'passesDefended': 'PD',
}

SCHOOL_FALLBACK = {
    '2017-125': {
        'label': 'Eastern Washington official college biography', 'rawFile': 'school-ebukam.json',
        'url': 'https://goeags.com/sports/football/roster/samson-ebukam/4555',
        'facts': [('defensive', 2013, None, dict(totalTackles=28, tacklesForLoss=4, sacks=3, interceptions=1, passesBrokenUp=2, gamesPlayed=15)),
                  ('defensive', 2014, None, dict(totalTackles=45, tacklesForLoss=15, sacks=7.5, gamesPlayed=13, gamesStarted=13)),
                  ('defensive', 2015, None, dict(totalTackles=44, tacklesForLoss=10, sacks=4, passesBrokenUp=2, gamesPlayed=11, gamesStarted=11)),
                  ('defensive', 2016, None, dict(totalTackles=71, tacklesForLoss=15, sacks=9.5, interceptions=1, passesBrokenUp=2, fumblesForced=2, fumblesRecovered=3, hurries=8, gamesPlayed=14, gamesStarted=14))],
        'career': {'defensive': dict(totalTackles=188, tacklesForLoss=44, sacks=24, interceptions=2, passesBrokenUp=6, fumblesForced=2, fumblesRecovered=4, gamesPlayed=53, gamesStarted=38)},
    },
    '2017-144': {
        'label': 'Indianapolis Colts official college career biography', 'rawFile': 'school-stewart.json',
        'url': 'https://www.colts.com/team/players-roster/grover-stewart/career',
        'facts': [('defensive', 2016, None, dict(totalTackles=37, soloTackles=26, tacklesForLoss=12, sacks=7.5, passesDefended=2, fumblesForced=1, gamesPlayed=9, gamesStarted=9))],
        'career': {'defensive': dict(totalTackles=141, soloTackles=90, tacklesForLoss=35.5, sacks=27, passesDefended=5, fumblesForced=2, gamesPlayed=39, gamesStarted=19)},
    },
    '2017-192': {
        'label': 'West Georgia official college biography', 'rawFile': 'school-armah.json',
        'url': 'https://uwgathletics.com/sports/football/roster/alex-armah/3229',
        'facts': [('receiving', 2016, None, dict(receptions=8, receivingYards=144, receivingTouchdowns=1, gamesPlayed=11, gamesStarted=11)),
                  ('defensive', 2013, None, dict(totalTackles=47, gamesPlayed=11, gamesStarted=4)),
                  ('defensive', 2014, None, dict(totalTackles=64, soloTackles=26, sacks=6, hurries=6, passesBrokenUp=3, gamesPlayed=15)),
                  ('defensive', 2015, None, dict(totalTackles=52, tacklesForLoss=14.5, sacks=9, fumblesForced=2, gamesPlayed=14, gamesStarted=14)),
                  ('defensive', 2016, None, dict(totalTackles=25, soloTackles=12, tacklesForLoss=5.5, sacks=0.5, fumblesForced=1, passesBrokenUp=1, gamesPlayed=11, gamesStarted=11))],
    },
    '2017-226': {
        'label': 'East Central official 2016 cumulative statistics', 'rawFile': 'school-moore.json',
        'url': 'https://ecutigers.com/sports/football/stats/2016',
        'facts': [('receiving', 2016, None, dict(receptions=57, receivingYards=878, receivingTouchdowns=10, gamesPlayed=11)),
                  ('rushing', 2016, None, dict(rushingAttempts=6, rushingYards=74, rushingTouchdowns=1, gamesPlayed=11))],
    },
    '2018-238': {
        'label': 'Miami Dolphins official biography: college section', 'rawFile': 'school-sieler-dolphins.json',
        'url': 'https://media.miamidolphins.com/wp-content/uploads/Sieler-Zach-87.pdf',
        'facts': [('defensive', 2015, None, dict(totalTackles=17, soloTackles=8, sacks=6.5, gamesPlayed=11)),
                  ('defensive', 2016, None, dict(totalTackles=80, soloTackles=37, sacks=19.5, passesDefended=1, fumblesForced=5, fumblesRecovered=2, kicksBlocked=1, gamesPlayed=15)),
                  ('defensive', 2017, None, dict(totalTackles=79, soloTackles=32, sacks=7, passesDefended=2, fumblesForced=2, fumblesRecovered=2, kicksBlocked=1, gamesPlayed=13))],
        'career': {'defensive': dict(totalTackles=176, soloTackles=77, sacks=33, passesDefended=3, fumblesForced=7, fumblesRecovered=4, kicksBlocked=2, gamesPlayed=39, gamesStarted=28)},
    },
    '2023-211': {
        'label': 'Wagner official final-season and career release', 'rawFile': 'school-leo.json',
        'url': 'https://wagnerathletics.com/news/2022/11/23/football-titus-leo-and-naiem-simmons-earn-all-nec-honors.aspx',
        'facts': [('defensive', 2022, None, dict(totalTackles=65, sacks=3))],
        'career': {'defensive': dict(totalTackles=234, tacklesForLoss=41, sacks=13, fumblesForced=6)},
    },
    '2024-232': {
        'label': 'Texas A&M–Commerce official 2023 cumulative statistics', 'rawFile': 'school-rodriguez.json',
        'url': 'https://lionathletics.com/sports/football/stats/2023',
        'facts': [('defensive', 2023, None, dict(totalTackles=56, soloTackles=20, assistTackles=36, tacklesForLoss=7.5, sacks=5.5, hurries=1, fumblesRecovered=2, fumblesForced=1, gamesPlayed=10))],
    },
}

OL_EXPERIENCE = {
    '2017-20': {'url': 'https://www.denverbroncos.com/team/players-roster/garett-bolles/career',
                'label': 'Denver Broncos official college biography',
                'entries': [{'year': 2016, 'team': 'Utah', 'games': 13, 'starts': 13, 'snaps': 891}]},
    '2017-32': {'url': 'https://uwbadgers.com/sports/football/roster/ryan-ramczyk/4069',
                'label': 'Wisconsin official college biography',
                'entries': [{'year': 2013, 'team': 'UW–Stevens Point', 'games': 10},
                            {'year': 2016, 'team': 'Wisconsin', 'games': 14, 'starts': 14, 'sacksAllowed': 1,
                             'pressuresAllowed': 8, 'metricAttribution': 'Pro Football Focus, as reported by Wisconsin'}]},
    '2018-9': {'url': 'https://www.denverbroncos.com/team/players-roster/mike-mcglinchey/career',
               'label': 'Denver Broncos official college biography',
               'entries': [{'year': None, 'seasonLabel': 'College career', 'team': 'Notre Dame', 'games': 51, 'starts': 39},
                           {'year': 2014, 'team': 'Notre Dame', 'games': 13, 'starts': 1},
                           {'year': 2015, 'team': 'Notre Dame', 'games': 13, 'starts': 13},
                           {'year': 2016, 'team': 'Notre Dame', 'games': 12, 'starts': 12},
                           {'year': 2017, 'team': 'Notre Dame', 'games': 13, 'starts': 13}]},
    '2020-10': {'entries': [{'year': None, 'seasonLabel': 'First college season', 'team': 'Alabama', 'games': 11, 'starts': 1},
                           {'year': 2018, 'team': 'Alabama', 'starts': 15},
                           {'year': 2019, 'team': 'Alabama', 'starts': 13}]},
    '2020-13': {'entries': [{'year': None, 'seasonLabel': 'True freshman season', 'team': 'Iowa', 'games': 10, 'starts': 8},
                           {'year': 2018, 'team': 'Iowa', 'starts': 12},
                           {'year': 2019, 'team': 'Iowa', 'games': 13}]},
    '2021-7': {'entries': [{'year': None, 'seasonLabel': 'True freshman season', 'team': 'Oregon', 'starts': 7},
                          {'year': 2019, 'team': 'Oregon', 'starts': 13}]},
    '2019-78': {'entries': [{'year': None, 'seasonLabel': 'Season after redshirt year', 'team': 'Wisconsin', 'starts': 13},
                           {'year': None, 'seasonLabel': 'Sophomore season', 'team': 'Wisconsin', 'starts': 14},
                           {'year': 2017, 'team': 'Wisconsin', 'starts': 14},
                           {'year': None, 'seasonLabel': 'Senior season', 'team': 'Wisconsin', 'starts': 13}]},
    '2022-199': {'entries': [{'year': None, 'seasonLabel': 'Freshman season', 'team': 'Georgia', 'games': 11, 'starts': 7},
                            {'year': 2019, 'team': 'Georgia', 'games': 14, 'starts': 11},
                            {'year': 2020, 'team': 'Tennessee', 'starts': 7},
                            {'year': 2021, 'team': 'Tennessee', 'starts': 10}]},
}


def player_names(name):
    return [name, *NAME_ALIASES.get(normalized(name), [])]


def matching_bios(player, nfl_bios):
    candidates = nfl_bios.get((player['year'], normalized(player['name'])), [])
    person_id = player.get('nflPersonId')
    exact = nfl_bios.get(('person', person_id), []) if person_id else []
    if exact:
        return exact
    expected = school_key(player['college'])
    return [bio for bio in candidates if any(school_key(school) == expected for school in (bio.get('person') or {}).get('collegeNames') or [])]


def school_key(value):
    value = normalized(value)
    return SCHOOL_ALIASES.get(value, value)


def fetch(url, target):
    if target.exists():
        cached = json.loads(target.read_text(encoding='utf-8'))
        if cached.get('url') == url:
            return cached
    result = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'NFLDraftArchive/1.0 research', 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=25) as response:
                data = json.load(response)
            result = {'url': url, 'fetchedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'status': 'ok', 'data': data}
            break
        except urllib.error.HTTPError as exc:
            result = {'url': url, 'status': 'unavailable', 'httpStatus': exc.code}
            if exc.code in (400, 401, 403, 404):
                break
        except Exception as exc:
            result = {'url': url, 'status': 'error', 'error': str(exc)}
        time.sleep(0.5 * (2 ** attempt))
    target.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    return result


def athlete(aid):
    # Reuse feasibility samples, wrapping them in the same provenance envelope.
    target = CACHE / f'{aid}.json'
    sample = ROOT / f'college-{aid}.json'
    if not target.exists() and sample.exists():
        target.write_text(json.dumps({'url': API.format(aid), 'status': 'ok', 'data': json.loads(sample.read_text())}), encoding='utf-8')
    return fetch(API.format(aid), target)


def box_index(year):
    target = ROOT / f'player_box_{year}.csv.gz'
    try:
        if not target.exists():
            with urllib.request.urlopen(BOX.format(year), timeout=40) as response:
                target.write_bytes(response.read())
        index = defaultdict(set)
        reader = csv.DictReader(io.StringIO(gzip.decompress(target.read_bytes()).decode('utf-8-sig')))
        for row in reader:
            aid = row.get('athlete_id', '')
            if aid.isdigit():
                index[normalized(row.get('athlete_name', ''))].add(aid)
        return year, index
    except Exception as exc:
        print(f'Box identity index {year}: {exc}', flush=True)
        return year, {}


def identity_candidates(player, combined, boxes):
    ids = []
    rows = [row for name in player_names(player['name']) for row in combined.get((player['year'], normalized(name)), [])]
    for row in rows:
        value = row.get('athlete_id')
        if value:
            try:
                aid = str(int(float(value)))
                if aid not in ids:
                    ids.append(aid)
            except ValueError:
                pass
    # Historical names can have different NFL and college identifiers. The game
    # exports give college IDs, which are then validated against final school.
    for year in range(player['year'] - 1, max(2012, player['year'] - 8), -1):
        possible = set().union(*(boxes.get(year, {}).get(normalized(name), set()) for name in player_names(player['name'])))
        for aid in sorted(possible):
            if aid not in ids:
                ids.append(aid)
    return ids


def searched_ids(player):
    query = re.sub(r'\b(Jr\.?|Sr\.?|II|III|IV)\b', '', player['name']).strip()
    url = 'https://site.web.api.espn.com/apis/search/v2?region=us&lang=en&limit=30&type=player&query=' + urllib.parse.quote(query)
    raw = fetch(url, CACHE / f"search-{player['id']}.json")
    found = []
    for group in raw.get('data', {}).get('results', []):
        for item in group.get('contents', []):
            if item.get('sport') != 'football' or normalized(item.get('displayName')) not in [normalized(name) for name in player_names(player['name'])]:
                continue
            match = re.search(r'~a:(\d+)', item.get('uid', ''))
            if match:
                found.append((item.get('defaultLeagueSlug') != 'college-football', match[1]))
    return list(dict.fromkeys(aid for _, aid in sorted(found)))


def college_experience(player, nfl_bios):
    """Extract numeric facts from explicitly year-labelled college bio entries.

    Preserve individual reported years rather than guessing complete career totals.
    No source prose is reproduced, and team production is never individual credit.
    """
    override = OL_EXPERIENCE.get(player['id'])
    if override:
        slug = re.sub(r'[^a-z0-9]+', '-', player['name'].lower()).strip('-')
        source = {'label': override.get('label', 'NFL draft-time college biography'),
                  'url': override.get('url') or f'https://www.nfl.com/prospects/{slug}/{player.get("nflPersonId", "")}' }
        return [dict(entry) for entry in override['entries']], source
    candidates = matching_bios(player, nfl_bios)
    if not candidates:
        return [], None
    profile = max(candidates, key=lambda item: len(item.get('bio') or ''))
    person = profile.get('person', {})
    text = html.unescape(re.sub(r'<[^>]+>', ' ', profile.get('bio') or ''))
    text = re.sub(r'\s+', ' ', text)
    entries = []
    for segment in re.finditer(r'\b(20\d{2})(?:\s*\(([^)]+)\))?\s*:\s*(.*?)(?=\b20\d{2}(?:\s*\([^)]+\))?\s*:|Miscellaneous\s*:|$)', text):
        year, detail = int(segment[1]), segment[3]
        if year >= player['year']:
            continue
        facts = {}
        patterns = [
            ('games', r'\b[Pp]layed(?: in)?(?: all)? (\d+) games'),
            ('starts', r'\b[Ss]tarted(?: in)?(?: all)? (\d+)(?: games)?'),
            ('starts', r'\b(\d+) starts\b'),
            ('snaps', r'\b([\d,]+) (?:offensive )?snaps\b'),
        ]
        for key, pattern in patterns:
            match = re.search(pattern, detail)
            if match:
                value = int(match[1].replace(',', ''))
                if (key == 'snaps' and value <= 2000) or (key != 'snaps' and value <= 20):
                    facts[key] = value
        for key, pattern in [('tacklesForLoss', r'\b(\d+(?:\.\d+)?) (?:TFLs?\b|tackles for loss)'),
                             ('passesBrokenUp', r'\b(\d+) PBUs?\b')]:
            match = re.search(pattern, detail)
            if match:
                facts[key] = float(match[1]) if '.' in match[1] else int(match[1])
        both = re.search(r'[Ss]tarted (?:all )?(\d+) games(?: played)?', detail)
        if both:
            facts['starts'] = int(both[1])
        if facts:
            entries.append({'year': year, 'team': segment[2] or player['college'], **facts})
    if not entries:
        for match in re.finditer(r'\bin (20\d{2}),?\s+(?:starting|started) (\d+) of (\d+) games', text):
            year = int(match[1])
            if year < player['year']:
                entries.append({'year': year, 'team': player['college'], 'starts': int(match[2]), 'games': int(match[3])})
    if not entries and player['position'] in ('OT', 'OG', 'C', 'LS'):
        # Older NFL profiles use prose instead of the recent year-labelled lists.
        # Require an explicit class-year or a single calendar year in the same
        # sentence. Do not turn "every game" into a guessed numeric game count.
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            if re.search(r'high school|prep |all-state|father|brother|cousin|NFL Draft|draft pick', sentence, re.I):
                continue
            if re.search(r'after.{0,45}(?:redshirt|opt(?:ed|ing) out|sat out|miss(?:ed|ing))', sentence, re.I):
                continue
            facts = {}
            both = re.search(r'\b(?:started|starting)\s+(\d+) of (\d+) games', sentence, re.I)
            starts = re.search(r'\b(?:started|starting)(?: all)?\s+(\d+) (?:games|contests)', sentence, re.I)
            games = re.search(r'\b(?:played|playing)(?: in)?(?: all)?\s+(\d+) (?:games|contests|appearances)', sentence, re.I)
            if both:
                facts.update(starts=int(both[1]), games=int(both[2]))
            elif starts:
                facts['starts'] = int(starts[1])
            if games:
                facts['games'] = int(games[1])
            if not starts and not both:
                starts_report = re.search(r'\b(\d+) starts\b', sentence, re.I)
                if starts_report:
                    facts['starts'] = int(starts_report[1])
            if not facts or any(value > 20 for value in facts.values()):
                continue
            years = {int(year) for year in re.findall(r'\b20\d{2}\b', sentence) if int(year) < player['year']}
            class_year = re.search(r'\b(redshirt freshman|true freshman|freshman|sophomore|junior|senior)\b', sentence, re.I)
            if len(years) == 1:
                entry = {'year': years.pop(), 'team': player['college'], **facts}
            elif class_year:
                entry = {'year': None, 'seasonLabel': class_year[1].capitalize() + ' season', 'team': player['college'], **facts}
            else:
                continue
            if re.search(r'\btransfer(?:red|ring)?\b', text, re.I):
                # Draft college is not necessarily the college for an older
                # undated sentence; do not silently assign transfer history.
                entry['team'] = 'College program (see source)'
            if entry not in entries:
                entries.append(entry)
    # Explicit primary-school participation data for this important historical OL.
    if normalized(player['name']) == 'quentonnelson' and player['year'] == 2018:
        entries = [{'year': 2015, 'team': 'Notre Dame', 'games': 12, 'starts': 11},
                   {'year': 2016, 'team': 'Notre Dame', 'games': 12, 'starts': 12},
                   {'year': 2017, 'team': 'Notre Dame', 'games': 13, 'starts': 13, 'snaps': 883}]
        return entries, {'label': 'Notre Dame final college biography', 'url': 'https://fightingirish.com/wp-content/uploads/2019/08/42673__m_footbl_2017_18_misc_non_event__Quenton_Nelson_Final_Bio.pdf'}
    if normalized(player['name']) == 'mylesgarrett' and player['year'] == 2017:
        # The bio explicitly attributes these figures to his 2016 junior season.
        entries = [{'year': 2016, 'team': 'Texas A&M', 'games': 11, 'starts': 9, 'tacklesForLoss': 15}]
    if not entries:
        return [], None
    person_id = person.get('id', '')
    slug = re.sub(r'[^a-z0-9]+', '-', player['name'].lower()).strip('-')
    return entries, {'label': 'NFL draft-time college biography', 'url': f'https://www.nfl.com/prospects/{slug}/{person_id}', 'author': profile.get('profileAuthor') or 'NFL.com'}


def compatible_school(payload, expected):
    target = {school_key(name) for name in expected}
    teams = payload.get('teams', {})
    real = [t for t in teams.values() if not t.get('isAllStar')]
    for team in real:
        names = [team.get('location', ''), team.get('nickname', ''), team.get('shortDisplayName', ''), team.get('abbreviation', '')]
        if any(school_key(name) in target for name in names):
            return True
    # Empty teams means empty published statistical categories, never valid stats.
    return not real and not payload.get('categories')


def allowed_categories(position):
    if position == 'QB': return ['passing', 'rushing']
    if position in ('RB', 'FB'): return ['rushing', 'receiving', 'returning']
    if position in ('WR', 'TE'): return ['receiving', 'rushing', 'returning']
    if position == 'CB / WR': return ['receiving', 'defensive', 'returning']
    if position == 'K': return ['kicking']
    if position == 'P': return ['punting']
    if position in ('OT', 'OG', 'C', 'LS'): return []
    return ['defensive', 'returning']


def biography_statistics(player, nfl_bios):
    facts = BIO_FALLBACK.get(player['id'])
    biographies = matching_bios(player, nfl_bios)
    if not facts or not biographies:
        return [], None
    biography = max(biographies, key=lambda item: len(item.get('bio') or ''))
    if not biography.get('bio'):
        return [], None
    slug = re.sub(r'[^a-z0-9]+', '-', player['name'].lower()).strip('-')
    url = f"https://www.nfl.com/prospects/{slug}/{biography['person']['id']}"
    source = {'label': 'NFL draft-time college biography', 'url': url,
              'author': biography.get('profileAuthor') or 'NFL.com'}
    categories = []
    for key in dict.fromkeys(fact[0] for fact in facts):
        rows = [fact for fact in facts if fact[0] == key]
        metrics = list(dict.fromkeys(metric for _, _, _, values in rows for metric in values))
        columns = [{'key': metric, 'label': BIO_LABELS.get(metric, metric),
                    'description': 'Passes broken up; excludes interceptions.' if metric == 'passesBrokenUp'
                    else re.sub(r'(?<!^)(?=[A-Z])', ' ', metric).capitalize()} for metric in metrics]
        seasons = []
        for _, year, label, values in rows:
            if year is not None and year >= player['year']:
                raise ValueError(f'Biography fact after draft cutoff: {player["id"]}')
            seasons.append({'year': year, 'seasonLabel': label, 'team': player['college'],
                            'teamId': None, 'values': {metric: str(values[metric]) if metric in values else None for metric in metrics},
                            'sourceUrl': url, 'sourceLabel': source['label']})
        categories.append({'key': key, 'label': key.capitalize() + ' · NFL college biography',
                           'columns': columns, 'seasons': seasons,
                           'career': {'values': {}, 'basis': 'Complete career totals were not reported; listed seasons are not aggregated.'},
                           'coverage': 'Partial, explicitly reported college seasons', 'sourceUrl': url})
    return categories, source


def school_statistics(player):
    record = SCHOOL_FALLBACK.get(player['id'])
    if not record:
        return [], None
    evidence = CACHE / record['rawFile']
    if not evidence.exists():
        return [], None
    source = {'label': record['label'], 'url': record['url'], 'rawReference': str(evidence)}
    categories = []
    for key in dict.fromkeys(fact[0] for fact in record['facts']):
        rows = [fact for fact in record['facts'] if fact[0] == key]
        career = record.get('career', {}).get(key, {})
        metrics = list(dict.fromkeys([metric for _, _, _, values in rows for metric in values] + list(career)))
        columns = [{'key': metric, 'label': BIO_LABELS.get(metric, metric),
                    'description': 'Passes broken up; excludes interceptions.' if metric == 'passesBrokenUp'
                    else re.sub(r'(?<!^)(?=[A-Z])', ' ', metric).capitalize()} for metric in metrics]
        seasons = [{'year': year, 'seasonLabel': label, 'team': player['college'], 'teamId': None,
                    'values': {metric: str(values[metric]) if metric in values else None for metric in metrics},
                    'sourceUrl': source['url'], 'sourceLabel': source['label']}
                   for _, year, label, values in rows]
        categories.append({'key': key, 'label': key.capitalize() + ' · Official college record',
                           'columns': columns, 'seasons': seasons, 'sourceUrl': source['url'],
                           'career': {'values': {metric: str(value) for metric, value in career.items()},
                                      'basis': 'Explicitly reported college career totals in the primary biography.' if career else 'Complete career totals not reported; no season aggregation inferred.'}})
    return categories, source


def display(value):
    return None if value is None or str(value).strip() in ('', '-', '--') else str(value)


def make_profile(player, ids, nfl_bios):
    source = []
    result = {'status': 'unavailable', 'athleteId': None, 'sources': source, 'categories': [], 'summary': ''}
    expected = player['college']
    if normalized(expected) in ('none', 'international', '') or normalized(expected).startswith('nocollege'):
        result.update(status='not-applicable', summary='No college football program is listed for this draft selection.')
        return result
    tried = []
    acceptable_schools = [expected]
    for bio in matching_bios(player, nfl_bios):
        acceptable_schools.extend((bio.get('person') or {}).get('collegeNames') or [])
    # Search only unresolved non-OL statistical records, after all verified IDs.
    candidates = list(ids)
    searched = False
    index = 0
    while index < len(candidates) or not searched:
        if index >= len(candidates):
            searched = True
            if player['position'] not in ('OT', 'OG', 'C', 'LS'):
                candidates.extend(aid for aid in searched_ids(player) if aid not in candidates)
            if index >= len(candidates):
                break
        aid = candidates[index]
        index += 1
        raw = athlete(aid)
        tried.append({'athleteId': aid, 'status': raw.get('status'), 'httpStatus': raw.get('httpStatus')})
        if raw.get('status') != 'ok':
            continue
        payload = raw['data']
        if not payload.get('categories'):
            continue
        if not compatible_school(payload, acceptable_schools):
            tried[-1]['status'] = 'school-mismatch'
            continue
        teams = payload.get('teams', {})
        relevant = allowed_categories(player['position'])
        eligible = any(
            category.get('name') in relevant
            and any(season.get('teamId') and not teams.get(season.get('teamSlug'), {}).get('isAllStar')
                    and 0 < (season.get('season', {}).get('year') or 0) < player['year']
                    and any(display(value) is not None for value in season.get('stats', []))
                    for season in category.get('statistics', []))
            for category in payload.get('categories', []))
        if not eligible:
            tried[-1]['status'] = 'no-position-statistics-before-draft'
            continue
        source.append({'label': 'ESPN college career statistics', 'url': f'https://www.espn.com/college-football/player/stats/_/id/{aid}', 'dataUrl': API.format(aid)})
        result['athleteId'] = aid
        for category in payload.get('categories', []):
            if category.get('name') not in allowed_categories(player['position']):
                continue
            columns = [{'key': name, 'label': category.get('labels', [])[i] if i < len(category.get('labels', [])) else name,
                        'description': category.get('descriptions', [])[i] if i < len(category.get('descriptions', [])) else ''}
                       for i, name in enumerate(category.get('names', []))]
            seasons = []
            excluded_future = False
            for season in category.get('statistics', []):
                year = season.get('season', {}).get('year')
                team = teams.get(season.get('teamSlug'), {})
                if not season.get('teamId') or team.get('isAllStar'):
                    continue
                if not year or year >= player['year']:
                    excluded_future = True
                    continue
                values = {col['key']: display(val) for col, val in zip(columns, season.get('stats', []))}
                if not any(v is not None for v in values.values()):
                    continue
                seasons.append({'year': year, 'team': team.get('location') or team.get('displayName') or season.get('teamSlug', expected),
                                'teamId': season['teamId'], 'values': values})
            if not seasons:
                continue
            totals = None if excluded_future else category.get('totals')
            career = {'values': {col['key']: display(val) for col, val in zip(columns, totals or [])},
                      'basis': 'ESPN reported college career totals' if totals else 'Unavailable within draft-time cutoff'}
            result['categories'].append({'key': category['name'], 'label': category.get('displayName', category['name']),
                                         'columns': columns, 'seasons': seasons, 'career': career})
        if result['categories']:
            result['status'] = 'available'
            if not compatible_school(payload, [expected]):
                result['coverageNote'] = f'ESPN publishes statistics for an earlier college program. Later statistics at {expected} are not in this athlete feed; reported career totals represent the available ESPN record.'
        break
    result['identityAttempts'] = tried
    experience, bio_source = college_experience(player, nfl_bios)
    result['experience'] = experience
    result['collegeExperience'] = experience
    if bio_source:
        source.append(bio_source)
        for entry in experience:
            entry.update(sourceUrl=bio_source['url'], sourceLabel=bio_source['label'])
    if not result['categories']:
        fallback, fallback_source = school_statistics(player)
        if fallback:
            result['categories'] = fallback
            result['status'] = 'available-school'
            result['coverageNote'] = 'College statistics from the primary school or NFL team college biography. Only explicitly reported seasons and career figures are included; absent totals are not inferred.'
            if not any(item['url'] == fallback_source['url'] for item in source):
                source.append(fallback_source)
    if not result['categories']:
        fallback, fallback_source = biography_statistics(player, nfl_bios)
        if fallback:
            result['categories'] = fallback
            result['status'] = 'available-biography'
            result['coverageNote'] = 'These college statistics are reported in the official NFL draft-time biography. Coverage is partial; seasons without an explicit calendar year keep the source season label. Complete career totals are unavailable.'
            if not any(item['url'] == fallback_source['url'] for item in source):
                source.append(fallback_source)
    if result['categories']:
        primary = result['categories'][0]
        season = primary['seasons'][-1] if result['status'] in ('available-biography', 'available-school') else max(primary['seasons'], key=lambda s: s['year'])
        vals = season['values']
        if primary['key'] == 'passing': metrics = [('passingYards', 'passing yards'), ('passingTouchdowns', 'TD'), ('interceptions', 'INT'), ('completionPct', '% completions')]
        elif primary['key'] == 'rushing': metrics = [('rushingYards', 'rushing yards'), ('rushingTouchdowns', 'rushing TD'), ('rushingAttempts', 'carries')]
        elif primary['key'] == 'receiving': metrics = [('receptions', 'receptions'), ('receivingYards', 'receiving yards'), ('receivingTouchdowns', 'TD')]
        elif primary['key'] == 'defensive': metrics = [('totalTackles', 'tackles'), ('tacklesForLoss', 'TFL'), ('sacks', 'sacks'), ('interceptions', 'INT'), ('passesDefended', 'passes defended'), ('passesBrokenUp', 'PBU')]
        elif primary['key'] == 'kicking': metrics = [('fieldGoalsMade', 'FG made'), ('fieldGoalAttempts', 'FG attempts'), ('fieldGoalPct', '% FG')]
        else: metrics = [('punts', 'punts'), ('grossAvgPuntYards', 'gross yards/punt'), ('longPunt', 'longest punt yards')]
        facts = [f'{vals[k]} {label}' for k, label in metrics if vals.get(k) is not None]
        history = sorted({(s['year'], s['team']) for c in result['categories'] for s in c['seasons'] if s['year'] is not None})
        schools = list(dict.fromkeys(school for _, school in history))
        result['summary'] = f"{season.get('seasonLabel') or season['year']} at {season['team']}: " + ', '.join(facts) + '. '
        if result['status'] == 'available-biography':
            result['summary'] += 'Official NFL college biography; only explicitly reported season figures are included.'
        elif result['status'] == 'available-school':
            result['summary'] += 'Primary school or NFL team college record; source-reported seasons and career figures only.'
        elif len(schools) > 1:
            result['summary'] += 'Published college history: ' + ' → '.join(schools) + '.'
        else:
            result['summary'] += f"Published college statistics cover {history[0][0]}–{history[-1][0]}."
    elif player['position'] in ('OT', 'OG', 'C', 'LS'):
        result['status'] = 'experience-only'
        if experience:
            last = max(experience, key=lambda item: item.get('year') or -1)
            facts = [f"{last[k]:,} {k}" for k in ('games', 'starts', 'snaps') if k in last]
            result['summary'] = f"{last.get('seasonLabel') or last['year']} at {last['team']}: " + ', '.join(facts) + '. College biography participation figures are shown for the reported years; individual blocking grades are unavailable in this feed.'
        else:
            result['summary'] = f"Drafted from {expected} as a {player['position']}. Individual blocking, snap counts and starts were unavailable in the checked college statistics feed."
    else:
        if experience:
            last = max(experience, key=lambda item: item.get('year') or -1)
            facts = [f"{last[k]:,} {k}" for k in ('games', 'starts', 'tacklesForLoss', 'passesBrokenUp') if k in last]
            result['summary'] = f"{last['year']} at {last['team']}: " + ', '.join(facts) + '. These figures come from the draft-time college biography; full ESPN season/career tables were unavailable.'
        else:
            result['summary'] = f"Drafted from {expected}. No verified college statistical record was available from the checked ESPN athlete identifiers; unavailable metrics are not zero."
    return result


def main():
    drafts = json.loads((PROJECT / 'drafts.json').read_text(encoding='utf-8'))
    players = [{'id': f'{year}-{row[1]}', 'year': int(year), 'name': row[4], 'position': row[5], 'college': row[6]}
               for year, rows in drafts.items() for row in rows]
    workout_path = ROOT / 'workout-profiles.json'
    if workout_path.exists():
        workouts = json.loads(workout_path.read_text(encoding='utf-8'))
        for player in players:
            player['nflPersonId'] = workouts.get(player['id'], {}).get('nflPersonId')
    combined = defaultdict(list)
    for row in csv.DictReader((RAW / 'combine_pro_day.csv').open(encoding='utf-8-sig')):
        combined[(int(float(row['Year'])), normalized(row['player']))].append(row)
    nfl_bios = defaultdict(list)
    for file in (ROOT / 'nfl-years').glob('*.json'):
        payload = json.loads(file.read_text(encoding='utf-8'))
        for profile in payload.get('mergedProfiles', payload.get('combineProfiles', [])):
            nfl_bios[(int(file.stem), normalized(profile.get('person', {}).get('displayName')))].append(profile)
            nfl_bios[('person', profile.get('person', {}).get('id'))].append(profile)
    print(f'Preparing college identity indexes for {len(players)} draft selections.', flush=True)
    boxes = {}
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        for year, index in pool.map(box_index, range(2013, 2026)):
            boxes[year] = index
    profiles = {}
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        pending = {pool.submit(make_profile, player, identity_candidates(player, combined, boxes), nfl_bios): player for player in players}
        for future in futures.as_completed(pending):
            player = pending[future]
            try:
                profiles[player['id']] = future.result()
            except Exception as exc:
                profiles[player['id']] = {'status': 'error', 'sources': [], 'categories': [], 'summary': f'College collection failed: {exc}'}
            if len(profiles) % 100 == 0:
                (ROOT / 'college-profiles.json').write_text(json.dumps(profiles, ensure_ascii=False), encoding='utf-8')
                print(f'College {len(profiles)}/{len(players)}: {dict(Counter(p["status"] for p in profiles.values()))}', flush=True)
    ordered = {p['id']: profiles[p['id']] for p in players}
    identities = defaultdict(list)
    for player in players:
        profile = ordered[player['id']]
        if profile['status'] == 'available':
            identities[(player['year'], profile['athleteId'])].append(player['id'])
    duplicates = {str(key): ids for key, ids in identities.items() if len(ids) > 1}
    if duplicates:
        raise ValueError(f'College athlete identity reused across draft selections: {duplicates}')
    coverage = {'totalPlayers': len(players), 'statuses': dict(Counter(p['status'] for p in ordered.values())),
                'withProductionTables': sum(bool(p.get('categories')) for p in ordered.values()),
                'withBiographyExperience': sum(bool(p.get('experience')) for p in ordered.values()),
                'withOffensiveLineExperience': sum(bool(profiles[p['id']].get('experience')) for p in players if p['position'] in ('OT', 'OG', 'C', 'LS')),
                'byYear': {year: dict(Counter(profiles[p['id']]['status'] for p in players if p['year'] == int(year))) for year in drafts},
                'unresolved': [{'id': p['id'], 'name': p['name'], 'college': p['college'], 'position': p['position'],
                                'attempts': profiles[p['id']].get('identityAttempts', [])} for p in players if not profiles[p['id']].get('athleteId')],
                'notes': ['Published ESPN web-v3 college statistics; missing and unavailable remain null.',
                          'Historical game-box files resolve identity only; sparse aggregates are never career totals.',
                          'All-star and synthetic total rows excluded. College seasons at/after draft year excluded.',
                          'Official NFL college biographies and primary school/team records supplement missing production tables.',
                          'Unresolved lists unavailable ESPN identity joins; these players can still have sourced biography or school tables.',
                          'Undated class-year and career statements retain seasonLabel; calendar years and complete totals are never inferred.',
                          'OL participation, defensive TFL and published blocking facts retain separate primary-source attribution.']}
    (ROOT / 'college-profiles.json').write_text(json.dumps(ordered, ensure_ascii=False), encoding='utf-8')
    (ROOT / 'college-coverage.json').write_text(json.dumps(coverage, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in coverage.items() if k not in ('unresolved', 'notes')}), flush=True)


if __name__ == '__main__':
    main()
