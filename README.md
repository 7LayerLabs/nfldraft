# NFL Draft Archive

Complete 2017–2026 NFL drafts with year dropdowns, all rounds, overall picks, teams/trade origins, positions and colleges. Every selection opens an addressable player profile with NFL career stats by season, position-focused testing, college production, a career summary and brief sourced pre-draft scouting excerpts.

## Run locally

Python 3.10+ is sufficient to serve the included app; no account, API key, Node build or database is required.

```sh
python -m http.server 8766 --bind 127.0.0.1 --directory local
```

Open http://localhost:8766/. A player URL looks like http://localhost:8766/#player=2017-10. Serve through HTTP rather than opening the HTML file directly, because profiles load JSON files.

## Included data

| Coverage | Players |
| --- | ---: |
| Complete draft selections and profiles | 2,569 |
| At least height and weight | 2,569 |
| Brief sourced scouting excerpts | 2,527 |
| College production tables | 2,118 |
| Additional college biography/participation figures | 953 |
| OL/LS with published numerical participation | 338 of 447 |
| Curated additional workout event reports | 12 |
| No college football history | 4 |

College production comprises 2,057 ESPN records, 54 NFL college-biography fallbacks and seven primary school/team fallbacks. Biography tables can be partial. The remaining 447 college records are offensive linemen/long snappers, for whom ordinary production tables are generally unavailable; 338 have sourced participation figures. Four players did not play college football. The app labels missing values and absent scouting reports explicitly.

Download the complete draft CSV, each player JSON, or the ZIP containing all profiles, coverage, measurement definitions and positional distributions. Published JSON files preserve individual observations and source links. Unpublished private-workout results cannot be recovered; the app does not infer them.

## Current teams and league status

The **Current team** column follows College and is separate from the team that drafted the player. The page displays the roster snapshot date and links each current team/status to its source. Profiles, the CSV and the complete profile ZIP include the same dated membership data; `local/data/current-teams.json` contains the full join and source coverage report.

Players listed on current NFL rosters retain their team, including reserve and practice-squad membership when supplied. Players without a current team show `--` plus a sourced status such as Free agent, Retired or Unsigned. Missing roster membership alone does not establish retirement; unconfirmed statuses remain explicitly labelled.

The 2026-10-06 snapshot has 1,583 rostered players, 851 explicit free agents, 104 explicitly inactive players, 17 confirmed retirements, four deceased players and ten unconfirmed statuses. An Inactive provider status is not treated as a retirement announcement. No explicit Unsigned result was returned in this snapshot; the collector supports it when reported.

To refresh the current membership snapshot without repeating historical college/workout collection:

```sh
python -m pip install -r requirements.txt
python prepare-source-cache.py
python collect-current-teams.py
python build-site.py
python validate-current-teams.py
python validate-profiles.py
```

The collector requires complete retrieval from all 32 NFL and ESPN rosters before publishing a replacement. Current membership is a source snapshot, so rerun this refresh when rosters change. Same-day cached reconstruction uses `python collect-current-teams.py --reuse-cache`. `validation/current-team-status-overrides.json` holds the reviewed primary retirement/deceased reports; live roster membership takes priority when players return. `validation/current-teams-validation.json` records the roster and identity checks. Raw responses remain outside Git; `python validate-current-teams.py --require-source-cache` reconciles every published result against the collected evidence.

## NFL careers and Career Arcs

Every profile now opens with an **NFL career** section: one row per career year (Year 1 = draft season) from the draft season through the in-progress season, including seasons without games. Tables cover playing time (games, PFR games started where published, games at 50%+ snaps, season snap share, snap share when active, special-teams snaps) plus position production: passing, rushing, receiving, pass rush, coverage, kicking, punting and returns.

