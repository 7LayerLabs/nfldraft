# NFL Draft History: 2017–2026

## Problem Statement
Compile every selection from the ten most recent completed NFL drafts with Round, Pick, Team (via), Selection, Position, and College. Present a clean expandable section for each year.

## Plan
- [x] Confirm the ten-year range and overall-pick convention.
- [x] Retrieve all ten draft records, including published trade chains.
- [x] Validate annual selection totals, sequential overall picks, and all seven rounds.
- [x] Resolve players drafted without a college football background.
- [x] Create the expandable year-by-year tables and attach source links.
- [x] Verify every year opens correctly and displays every selection.
- [x] Record the final results and limitations.

## Progress Notes
- Derek requested the compilation and then instructed the work to resume.
- Collected 2,569 selections: 253, 256, 254, 255, 259, 262, 259, 257, 257, and 257 for 2017 through 2026 respectively.
- Raw source snapshots and the extraction script are retained in C:/Users/Derek/.agent-reach/nfl-draft-history.
- Historical team names are preserved. Pick means overall pick, not the ordinal within a round.
- Via entries preserve the source's original-team and intermediary-team wording.

## Review
- Delivered `nfl-draft-history.html`, an inline interactive table with ten year dropdowns and all 2,569 selections. Six displayed columns match Derek's request.
- Each year contains all seven rounds in overall-pick order and a link to its draft record and trade notes.
- Verified all ten dropdowns, their complete selection counts, first/last picks, seven round groups, six column headings, and exclusive year expansion in Microsoft Edge.
- Layout checks passed at 736px and 320px. Wide tables scroll horizontally inside their table wrapper on small screens. No outer horizontal overflow or JavaScript errors.
- 2026 team assignments and selections were cross-checked against the NFL's 257-entry high-school list. Source typos were not copied; confirmed draft-day position/name corrections are recorded in `build.py`.
- Position abbreviations T and G are displayed as OT and OG. Retained more specific labels from draft records when NFL publications use different position labels.
- No-college entries include Jordan Mailata, Qwan'tez Stiggers, Travis Clayton, and Uar Bernard.
- Kept `drafts.json` and `nfl-drafts-2017-2026.csv` locally for subsequent NFL analysis.
- Coverage is the annual regular NFL draft; supplemental drafts and forfeited/unmade selections are outside the selection tables.

## Localhost delivery
- [x] Render the inline table as a standalone page under local/index.html.
- [x] Start a background Python HTTP server bound to 127.0.0.1 on port 8766.
- [x] Open http://localhost:8766/ in Chrome and verify the ten year dropdowns and 2,569-selection count are visible.
- Server process ID is stored in server.pid; startup logs are in server.stdout.log and server.stderr.log.

## Design revision
The initial localhost page reused the compact conversation visualization. Derek rejected its appearance. Replace it with a full-width standalone sports archive on the existing localhost URL.

### Plan
- [x] Inspect the current page and data; read frontend-design guidance.
- [x] Establish the visual direction and create a standalone template with a deliberate type scale and spacious layout.
- [x] Add team logos, prominent year dropdowns, round navigation, and readable six-column tables, with 2026 initially open.
- [x] Preserve all 2,569 picks and source links; add useful search and team/position filters.
- [x] Verify desktop/mobile layout, complete draft coverage, year expansion, round navigation, filters, and accessibility.
- [x] Refresh the existing Chrome localhost tab and record the design review.

### Design brief
- Subject: an NFL draft reference archive for browsing picks across a decade.
- Layout: full-width header, compact introduction, year accordion; expanded year shows a left round rail and wide selection table.
- Type: Barlow Condensed for football-scale display headings; Barlow for controls and player/team text.
- Dark direction: navy #142438, deep navy #0D1929, slate #203348, paper #F4F7FB, secondary #AFBED0, red #E45050.
- Light direction: paper #F5F7FA, white #FFFFFF, navy #152B45, secondary #65768A, line #DCE3EB, red #C73D44.
- Principles: real draft content appears immediately; logos identify teams; round and pick numbers structure the table; no decorative metric cards or generic landing-page hero.
- Contrast with the failed page: give actual content the primary surface instead of presenting ten empty disclosure rows inside a narrow iframe.

