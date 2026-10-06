"""Shared NFL career metric catalogue for the collector, career-arc builder and validator.

Season rows are keyed by short metric names. Counting metrics treat a season the player
did not play as zero when the basis is "all drafted players". Rate metrics only use
seasons that meet their volume qualifier; they are never zero-filled.
"""
from __future__ import annotations

FIRST_DRAFT = 2017
LAST_COMPLETED_SEASON = 2025
IN_PROGRESS_SEASON = 2026
TIMING_CLASSES = (2017, 2021)  # classes with five completed seasons through 2025
TIMING_YEARS = 5
MIN_SAMPLE = 20  # smaller year samples are shown but flagged

# key: label, short label, format, kind, optional qualifier (metric, minimum), description
METRICS = {
    'g': ('Games played', 'G', 'int', 'count', None, 'Regular-season games with at least one offensive, defensive or special-teams snap.'),
    'gs': ('Games started', 'GS', 'int', 'count', None, 'Games started, from Pro Football Reference team rosters (every position, including offensive line).'),
    'av': ('Approximate Value', 'AV', 'int', 'count', None, 'Pro Football Reference\'s single-number estimate of a player\'s season value, comparable across positions. Roughly: 1-3 backup, 4-7 starter, 8-11 good starter, 12+ Pro Bowl level.'),
    'pro_bowl': ('Pro Bowl selections', 'PB', 'int', 'count', None, 'Pro Bowl selection for the season, including replacement selections (as counted by Pro Football Reference).'),
    'all_pro': ('First-team All-Pro (AP)', 'AP 1st', 'int', 'count', None, 'Associated Press first-team All-Pro.'),
    'all_pro_2nd': ('Second-team All-Pro (AP)', 'AP 2nd', 'int', 'count', None, 'Associated Press second-team All-Pro.'),
    'snap50': ('Games at 50%+ snaps', '50%+ G', 'int', 'count', None, 'Games in which the player took at least half of his team\'s snaps on his side of the ball. A starter measure that also covers offensive linemen.'),
    'snap_share': ('Season snap share', 'Snap %', 'pct', 'count', None, 'Share of all team snaps on his side of the ball across the full season, including games missed. Measures role and availability together.'),
    'snap_active': ('Snap share when active', 'Active %', 'pct', 'rate', ('g', 4), 'Share of team snaps on his side of the ball in the games he played (4+ games).'),
    'st_snaps': ('Special-teams snaps', 'ST snaps', 'int', 'count', None, 'Regular-season special-teams snaps.'),
    'side_snaps': ('Snaps on his side of the ball', 'Snaps', 'int', 'count', None, 'Offensive snaps for offensive players, defensive snaps for defenders, special-teams snaps for specialists.'),
    # Passing
    'att': ('Pass attempts', 'Att', 'int', 'count', None, 'Pass attempts.'),
    'cmp': ('Completions', 'Cmp', 'int', 'count', None, 'Completed passes.'),
    'cmp_pct': ('Completion %', 'Cmp %', 'pct', 'rate', ('att', 100), 'Completions divided by attempts (100+ attempts).'),
    'pass_yds': ('Passing yards', 'Pass yds', 'int', 'count', None, 'Passing yards.'),
    'pass_td': ('Passing TD', 'Pass TD', 'int', 'count', None, 'Passing touchdowns.'),
    'int': ('Interceptions thrown', 'INT', 'int', 'count', None, 'Interceptions thrown.'),
    'ypa': ('Yards per attempt', 'Y/A', 'dec1', 'rate', ('att', 100), 'Passing yards per attempt (100+ attempts).'),
    'anya': ('Adj. net yards per attempt', 'ANY/A', 'dec2', 'rate', ('att', 100), '(Pass yards + 20 x TD - 45 x INT - sack yards) / (attempts + sacks). 100+ attempts.'),
    'rating': ('Passer rating', 'Rate', 'dec1', 'rate', ('att', 100), 'NFL passer rating (100+ attempts).'),
    'epa_db': ('EPA per dropback', 'EPA/db', 'dec2', 'rate', ('att', 100), 'Expected points added on passes and sacks, per dropback (100+ attempts).'),
    'cpoe': ('Completion % over expected', 'CPOE', 'dec1', 'rate', ('att', 100), 'Completion percentage above the play-by-play expectation (100+ attempts).'),
    'sacks_taken': ('Sacks taken', 'Sk', 'int', 'count', None, 'Times sacked.'),
    'on_tgt_pct': ('On-target throw %', 'On-tgt %', 'pct', 'rate', ('att', 100), 'PFR charted on-target throws per attempt, 2018+ (100+ attempts).'),
    'pressure_pct': ('Pressured %', 'Pressured', 'pct', 'rate', ('att', 100), 'PFR charted share of dropbacks under pressure, 2018+ (100+ attempts).'),
    'qb_wins': ('QB wins as starter', 'W', 'int', 'count', None, 'Regular-season wins in games he started.'),
    'win_pct': ('Win % as starter', 'Win %', 'pct', 'rate', ('gs', 6), 'Regular-season winning percentage as the starting QB (6+ starts; ties count half).'),
    # Rushing
    'carries': ('Carries', 'Car', 'int', 'count', None, 'Rushing attempts.'),
    'rush_yds': ('Rushing yards', 'Rush yds', 'int', 'count', None, 'Rushing yards.'),
    'rush_td': ('Rushing TD', 'Rush TD', 'int', 'count', None, 'Rushing touchdowns.'),
    'ypc': ('Yards per carry', 'Y/C', 'dec1', 'rate', ('carries', 50), 'Rushing yards per carry (50+ carries).'),
    'carry_share': ('Team carry share', 'Car share', 'pct', 'rate', ('g', 4), 'Share of team rushing attempts in the games he recorded a stat (4+ games played).'),
    'yac_att': ('Yards after contact per carry', 'YAC/car', 'dec1', 'rate', ('carries', 50), 'PFR charted rushing yards after contact per carry, 2018+ (50+ carries).'),
    'brk_tkl': ('Broken tackles', 'Brk tkl', 'int', 'count', None, 'PFR charted broken tackles on rushes and receptions, 2018+.'),
    'scrim_yds': ('Scrimmage yards', 'Scrim yds', 'int', 'count', None, 'Rushing plus receiving yards.'),
    'total_td': ('Scrimmage TD', 'Tot TD', 'int', 'count', None, 'Rushing plus receiving touchdowns.'),
    'fum_lost': ('Fumbles lost', 'FL', 'int', 'count', None, 'Fumbles lost on rushes, receptions and sacks.'),
    # Receiving
    'targets': ('Targets', 'Tgt', 'int', 'count', None, 'Passes thrown to the player.'),
    'rec': ('Receptions', 'Rec', 'int', 'count', None, 'Catches.'),
    'rec_yds': ('Receiving yards', 'Rec yds', 'int', 'count', None, 'Receiving yards.'),
    'rec_td': ('Receiving TD', 'Rec TD', 'int', 'count', None, 'Receiving touchdowns.'),
    'rec_fd': ('Receiving first downs', 'Rec 1D', 'int', 'count', None, 'Receptions that gained a first down.'),
    'catch_pct': ('Catch rate', 'Catch %', 'pct', 'rate', ('targets', 30), 'Receptions per target (30+ targets).'),
    'ypr': ('Yards per reception', 'Y/R', 'dec1', 'rate', ('rec', 20), 'Receiving yards per catch (20+ catches).'),
    'ypt': ('Yards per target', 'Y/Tgt', 'dec1', 'rate', ('targets', 30), 'Receiving yards per target (30+ targets).'),
    'target_share': ('Team target share', 'Tgt share', 'pct', 'rate', ('g', 4), 'Share of all team targets over the full season, so missed games lower it (4+ games played). The core receiver usage rate.'),
    'air_share': ('Team air-yards share', 'Air share', 'pct', 'rate', ('g', 4), 'Share of all team intended air yards over the full season (4+ games played).'),
    'wopr': ('Weighted opportunity rating', 'WOPR', 'dec2', 'rate', ('g', 4), '1.5 x target share + 0.7 x air-yards share. Combines volume and downfield usage (4+ games).'),
    'adot': ('Average depth of target', 'aDOT', 'dec1', 'rate', ('targets', 30), 'PFR charted average air yards per target, 2018+ (30+ targets).'),
    'yac_rec': ('Yards after catch per reception', 'YAC/rec', 'dec1', 'rate', ('rec', 20), 'Receiving yards after the catch per reception (20+ catches).'),
    'drops': ('Drops', 'Drops', 'int', 'count', None, 'PFR charted drops, 2018+.'),
    'drop_pct': ('Drop rate', 'Drop %', 'pct', 'rate', ('targets', 30), 'PFR charted drops per target, 2018+ (30+ targets).'),
    'ppr': ('Fantasy points (PPR)', 'PPR', 'dec1', 'count', None, 'Standard PPR fantasy points.'),
    # Defense
    'tackles': ('Combined tackles', 'Tkl', 'int', 'count', None, 'Solo plus assisted tackles.'),
    'tfl': ('Tackles for loss', 'TFL', 'int', 'count', None, 'Tackles behind the line of scrimmage.'),
    'sacks': ('Sacks', 'Sacks', 'dec1', 'count', None, 'Sacks (half sacks included).'),
    'qb_hits': ('QB hits', 'QB hits', 'int', 'count', None, 'Hits on the quarterback.'),
    'pressures': ('Pressures', 'Prss', 'int', 'count', None, 'PFR charted pressures (hurries + knockdowns + sacks), 2018+.'),
    'hurries': ('Hurries', 'Hrry', 'int', 'count', None, 'PFR charted hurries, 2018+.'),
    'ff': ('Forced fumbles', 'FF', 'int', 'count', None, 'Forced fumbles.'),
    'pd': ('Passes defended', 'PD', 'int', 'count', None, 'Passes defended (play-by-play pass defense credits).'),
    'def_int': ('Interceptions', 'INT', 'int', 'count', None, 'Interceptions.'),
    'missed_tkl_pct': ('Missed tackle rate', 'Miss %', 'pct', 'rate', ('tackle_att', 20), 'PFR charted missed tackles / (tackles + missed tackles), 2018+ (20+ attempts).'),
    'tgt_allowed': ('Targets in coverage', 'Tgt alw', 'int', 'count', None, 'PFR charted targets when in coverage, 2018+.'),
    'cmp_allowed_pct': ('Completion % allowed', 'Cmp % alw', 'pct', 'rate', ('tgt_allowed', 25), 'PFR charted completions allowed per target, 2018+ (25+ targets).'),
    'yds_allowed': ('Yards allowed in coverage', 'Yds alw', 'int', 'count', None, 'PFR charted receiving yards allowed, 2018+.'),
    'ypt_allowed': ('Yards allowed per target', 'Y/Tgt alw', 'dec1', 'rate', ('tgt_allowed', 25), 'PFR charted yards allowed per target, 2018+ (25+ targets).'),
    'td_allowed': ('TD allowed in coverage', 'TD alw', 'int', 'count', None, 'PFR charted touchdowns allowed, 2018+.'),
    'rating_allowed': ('Passer rating allowed', 'Rate alw', 'dec1', 'rate', ('tgt_allowed', 25), 'PFR charted passer rating when targeted, 2018+ (25+ targets). Lower is better.'),
    # Offensive line
    'penalties': ('Penalties', 'Pen', 'int', 'count', None, 'Accepted penalties charged in play-by-play.'),
    'penalty_yds': ('Penalty yards', 'Pen yds', 'int', 'count', None, 'Yards from accepted penalties.'),
    'holds': ('Offensive holding', 'Holds', 'int', 'count', None, 'Accepted offensive holding penalties (play-by-play).'),
    'false_starts': ('False starts', 'False st', 'int', 'count', None, 'Accepted false start penalties (play-by-play).'),
    'hands': ('Illegal use of hands', 'Hands', 'int', 'count', None, 'Accepted illegal use of hands penalties (play-by-play).'),
    'opi': ('Offensive pass interference', 'OPI', 'int', 'count', None, 'Accepted offensive pass interference penalties.'),
    'dpi': ('Defensive pass interference', 'DPI', 'int', 'count', None, 'Accepted defensive pass interference penalties.'),
    'def_holds': ('Defensive holding', 'Def hold', 'int', 'count', None, 'Accepted defensive holding penalties.'),
    'rtp': ('Roughing the passer', 'RTP', 'int', 'count', None, 'Accepted roughing the passer penalties.'),
    'offsides': ('Offsides / encroachment', 'Offside', 'int', 'count', None, 'Accepted defensive offside, neutral zone infraction and encroachment penalties.'),
    'roughness': ('Unnecessary roughness', 'UR', 'int', 'count', None, 'Accepted unnecessary roughness penalties.'),
    # Kicking and punting
    'fgm': ('Field goals made', 'FGM', 'int', 'count', None, 'Field goals made.'),
    'fga': ('Field goal attempts', 'FGA', 'int', 'count', None, 'Field goal attempts.'),
    'fg_pct': ('Field goal %', 'FG %', 'pct', 'rate', ('fga', 10), 'Field goals made per attempt (10+ attempts).'),
    'fg50': ('50+ yard field goals', '50+ FGM', 'int', 'count', None, 'Field goals made from 50+ yards.'),
    'fg_long': ('Longest field goal', 'Long', 'int', 'rate', ('fgm', 1), 'Longest made field goal.'),
    'xp_pct': ('Extra point %', 'XP %', 'pct', 'rate', ('xpa', 10), 'Extra points made per attempt (10+ attempts).'),
    'punts': ('Punts', 'Punts', 'int', 'count', None, 'Punts.'),
    'punt_avg': ('Gross punting average', 'Avg', 'dec1', 'rate', ('punts', 20), 'Gross yards per punt (20+ punts).'),
    'net_avg': ('Net punting average', 'Net', 'dec1', 'rate', ('punts', 20), 'Net yards per punt after returns and touchbacks (20+ punts).'),
    'in20_pct': ('Inside-20 rate', 'In20 %', 'pct', 'rate', ('punts', 20), 'Punts downed inside the 20 per punt (20+ punts).'),
    # Returns
    'kr': ('Kick returns', 'KR', 'int', 'count', None, 'Kickoff returns.'),
    'kr_yds': ('Kick return yards', 'KR yds', 'int', 'count', None, 'Kickoff return yards.'),
    'pr': ('Punt returns', 'PR', 'int', 'count', None, 'Punt returns.'),
    'pr_yds': ('Punt return yards', 'PR yds', 'int', 'count', None, 'Punt return yards.'),
}

