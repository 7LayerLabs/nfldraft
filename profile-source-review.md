# NFL player-profile source review

Status: approved by Derek's GO AND BUILD instruction; collection, profiles and measurement context are published and validated.

## Final coverage and handling
- 2,569 profiles/measurement records; 2,527 short sourced scouting reports; 2,118 college production tables (2,057 ESPN, 54 NFL biography, seven school/team); 953 additional biography records; 338/447 OL/LS numerical participation records; four no-college players.
- Twelve players have separately curated published workout reports. A scheduled visit does not establish workout completion or published private test results.
- Observations retain units, source/event and designation. Mutable prospect body readings and uncertain mixed-source events stay unspecified. Six inconsistent source observations are quarantined rather than guessed.
- Identity checks use NFL person IDs, college ESPN IDs, aliases, colleges and primary biographies. Same-name collisions were resolved; all 2,569 published identities pass validation.
- Scouting excerpts total at most 24 words per player. Full source narratives stay outside the repository; anonymous NFL tokens remain in memory.
- Fourteen measurement definitions link to primary NFL/team explanations. The app includes 239 distributions across 19 positions. Official-combine samples exclude 2021; size and mixed-event cohorts are disclosed. Percentiles require 20 results and use midpoint ranks for ties.
- Investigation notes below describe initial discovery. Final joins and coverage supersede preliminary counts.

## Measurements and scouting
- [NFL combine profiles](https://api.nfl.com/football/v2/combine/profiles?year=2026&limit=2): successfully tested for 2017 and 2026 using the NFL's public anonymous WEB_DESKTOP identity token. Returns combineProfiles and pagination metadata, person IDs, measurements with OFFICIAL/UNOFFICIAL designation, biography, overview, strengths, weaknesses, and author information. Do not retain or expose the short-lived bearer token in exports or reports.
- [Combine/pro-day dataset schema](https://github.com/array-carpenter/nfl-draft-data/blob/master/docs/SCHEMAS.md): actual CSVs include hand size, arm length, height/weight, forty, splits, bench, jumps, shuttle, three-cone, and wingspan. The combined data includes ESPN athlete IDs; official and combined NFL identifiers are not always the same kind of identifier.
- [nflverse combine documentation](https://nflreadr.nflverse.com/reference/load_combine.html): use historical PFR-backed results as a secondary measurement source with their own attribution.
- Combine-only data has no 2021 rows. Event labels must follow actual event/source information.
- Preliminary exact normalized year/name joins: 2,025 drafted players in combine-only data; 2,304 in the combined dataset. Alias resolution and identity validation remain outstanding.
- Some NFL records have biography but no scouting overview/strengths/weaknesses. Missing narrative is a real source gap.

## College statistics
- Tested endpoint: https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/{college_athlete_id}/stats
- Tested IDs: Mahomes 3139477; Garrett 3122132; Ward 4688380; Mendoza 4837248; Dickson 3929851; Elliott 549513.
- categories[].names supplies metric keys; labels/displayNames/descriptions supply presentation metadata. statistics[].season.year, teamId/teamSlug, position, and stats provide season rows. categories[].totals provides source-reported career totals. teams maps school metadata.
- Ward includes Incarnate Word, Washington State, and Miami. Mendoza includes Cal and Indiana. Preserve transfers and pre-draft career seasons.
- College and NFL athlete IDs may differ. Elliott's NFL ID 3050478 returns college 404; college ID 549513 works.
- Exclude synthetic season totals and all-star-team rows when constructing season tables; do not double-count them.
- Historical defensive statistics differ by provider. Garrett's ESPN tackle total is 143 versus 145 at Sports Reference; keep each source intact.
- Core ESPN defensive endpoints expose misleading default-zero fields. Do not infer missing TFL/pass-breakup production from zero placeholders.
- Public sportsdataverse player-box release files were verified for 2016 and 2025: https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_player_box/player_box_{season}.csv.gz . These help resolve IDs and supplement individual games, but incomplete historical coverage cannot be presented as full-season totals.
- Anonymous CFBD player-season statistics returned 401; no paid/credentialed data dependency has been introduced.

## Offensive-line and specialist gaps
- Quenton Nelson's ESPN college athlete record exists but its statistics endpoint returns 404. Ordinary counting-stat tables do not supply OL starts or blocking grades.
- [Notre Dame's Nelson final bio](https://fightingirish.com/wp-content/uploads/2019/08/42673__m_footbl_2017_18_misc_non_event__Quenton_Nelson_Final_Bio.pdf) supplies 37 appearances/36 starts and senior-year snaps, plus specifically attributed blocking statistics. School bios require player-level retrieval and extraction.
- Dickson's punting and Elliott's kicking career tables were verified, including useful punt averages and kicking distance buckets.
- Players without college football careers need a distinct not-applicable status, rather than an empty conventional college-career table.

## Workout evidence handling
- Keep official combine results distinct from combined-source or pro-day results.
- Preserve reported timing/event type and source URL for every supplemental result where supplied.
- A workout visit is not evidence of a measured test result. Do not create private results from invitation/visit news.
- Unpublished private workouts and proprietary medical/psychometric data are not publicly retrievable; display gaps honestly.

Raw source snapshots: C:/Users/Derek/.agent-reach/nfl-player-profiles.