### Revision review
- Replaced the localhost iframe export with a full standalone page built from site-template.html and build-site.py.
- Dark navy sports archive with a light-mode option, locally served Barlow/Barlow Condensed fonts, and 32 team logos.
- All years have native dropdown headers and quick year navigation; 2026 starts expanded. Six original data columns remain present.
- Added round selection, player/college/team search, team and position filters, clear-filters control, source links, and a working CSV download.
- Browser checks passed for each year's full selection count and seven rounds, overall first/last picks, Round 1 filtering, Mendoza search, Philadelphia team filter, QB position filter, reset behavior, and both themes.
- Visual review completed at the browser's normal desktop width and 390px; outer overflow checks passed at 390px and 320px. Table overflow stays inside the horizontal table region.
- Existing localhost:8766 Chrome tab refreshed and retained. Screenshot saved as redesign-desktop.png.
- Chrome's logs retain messages from extensions and the previous iframe; no application script failure was observed during the redesign checks.

## Player profiles: workout data, college production, and scouting

### Problem statement
Enrich every one of the 2,569 drafted players from 2017–2026. Each player opens a profile showing position-relevant measurements and drills, separately identified workout evidence, college season/career statistics, a factual college-career summary, and a brief sourced pre-draft scouting report. Preserve the current draft archive and localhost URL.

### Source findings
- Downloaded and inspected current nflverse combine and draft-pick releases. Draft records include stable overall-pick identifiers, PFR player IDs, and college player IDs. Combine releases cover 2017–2026.
- Downloaded and inspected array-carpenter/nfl-draft-data's combine-only and combined combine/pro-day CSVs. Both include arm length and hand size; the combine-only records include NFL prospect UUIDs, draft grades/projections/comparisons; the combined records include ESPN athlete IDs.
- The combine-only dataset has no 2021 rows; do not treat 2021 mixed workout records as official combine results.
- Mixed-source values differ from combine-only records in some fields; preserve source attribution and do not overwrite verified combine results silently.
- ESPN's public college athlete statistics endpoint successfully returned season/career records for Patrick Mahomes, Myles Garrett, Cam Ward, and Fernando Mendoza, including transfers and FCS seasons where ESPN provides them.
- NFL.com prospect narratives and publicly reported pro-day/private-workout evidence are being investigated. Unpublished private measurements cannot be recovered from public sources.

### Plan for verification (approved and completed)
- [x] Inspect the existing archive, available dependencies, and source schemas; assign source investigations to API specialists.
- [x] Derek approved implementation and full collection: GO AND BUILD! DONT STOP TIL COMPLETED.
- [x] Define stable IDs from draft year and pick; join measurements using aliases, colleges and NFL/ESPN identifiers; produce coverage reports.
- [x] Collect combine and supplemental values with units/events/sources; highlight position-relevant fields and retain all other measurements.
- [x] Collect college seasons/totals, preserving labels, transfers and pre-draft cutoff; supplement OL participation and identify no-college cases.
- [x] Collect brief attributed pre-draft strength/concern excerpts and links to full reports; label missing scouting.
- [x] Add sourced pro-day/private-workout facts; separate scheduled visits, completed events and published numerical results.
- [x] Add all clickable profiles, direct URLs, sections and archive back navigation on localhost.
- [x] Build cached collectors with bounded concurrency/retries, public-source bootstrap and CSV/JSON/ZIP exports.
- [x] Validate all 2,569 profile identities, units, source links and season cutoffs; verify representative data and desktop/mobile browser flows.
- [x] Publish current data to localhost and document actual coverage/gaps.

### Position priorities
- QB: hand size, height/weight, arm length, movement testing; passing completion rate, attempts, yards, TD/INT and rushing production.
- WR/TE: 20-yard shuttle, three-cone, 40-yard dash and splits, vertical/broad jump, hands and arm length; receiving and rushing production where relevant.
- OL: arm length/wingspan, hands, height/weight, bench, shuttle and three-cone; starts/experience from sourced bios, with blocking grades/pressures only where published.
- RB/FB: 40/splits, jumps, shuttle/cone, strength and size; rushing, receiving, and return production where available.
- EDGE/DL/LB: arm length, size, bench, jumps, splits/cone/shuttle; tackles, tackles for loss, sacks, forced fumbles and coverage production where supplied.
- CB/S: speed/splits, shuttle/cone, jumps, height/length; tackles, interceptions, pass breakups and return production where supplied.
- K/P/LS: size and role-specific college production, including kicking accuracy/distance and punting average where published; avoid made-up specialist drills or grades.