LOWER_IS_BETTER = {'int', 'fum_lost', 'drop_pct', 'drops', 'missed_tkl_pct', 'cmp_allowed_pct', 'ypt_allowed', 'rating_allowed', 'td_allowed', 'yds_allowed', 'penalties', 'penalty_yds', 'pressure_pct', 'sacks_taken',
                   'holds', 'false_starts', 'hands', 'opi', 'dpi', 'def_holds', 'rtp', 'offsides', 'roughness'}
UNKNOWN_WHEN_MISSING = {'gs', 'av'}  # only known where a PFR roster row (or published starts) exists
PFR_ADVANCED_FROM_2018 = {'pressures', 'hurries', 'missed_tkl_pct', 'tgt_allowed', 'cmp_allowed_pct', 'yds_allowed', 'ypt_allowed', 'td_allowed', 'rating_allowed', 'adot', 'drops', 'drop_pct', 'yac_att', 'brk_tkl', 'on_tgt_pct', 'pressure_pct'}

USAGE = ['g', 'gs', 'av', 'snap50', 'snap_share', 'snap_active', 'side_snaps', 'st_snaps']
HONORS = ['av', 'pro_bowl', 'all_pro', 'all_pro_2nd', 'awards']
DEF_PENALTIES = ['penalties', 'penalty_yds', 'dpi', 'def_holds', 'rtp', 'offsides', 'roughness']
PASSING = ['cmp', 'att', 'cmp_pct', 'pass_yds', 'pass_td', 'int', 'ypa', 'anya', 'rating', 'epa_db', 'cpoe', 'sacks_taken', 'on_tgt_pct', 'pressure_pct', 'qb_wins', 'win_pct']
RUSHING = ['carries', 'rush_yds', 'ypc', 'rush_td', 'carry_share', 'yac_att', 'brk_tkl', 'fum_lost']
RECEIVING = ['targets', 'rec', 'rec_yds', 'rec_td', 'rec_fd', 'catch_pct', 'ypr', 'ypt', 'target_share', 'air_share', 'wopr', 'adot', 'yac_rec', 'drops', 'drop_pct']
FRONT = ['tackles', 'tfl', 'sacks', 'qb_hits', 'pressures', 'hurries', 'ff', 'pd', 'def_int', 'missed_tkl_pct']
COVERAGE = ['tackles', 'def_int', 'pd', 'tfl', 'sacks', 'ff', 'tgt_allowed', 'cmp_allowed_pct', 'yds_allowed', 'ypt_allowed', 'td_allowed', 'rating_allowed', 'missed_tkl_pct']
KICKING = ['fgm', 'fga', 'fg_pct', 'fg50', 'fg_long', 'xp_pct']
PUNTING = ['punts', 'punt_avg', 'net_avg', 'in20_pct']
RETURNS = ['kr', 'kr_yds', 'pr', 'pr_yds']
LINE = ['penalties', 'penalty_yds', 'holds', 'false_starts', 'hands']