The **Career arcs** view (http://localhost:8766/#careers) answers when each position typically arrives. For each of 16 position groups (QB, RB, FB, WR, TE, T, G, C, edge, interior DL, off-ball LB, CB, S, K, P, LS) it shows:

- breakout timing: the first season each milestone was reached, plus the career-best season within Years 1-5, for the 2017-2021 classes (all had five completed seasons)
- a year-by-year chart and table (median, average, 75th and 90th percentiles) of any metric, filtered by round group and by all drafted players vs players who played
- same-player year-over-year change, which removes survivor bias
- a sortable grid of every player at the position with Year 1-10 values

Front-seven players are grouped by NFL role tag (edge, interior, off-ball) where nflverse supplies one, so T.J. Watt counts as edge even though he was drafted as a linebacker. Downloads: `nfl-career-arcs-2017-2026.xlsx` (one sheet per position with Year 1-10 column blocks, plus trend sheets), `nfl-career-seasons-2017-2026.csv` (every player-season) and `data/nfl-careers.json`.

Sources: games played, games started (all positions, including offensive line), season Approximate Value, Pro Bowls, AP All-Pro teams and awards (AP MVP, OPOY, DPOY, OROY, DROY, Comeback, Super Bowl MVP, Walter Payton Man of the Year) come from Pro Football Reference team roster, Pro Bowl, All-Pro and award pages. PFR blocks scripted clients, so `collect-pfr-browser.js` runs in a normal browser tab (paste into the DevTools console on any PFR page, then `savePfr()`), at under 20 pages per minute; place the downloaded `pfr-rosters-honors.json` in `~/.agent-reach/nfl-player-profiles/pfr/`. Box-score data comes from nflverse public releases: NFL play-by-play player statistics, penalty detail by type (holding, false starts, pass interference, roughing, offsides), PFR snap counts, PFR advanced charting (2018+), schedules with starting quarterbacks, and PFR draft records. Each profile links to the player's PFR page. `validation/nfl-careers-validation.json` records 33 PFR spot checks and a comparison of summed seasons with PFR career totals. Finished careers match exactly. Active players differ only because nflverse captured PFR's totals at an earlier week of the current season.

Weekly refresh during the season:

```sh
python collect-nfl-careers.py --refresh-current
python build-career-arcs.py
python build-scouting-reports.py
python build-grades.py
python build-scouting-reports.py
python write-scouting-copy.py        # only re-writes copy whose numbers changed
python write-scouting-copy.py --merge
python build-site.py
python validate-nfl-careers.py
```

## Scouting reports

Each profile has two side-by-side reports built from data in this archive (not film grades):

- **Draft-day report:** NFL.com prospect grade ranked within the draft class and at the position (grade scales changed over the years, so ranks are comparable across years), pick vs grade rank, projection and published comparison, athletic-testing percentiles, college production ranked against the class at the position, and the short attributed strength/concern excerpts with a link to the full published report. Full report prose is linked, not republished.
- **Current report:** league status, a trend label (best season yet, near peak, below peak, developing, not on a roster), Approximate Value by season with Pro Bowl/All-Pro markers, the latest completed season ranked against every 2017-2025 season by drafted players at the position, comparison with the typical player in the same career year, the current season so far, and links to ESPN news and PFR.

`build-scouting-reports.py` runs after `build-career-arcs.py`.

## Archive grades

Every player carries three grades on one 5.0-8.0 scale (7.5+ rare/All-Pro caliber, 7.0 Pro Bowl caliber, 6.7 high-end starter, 6.5 quality starter, 6.3 average starter, 6.1 spot starter/top backup, 6.0 backup/special teams, 5.7 fringe roster, below 5.7 did not stick), shown next to the NFL.com prospect grade:

- **Archive draft grade:** pre-draft information only (NFL.com grade percentile within the class, athletic-testing percentile, college production percentile within the class and position), weighted by one ridge regression trained on how 2017-2021 picks turned out. Each 2017-2021 class is graded by a model that never saw that class's results; predictions are spread to each position family's outcome distribution.
- **Hindsight grade:** best three seasons of Approximate Value (seasons without games count as zero) ranked against the 2017-2022 classes at the same position group, with positional Pro Bowls, AP All-Pro selections and major awards as floors. Special-teams/return honors are shown but do not set position floors. Provisional under three completed seasons.
- **Current grade:** the last three completed seasons of AV weighted 0.6/0.3/0.1, ranked the same way; players not on a roster are capped at 5.80; current-season rookies carry their draft grade.

On 2017-2021 picks, rank agreement with hindsight grades (Spearman) is about 0.50 for both the NFL.com grade and the archive draft grade; actual draft order is about 0.59. `local/data/grades.json` holds the scale, model weights and per-position evaluation.

## Scout-style write-ups

`write-scouting-copy.py` uses the local Claude Code CLI to write an original draft-day report (pre-draft facts plus the NFL.com narrative as background, from the private cache built by `collect-scouting-text.py`) and a current report (a fact sheet from the archive's NFL data) for every player. Copy that reuses any 6-word sequence from the NFL.com text, or contains a number not present in the player's data, is rejected and rewritten; on later runs, cached copy that no longer matches the data is dropped and rewritten. Full NFL.com prose is never published.

## Measurement info and percentiles

Each of the 14 measurement/drill fields has an info button with its definition, interpretation, positional average, median, middle 50%, sample size and player percentile when supported.

The reference population is **players drafted in this archive**, not all combine invitees or every current NFL player. Each player contributes one reading per metric. Speed, jump and bench reference samples use official NFL Scouting Combine results when available. If a position/metric has none, the reference uses reported mixed-event results and says so. Body measurements use preferred reported readings with differing measurement dates/events disclosed. Pro-day results compared with official combine results carry a cross-event estimate label. The cancelled 2021 in-person combine supplies no official-combine observations.

Percentiles use empirical midpoint ranks for ties. Lower sprint/shuttle/cone times rank higher; higher jumps/bench counts rank higher. Size percentiles describe larger measurements and do not grade football ability. Samples smaller than 20 show descriptive statistics without rankings. Positional averages are arithmetic means; quartiles use linear interpolation. Missing and quarantined invalid observations are excluded.

For example, 4.34 seconds is approximately the 90th percentile among the 221 eligible WR official-combine results in this snapshot. The WR mean is approximately 4.46 seconds. This is a comparison with the specified sample, rather than a universal NFL percentile.

## Build and verification

The generated data and local assets are checked in, so a fresh clone works immediately. To rebuild the UI and distributions from the included profiles:

```sh
python build-benchmarks.py
python build-site.py
python validate-profiles.py
python validate-benchmarks.py
```

`build-site.py` packages the JSON download after the benchmark build. Editing `site-template.html` or `profile-ui.js/css` requires running it. `node --check profile-ui.js` checks JavaScript syntax if Node is installed.

To refresh source collections, install `requirements.txt`, run `prepare-source-cache.py`, then `collect-workouts.py`, `collect-college.py`, `build-supplements.py`, `build-profiles.py`, and the build/validation commands above in that order. Collectors persist their source responses outside the repository at `~/.agent-reach/nfl-player-profiles/`, use bounded requests and retain provenance. NFL anonymous access tokens remain in process memory. Source endpoints and provider coverage can change; refresh coverage reports before replacing published data.

## Source and asset notes

Draft selections/trade origins link to each year's source in the archive. Testing uses [NFL prospect profiles](https://www.nfl.com/draft/tracker/prospects/), [array-carpenter's sourced workout data](https://github.com/array-carpenter/nfl-draft-data), and individually linked NFL/team/school reports. College production uses ESPN college-athlete records and the primary biography links attached to each table. Scouting quotes are short attributed excerpts totaling no more than 24 words per player; the full report is linked. Grades and comparisons retain their original pre-draft context.

Team logos are sourced from ESPN's public team asset CDN. Barlow fonts are served locally. NFL/team names and marks belong to their respective owners. See `profile-source-review.md`, `profile-coverage.json`, and `todo.md` for source handling, validation and remaining data gaps.