### Implementation notes
- Statistics must be college statistics, not similarly named NFL career columns in nflverse's draft-pick release.
- Missing measurements are missing, not zero. Pro-day timing and combine timing remain distinguishable.
- Summaries describe the player's pre-draft record, not NFL outcomes after the selection.
- Every player receives a profile; complete source coverage is reported separately from profile availability.
- Current status: collected, published and validated. Scouting excerpts are quoted and attributed rather than unsourced film assessments.

### Measurement context and GitHub delivery
- [x] Derek requested measurement info buttons with definitions, positional averages and percentile/top-percent ranges.
- [x] Define all 14 standard measurements/drills using linked primary NFL/team explanations.
- [x] Compute positional distributions with one observation per player; disclose official/mixed-event/size samples and suppress rankings below 20 results.
- [x] Add accessible dialogs on headline cards and every result row, including missing and event-specific readings.
- [x] Verify WR 4.34, WR hand size, OT arms, missing splits, small samples, Escape/focus, themes and 320px mobile.
- [x] Include definitions/distributions in the ZIP; validate all 239 distributions and download integrity.
- [x] Document fresh-clone localhost setup, collection/build commands, source handling and coverage.
- [x] Initialize an isolated project repository and push app/data to https://github.com/7LayerLabs/nfldraft.git; verify remote commit.

### Profile and measurement review
- All 2,569 selections have profiles and source-labelled measurements. 2,527 have brief sourced scouting excerpts; 42 missing reports remain labelled.
- College coverage: 2,118 production tables (2,057 ESPN, 54 NFL biography, seven school/team), 953 additional biography records, 338/447 OL/LS numerical participation records, four no-college players.
- Additional curated workout reports cover 12 players. Visits do not imply unpublished private results. The 2021 event cancellation is respected; mutable prospect body readings are not automatically labelled combine measurements.
- Six inconsistent mixed-source observations were quarantined instead of guessing units or drill labels.
- Browser checks passed ten-year counts/first-last links, filters/back navigation, direct routes, previous/next, real 404/retry, source links, profile tables, both themes and responsive layout.
- Measurement dialogs show definitions, averages/medians/quartiles, sample sizes, midpoint percentiles and top-percent bands. Larger hands/arms rank by size rather than football ability; cross-event estimates are identified.
- Removing smooth scrolling fixed click-position races in archive/profile navigation. Comparisons describe drafted players in this archive rather than all NFL players.
- Raw full narratives, tokens, server logs and personal cache paths are excluded from public data/Git. Public-source bootstrap uses the current user's external cache.
- GitHub delivery: main branch pushed successfully to 7LayerLabs/nfldraft; repository contains only this project, with generated data and local assets ready to serve.

## Position dropdown order
- [x] Apply Derek's order: QB, RB, FB, WR, TE, OT, G, C, DE, DT, LB, CB, S; display the existing OG filter as G.
- [x] Rebuild localhost and verify all ten years' ordered options and 2026 guard filtering (17 guards); retain additional positions after the requested sequence.
- [x] Push the update to GitHub and verify the remote commit.
- Review: G is the visible guard option and retains the original OG data match; no draft records or profile positions were changed. Browser checks passed for every year, including years with no drafted fullback.

### Tackle label and outside-linebacker order
- [x] Change dropdown label OT to T and place OLB directly after LB, retaining the underlying position values for filtering.
- [x] Rebuild localhost, verify T/OLB filtering and order, and push to GitHub.
- Review: 2026 dropdown shows T and LB followed immediately by OLB; T returned 22 tackles and OLB returned five outside linebackers. Underlying source positions remain intact.

## Current NFL team and league status
### Plan (requested by Derek; push to existing GitHub repository when complete)
- [x] Collect current rosters from all 32 NFL and ESPN teams, including reserve/practice-squad statuses; join draft IDs conservatively and report ambiguities.
- [x] Identify supported free-agent/retired/unsigned statuses without inferring retirement from missing roster membership.
- [x] Add Current team after College, source links and snapshot date; preserve drafted team and original draft data.
- [x] Include current membership/status in profiles, CSV and JSON/ZIP exports, with portable refresh/build instructions.
- [x] Validate identities and active/traded/retired/unrostered regression cases, all ten years' seven columns and 320px browser layout.
- [x] Push completed app/data to GitHub, verify the remote commit and record review.