def ms(label, test, metric=None):
    return {'label': label, 'test': test, 'metric': metric}


GROUPS = {
    'QB': dict(label='Quarterbacks', positions=['QB'], side='off', default='pass_yds',
               metrics=USAGE + PASSING + ['carries', 'rush_yds', 'rush_td', 'ppr'] + ['pro_bowl', 'all_pro'],
               milestones=[ms('Starter (9+ starts)', lambda s: (s.get('gs') or 0) >= 9, 'gs'),
                           ms('3,500+ passing yards', lambda s: (s.get('pass_yds') or 0) >= 3500, 'pass_yds'),
                           ms('25+ passing TD', lambda s: (s.get('pass_td') or 0) >= 25, 'pass_td'),
                           ms('ANY/A 6.5+ (200+ att)', lambda s: (s.get('att') or 0) >= 200 and (s.get('anya') or 0) >= 6.5, 'anya'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Passing', PASSING), ('Rushing', ['carries', 'rush_yds', 'ypc', 'rush_td', 'fum_lost'])]),
    'RB': dict(label='Running backs', positions=['RB'], side='off', default='scrim_yds',
               metrics=USAGE + ['scrim_yds', 'total_td'] + RUSHING + ['targets', 'rec', 'rec_yds', 'rec_td', 'target_share', 'catch_pct', 'ypr', 'ppr'] + RETURNS + ['pro_bowl', 'all_pro'],
               milestones=[ms('1,000+ rushing yards', lambda s: (s.get('rush_yds') or 0) >= 1000, 'rush_yds'),
                           ms('1,200+ scrimmage yards', lambda s: (s.get('scrim_yds') or 0) >= 1200, 'scrim_yds'),
                           ms('50+ receptions', lambda s: (s.get('rec') or 0) >= 50, 'rec'),
                           ms('50%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .5, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Rushing', RUSHING), ('Receiving', ['targets', 'rec', 'rec_yds', 'rec_td', 'catch_pct', 'ypr', 'target_share', 'drops']), ('Totals & fantasy', ['scrim_yds', 'total_td', 'ppr']), ('Returns', RETURNS)]),
    'FB': dict(label='Fullbacks', positions=['FB'], side='off', default='snap_share',
               metrics=USAGE + ['carries', 'rush_yds', 'rush_td', 'targets', 'rec', 'rec_yds', 'rec_td', 'ppr'] + ['pro_bowl', 'all_pro'],
               milestones=[ms('25%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .25, 'snap_share'),
                           ms('Full season (16+ games)', lambda s: (s.get('g') or 0) >= 16, 'g'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Rushing & receiving', ['carries', 'rush_yds', 'rush_td', 'targets', 'rec', 'rec_yds', 'rec_td'])]),
    'WR': dict(label='Wide receivers', positions=['WR', 'CB / WR'], side='off', default='rec_yds',
               metrics=USAGE + RECEIVING + ['carries', 'rush_yds', 'ppr'] + RETURNS + ['pro_bowl', 'all_pro'],
               milestones=[ms('1,000+ receiving yards', lambda s: (s.get('rec_yds') or 0) >= 1000, 'rec_yds'),
                           ms('100+ targets', lambda s: (s.get('targets') or 0) >= 100, 'targets'),
                           ms('20%+ target share (8+ games)', lambda s: (s.get('g') or 0) >= 8 and (s.get('target_share') or 0) >= .2, 'target_share'),
                           ms('75%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .75, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Receiving', RECEIVING), ('Rushing, fantasy & returns', ['carries', 'rush_yds', 'rush_td', 'ppr'] + RETURNS)]),
    'TE': dict(label='Tight ends', positions=['TE'], side='off', default='rec_yds',
               metrics=USAGE + RECEIVING + ['ppr', 'penalties'] + ['pro_bowl', 'all_pro'],
               milestones=[ms('600+ receiving yards', lambda s: (s.get('rec_yds') or 0) >= 600, 'rec_yds'),
                           ms('900+ receiving yards', lambda s: (s.get('rec_yds') or 0) >= 900, 'rec_yds'),
                           ms('15%+ target share (8+ games)', lambda s: (s.get('g') or 0) >= 8 and (s.get('target_share') or 0) >= .15, 'target_share'),
                           ms('60%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .6, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Receiving', RECEIVING), ('Fantasy & penalties', ['ppr', 'penalties', 'penalty_yds'])]),
    'T': dict(label='Offensive tackles', positions=['OT'], side='off', default='snap_share',
              metrics=USAGE + LINE + ['pro_bowl', 'all_pro'],
              milestones=[ms('50%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .5, 'snap_share'),
                          ms('12+ games started', lambda s: (s.get('gs') or 0) >= 12, 'gs'),
                          ms('90%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .9, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
              tables=[('Honors & value', HONORS), ('Penalties', LINE)]),
    'G': dict(label='Guards', positions=['OG'], side='off', default='snap_share',
              metrics=USAGE + LINE + ['pro_bowl', 'all_pro'],
              milestones=[ms('50%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .5, 'snap_share'),
                          ms('12+ games started', lambda s: (s.get('gs') or 0) >= 12, 'gs'),
                          ms('90%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .9, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
              tables=[('Honors & value', HONORS), ('Penalties', LINE)]),
    'C': dict(label='Centers', positions=['C'], side='off', default='snap_share',
              metrics=USAGE + LINE + ['pro_bowl', 'all_pro'],
              milestones=[ms('50%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .5, 'snap_share'),
                          ms('12+ games started', lambda s: (s.get('gs') or 0) >= 12, 'gs'),
                          ms('90%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .9, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
              tables=[('Honors & value', HONORS), ('Penalties', LINE)]),
    'DE': dict(label='Edge rushers', positions=['DE', 'OLB'], side='def', default='sacks',
               metrics=USAGE + FRONT + ['pro_bowl', 'all_pro'] + DEF_PENALTIES,
               milestones=[ms('8+ sacks', lambda s: (s.get('sacks') or 0) >= 8, 'sacks'),
                           ms('30+ pressures', lambda s: (s.get('pressures') or 0) >= 30, 'pressures'),
                           ms('10+ tackles for loss', lambda s: (s.get('tfl') or 0) >= 10, 'tfl'),
                           ms('60%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .6, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Pass rush & tackling', FRONT), ('Penalties', DEF_PENALTIES)]),
    'DT': dict(label='Interior defensive line', positions=['DT', 'NT'], side='def', default='pressures',
               metrics=USAGE + FRONT + ['pro_bowl', 'all_pro'] + DEF_PENALTIES,
               milestones=[ms('5+ sacks', lambda s: (s.get('sacks') or 0) >= 5, 'sacks'),
                           ms('20+ pressures', lambda s: (s.get('pressures') or 0) >= 20, 'pressures'),
                           ms('60%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .6, 'snap_share'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Pass rush & tackling', FRONT), ('Penalties', DEF_PENALTIES)]),
    'LB': dict(label='Off-ball linebackers', positions=['LB'], side='def', default='tackles',
               metrics=USAGE + FRONT + ['tgt_allowed', 'cmp_allowed_pct', 'ypt_allowed', 'rating_allowed', 'pro_bowl', 'all_pro'] + DEF_PENALTIES,
               milestones=[ms('100+ tackles', lambda s: (s.get('tackles') or 0) >= 100, 'tackles'),
                           ms('80%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .8, 'snap_share'),
                           ms('5+ sacks', lambda s: (s.get('sacks') or 0) >= 5, 'sacks'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Tackling & pass rush', FRONT), ('Coverage', ['tgt_allowed', 'cmp_allowed_pct', 'yds_allowed', 'ypt_allowed', 'td_allowed', 'rating_allowed']), ('Penalties', DEF_PENALTIES)]),
    'CB': dict(label='Cornerbacks', positions=['CB', 'CB / WR'], side='def', default='snap_share',
               metrics=USAGE + COVERAGE + RETURNS + ['pro_bowl', 'all_pro'] + DEF_PENALTIES,
               milestones=[ms('75%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .75, 'snap_share'),
                           ms('12+ passes defended', lambda s: (s.get('pd') or 0) >= 12, 'pd'),
                           ms('3+ interceptions', lambda s: (s.get('def_int') or 0) >= 3, 'def_int'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ('Coverage & tackling', COVERAGE), ('Penalties', DEF_PENALTIES), ('Returns', RETURNS)]),
    'S': dict(label='Safeties', positions=['S', 'FS'], side='def', default='snap_share',
              metrics=USAGE + COVERAGE + ['pro_bowl', 'all_pro'] + DEF_PENALTIES,
              milestones=[ms('75%+ season snap share', lambda s: (s.get('snap_share') or 0) >= .75, 'snap_share'),
                          ms('80+ tackles', lambda s: (s.get('tackles') or 0) >= 80, 'tackles'),
                          ms('3+ interceptions', lambda s: (s.get('def_int') or 0) >= 3, 'def_int'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
              tables=[('Honors & value', HONORS), ('Coverage & tackling', COVERAGE), ('Penalties', DEF_PENALTIES)]),
    'K': dict(label='Kickers', positions=['K'], side='st', default='fg_pct',
              metrics=['g', 'av', 'st_snaps'] + KICKING + ['pro_bowl', 'all_pro'],
              milestones=[ms('Full-time kicker (20+ FGA)', lambda s: (s.get('fga') or 0) >= 20, 'fga'),
                          ms('85%+ FG on 20+ attempts', lambda s: (s.get('fga') or 0) >= 20 and (s.get('fg_pct') or 0) >= .85, 'fg_pct'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
              tables=[('Honors & value', HONORS), ('Kicking', KICKING + ['xpm', 'xpa'])]),
    'P': dict(label='Punters', positions=['P'], side='st', default='net_avg',
              metrics=['g', 'av', 'st_snaps'] + PUNTING + ['pro_bowl', 'all_pro'],
              milestones=[ms('Full-time punter (40+ punts)', lambda s: (s.get('punts') or 0) >= 40, 'punts'),
                          ms('42+ net average (40+ punts)', lambda s: (s.get('punts') or 0) >= 40 and (s.get('net_avg') or 0) >= 42, 'net_avg'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
              tables=[('Honors & value', HONORS), ('Punting', PUNTING)]),
    'LS': dict(label='Long snappers', positions=['LS'], side='st', default='g',
               metrics=['g', 'av', 'st_snaps'] + ['pro_bowl', 'all_pro'],
               milestones=[ms('Full season (16+ games)', lambda s: (s.get('g') or 0) >= 16, 'g'),
                           ms('Pro Bowl selection', lambda s: (s.get('pro_bowl') or 0) >= 1, 'pro_bowl')],
               tables=[('Honors & value', HONORS), ]),
}
GROUP_ORDER = ['QB', 'RB', 'FB', 'WR', 'TE', 'T', 'G', 'C', 'DE', 'DT', 'LB', 'CB', 'S', 'K', 'P', 'LS']
EXTRA_LABELS = {'xpm': ('Extra points made', 'XPM', 'int', 'count', None, 'Extra points made.'),
                'xpa': ('Extra point attempts', 'XPA', 'int', 'count', None, 'Extra point attempts.')}
METRICS.update(EXTRA_LABELS)

ROUND_BUCKETS = {'all': ('All rounds', lambda r: True), 'r1': ('Round 1', lambda r: r == 1),
                 'r23': ('Rounds 2-3', lambda r: r in (2, 3)), 'r47': ('Rounds 4-7', lambda r: r >= 4)}


FRONT_SEVEN = {'DE', 'OLB', 'LB', 'DT', 'NT'}
ROLE_GROUPS = {'ED': 'DE', 'DI': 'DT', 'LB': 'LB'}  # PFF role tags in the nflverse player table


def groups_for_position(position, role=None):
    """Career group(s) for a drafted position. Front-seven players follow their NFL role tag
    (edge, interior, off-ball) when one exists, because draft listings blur DE/OLB/LB."""
    if position in FRONT_SEVEN and role in ROLE_GROUPS:
        return [ROLE_GROUPS[role]]
    return [key for key in GROUP_ORDER if position in GROUPS[key]['positions']]


def qualifies(metric, season):
    """True when a rate metric has enough volume in this season to be compared."""
    spec = METRICS[metric]
    if spec[4] is None:
        return True
    volume_key, minimum = spec[4]
    return (season.get(volume_key) or 0) >= minimum


def metric_value(metric, season, basis='all'):
    """Comparable value for one player-season, or None when it should be excluded.

    basis='all': counting stats count a season without games as zero.
    basis='played': only seasons with at least one game.
    Rate stats always require their qualifier; unknown (pre-2018 charted) values are None.
    """
    played = (season.get('g') or 0) > 0
    value = season.get(metric)
    if METRICS[metric][3] == 'rate':
        if not played or value is None or not qualifies(metric, season):
            return None
        return value
    if metric in PFR_ADVANCED_FROM_2018 and season['season'] < 2018:
        return None
    if not played:
        return 0 if basis == 'all' else None
    if value is None and metric in UNKNOWN_WHEN_MISSING:
        return None
    return 0 if value is None else value


def derive(s):
    """Rate statistics derived from counting totals (season rows and career totals)."""
    def put(key, value, digits=4):
        if value is not None:
            s[key] = round(value, digits)
    att, cmp_, yds = s.get('att'), s.get('cmp') or 0, s.get('pass_yds') or 0
    if att:
        td, ints, sacks = s.get('pass_td') or 0, s.get('int') or 0, s.get('sacks_taken') or 0
        put('cmp_pct', cmp_ / att)
        put('ypa', yds / att, 2)
        # nflverse stores sack yardage as a negative number
        put('anya', (yds + 20 * td - 45 * ints - abs(s.get('sack_yds') or 0)) / (att + sacks), 2)
        clamp = lambda v: max(0, min(2.375, v))
        parts = [clamp((cmp_ / att - .3) * 5), clamp((yds / att - 3) * .25), clamp(td / att * 20), clamp(2.375 - ints / att * 25)]
        put('rating', sum(parts) / 6 * 100, 1)
        if s.get('pass_epa') is not None:
            put('epa_db', s['pass_epa'] / (att + sacks), 3)
    if s.get('cpoe') is not None:
        put('cpoe', s['cpoe'], 2)
    if s.get('carries'):
        put('ypc', (s.get('rush_yds') or 0) / s['carries'], 2)
    if s.get('targets'):
        put('catch_pct', (s.get('rec') or 0) / s['targets'])
        put('ypt', (s.get('rec_yds') or 0) / s['targets'], 2)
        if s.get('drops') is not None:
            put('drop_pct', s['drops'] / s['targets'])
    if s.get('rec'):
        put('ypr', (s.get('rec_yds') or 0) / s['rec'], 2)
        if s.get('yac') is not None:
            put('yac_rec', s['yac'] / s['rec'], 2)
    scrim = (s.get('rush_yds') or 0) + (s.get('rec_yds') or 0)
    if scrim:
        s['scrim_yds'] = scrim
    tds = (s.get('rush_td') or 0) + (s.get('rec_td') or 0)
    if tds:
        s['total_td'] = tds
    if s.get('tgt_allowed'):
        put('cmp_allowed_pct', (s.get('cmp_allowed') or 0) / s['tgt_allowed'])
        put('ypt_allowed', (s.get('yds_allowed') or 0) / s['tgt_allowed'], 2)
    if s.get('fga'):
        put('fg_pct', (s.get('fgm') or 0) / s['fga'])
    if s.get('xpa'):
        put('xp_pct', (s.get('xpm') or 0) / s['xpa'])
    if s.get('punts'):
        put('punt_avg', (s.get('punt_yds') or 0) / s['punts'], 2)
        if s.get('punt_net_yds') is not None:
            put('net_avg', s['punt_net_yds'] / s['punts'], 2)
        put('in20_pct', (s.get('in20') or 0) / s['punts'])
    for key in ('target_share', 'air_share', 'wopr'):
        if s.get(key) is not None:
            put(key, s[key])
    if s.get('ppr') is not None:
        put('ppr', s['ppr'], 1)


def catalog():
    return {key: {'label': v[0], 'short': v[1], 'format': v[2], 'kind': v[3],
                  'qualifier': ({'metric': v[4][0], 'minimum': v[4][1]} if v[4] else None),
                  'description': v[5], 'lowerIsBetter': key in LOWER_IS_BETTER,
                  'chartedFrom2018': key in PFR_ADVANCED_FROM_2018}
            for key, v in METRICS.items()}