### Review
- Snapshot checked 2026-10-06: 1,583 rostered, 851 free agents, 104 Inactive, 17 confirmed Retired, four Deceased, ten Status unconfirmed. No explicit Unsigned records were returned; no status is invented to fill that category.
- All 32 NFL and ESPN rosters reconcile with zero ambiguous joins/provider disagreements. Includes 138 drafted practice-squad players and supported reserve/IR/PUP memberships. Released/terminated rows and historical athlete team fields do not assign a current team.
- Twenty-one primary status reports are curated; comeback cases are reconciled with current rosters. Incomplete-source retrieval preserves the prior publication.
- All 2,569 profiles and dated CSV rows match the roster snapshot; the complete ZIP includes current-teams.json. Existing identities, college statistics and 57,440 workout observations remain validated.
- Browser checks passed every year's complete counts and nonempty seventh column, sourced retirement/free-agent labels, profile current status, filters/search and mobile horizontal containment. Asset content fingerprints prevent existing tabs from retaining old profile scripts.
- Public reports and refresh instructions are included. Private source responses and anonymous tokens stay outside the repository. Final app/data pushed to 7LayerLabs/nfldraft main branch.

## NFL career stats and position career arcs
### Problem statement
Derek wants every drafted player's NFL career statistics so far, organised by career year (Year 1 = draft season), and a position-by-position view that shows how production and usage develop from Year 1 onward. The analysis must answer when each position typically comes into its own (for example, whether a rookie WR breakout is realistic or whether Year 3/4 is the norm). Draft grading and bust tracking are deferred.

### Source decision
- Pro Football Reference blocks automated access (Cloudflare challenge on direct HTTP, Jina reader, headless and headed Chromium; 2026-10-06).
- Use nflverse public releases: season/weekly player stats from NFL play-by-play, PFR snap counts, PFR advanced passing/rushing/receiving/defense (2018+), schedules for QB starts and records, and PFR draft-page career totals for validation. Every player links to his PFR page via the draft-pick PFR ID.

### Plan
- [x] Shared metric catalogue (career_metrics.py): position groups, per-season metrics, qualifiers for rate stats, milestones.
- [x] collect-nfl-careers.py: cache nflverse inputs outside Git, join all 2,569 picks by draft year + pick (PFR/GSIS IDs), build one row per career year from draft season through 2026 (2026 in progress), including seasons not played.
- [x] Season snap share from PFR snap counts with team snap totals; games at 50%+ snaps as a universal starter measure; PFR games started where published; QB starts/records from schedules.
- [x] build-career-arcs.py: per-position year-by-year distributions (all drafted vs played), milestone rates, same-player year-over-year change, breakout timing for 2017-2021 classes, player grids, CSV and Excel exports.
- [x] Profile NFL career section and a Career Arcs view (position, metric, round group, basis, chart, year table, breakout timing, sortable player grid).
- [x] validate-nfl-careers.py: identity joins, season sequences, spot checks vs PFR, career totals vs PFR draft-page totals.
- [x] Browser QA desktop/mobile, both themes; README/todo update.

### Review
- 2,569 players, 14,093 career-year rows (9,382 with games); 2,364 players have NFL games. 2026 through Week 4. All PFR IDs joined; eight GSIS gaps are players with no NFL games.
- 33/33 PFR spot checks match (Mahomes 2018, Jefferson 2020, Chase 2021, Nacua 2023, Barkley 2018, Watt 2021, Parsons 2021, Gardner 2022, Allen 2020, Butker 2019, Trubisky 2017). Finished careers match PFR draft-page totals exactly for 1,156-1,157 of 1,157 players on passing/rushing/receiving; active-player gaps come from the snapshot week.
- Fixes found in review: nflverse sack yards are negative (ANY/A), traded players' advanced rows use the multi-team total, 17 advanced rows with a different player under the same PFR ID are discarded by age, front-seven grouping follows the NFL role tag, PFR pressure milestones calibrated to PFR scale (edge 30+, interior 20+).
- Browser checks: careers WR/DE/QB/T, profiles with and without games, desktop 1440 and 390 mobile, light theme; no console errors and no horizontal page overflow.
- Known limits: no per-season Pro Bowl/All-Pro/AV; OL have no published starts or sacks allowed (snap-based measures instead); games played counts any snap, so a few special-teams-only games differ from PFR's G.

## Filling the gaps: games, starts, AV, honors, lineman detail
- [x] PFR team rosters 2017-2026 (320 pages), Pro Bowl and All-Pro pages 2017-2025, eight award pages, collected in Derek's Chrome session at under 20 pages/minute (collect-pfr-browser.js); file cached at ~/.agent-reach/nfl-player-profiles/pfr/.
- [x] Official games played and games started for every position (OL included), season AV (blank for the in-progress season), roster position per season, Pro Bowl / AP All-Pro first and second team, AP awards, Super Bowl MVP, Walter Payton MOY.
- [x] Penalty detail from play-by-play: holding, false starts, illegal hands, OPI, DPI, defensive holding, roughing the passer, offsides, unnecessary roughness.
- [x] Pro Bowl milestone for every position; "12+ games started" for OL; honors chips and Honors & value table on profiles; PB/AP badges in the Career Arcs grid; AV in the Excel blocks.
- Review: Pro Bowl and All-Pro counts match PFR career totals for all 2,360 players with totals; weighted career AV within 1 for all 1,132 finished careers; games exact for 1,129/1,132 finished careers (3 where nflverse's draft-page copy disagrees with PFR rosters). Fixed: hyphenated PFR ID (Rock Ya-Sin) missed by the link pattern; comeback players' stale "last season" in the validator.

## Scouting reports: draft-day and current
- [x] Draft-day report for all 2,569: grade rank in class/position (2,550 graded), pick vs grade rank, projection/comparison, athletic percentiles (2,502), college production ranked within class at position (2,093), excerpts + full-report link.
- [x] Current report: status and trend label, AV by season with PB/All-Pro markers, latest season percentiles vs all drafted player-seasons at the position, same-career-year comparison, 2026 so far, ESPN/PFR links.
- Review: copyright stance unchanged (excerpts only, full NFL.com report linked). Verified Jefferson, Sewell, Trubisky, Nacua, Mendoza (no games: PFR 0 G and no snaps), mobile 390px, no console errors.

## Grades, scout write-ups and page reorganization (2026-10-06)
- [x] Archive grades on one 5.0-8.0 scale (build-grades.py): NFL.com shown alongside Archive draft (pre-draft only, pooled ridge model, 2017-2021 graded out of sample), Hindsight (best-3-season AV percentile within position + positional honors floors; provisional under 3 seasons) and Current (last three seasons, roster cap). 2017-2021 Spearman vs hindsight: NFL.com 0.50, archive 0.50, draft slot 0.59.
- [x] Special-teams / return Pro Bowls and All-Pros (KR, PR, RET, ST) stored separately; shown on profiles, excluded from position grades and milestones. PFR count validation still exact.
- [x] Full NFL.com narratives cached privately (collect-scouting-text.py -> ~/.agent-reach/nfl-player-profiles/scouting-text.json); never published.
- [x] write-scouting-copy.py: separate draft (pre-draft facts + NFL.com background) and current (fact sheet) passes via headless Claude CLI, --effort low; rejects shared 6-word sequences with NFL.com text and numbers not in the input; drops stale copy when data changes.
- [x] Profile reorganized: grade cards, tabs (Overview, Scouting, NFL career, Measurements, College, Sources; tab kept in URL), overview cards, one NFL-career table at a time, write-ups atop each report.
- [x] Career Arcs reorganized into views: When they arrive, Year by year, Every player, Grades (sortable grades table, beat-projection column, who-saw-it-coming scorecard).

### Where we left off
- Write-up generation is part-way through (resumable). Cached copy lives in ~/.agent-reach/nfl-player-profiles/writeups.json. The first run was stopped by low system memory (11.8 GB machine); now running with 4 workers, batch 15.
- To finish: `python write-scouting-copy.py` (re-run until it reports 0 batches), then `python write-scouting-copy.py --merge`, then `python build-site.py`, then browser QA of Overview/Scouting tabs with write-ups.
- Until merged, profiles show the data-built summary in place of the write-up.
- Not yet done: commit/push of the merged write-ups.
