/*
 * Pro Football Reference roster, Pro Bowl, All-Pro and award collector.
 *
 * PFR blocks scripted HTTP clients (Cloudflare), so this runs inside a normal browser tab:
 *   1. Open any https://www.pro-football-reference.com/ page in Chrome.
 *   2. Paste this file into the DevTools console. It fetches ~346 pages same-origin, one every ~3.3 s
 *      (under PFR's 20 requests/minute guideline), and shows progress in window.__pfr.
 *   3. When window.__pfr.status === 'complete', run savePfr() to download pfr-rosters-honors.json.
 *   4. Move the file to ~/.agent-reach/nfl-player-profiles/pfr/pfr-rosters-honors.json and run
 *      collect-nfl-careers.py, build-career-arcs.py, build-site.py, validate-nfl-careers.py.
 *
 * Output arrays (compact):
 *   rosters  [pfrId, season, teamCode, pos, G, GS, AV, age]   players drafted 2017+ only
 *   probowl  [pfrId, season, pos, team, mark, allProString]   mark '%' = selected, did not play; '+' = replacement
 *   allpro   [pfrId, season, pos, team, mark, allProString]   allProString includes "AP: 1st Tm" / "AP: 2nd Tm"
 *   awards   [awardSlug, season, pfrId]
 */
(() => {
  if (window.__pfr && window.__pfr.status === 'running') return 'already running';
  const FIRST = 2017, LAST = 2026, LAST_HONORS = 2025;
  const teams = 'crd atl rav buf car chi cin cle dal den det gnb htx clt jax kan sdg ram rai mia min nwe nor nyg nyj phi pit sea sfo tam oti was'.split(' ');
  const jobs = [];
  for (let season = FIRST; season <= LAST; season++) teams.forEach(t => jobs.push({ kind: 'roster', season, team: t, path: '/teams/' + t + '/' + season + '_roster.htm' }));
  for (let season = FIRST; season <= LAST_HONORS; season++) {
    jobs.push({ kind: 'probowl', season, path: '/years/' + season + '/probowl.htm' });
    jobs.push({ kind: 'allpro', season, path: '/years/' + season + '/allpro.htm' });
  }
  ['ap-nfl-mvp-award', 'ap-offensive-player-of-the-year', 'ap-defensive-player-of-the-year', 'ap-offensive-rookie-of-the-year-award',
   'ap-defensive-rookie-of-the-year-award', 'ap-comeback-player-award', 'super-bowl-mvp-award', 'walter-payton-man-of-the-year']
    .forEach(a => jobs.push({ kind: 'award', award: a, path: '/awards/' + a + '.htm' }));
  const S = window.__pfr = { status: 'running', total: jobs.length, done: 0, errors: [], rosters: [], probowl: [], allpro: [], awards: [], startedAt: new Date().toISOString() };
  // PFR wraps secondary tables in HTML comments; strip them before parsing.
  const parse = html => new DOMParser().parseFromString(html.replace(/<!--|-->/g, ''), 'text/html');
  const pid = cell => { const a = cell && cell.querySelector('a[href*="/players/"]'); const m = a && a.getAttribute('href').match(/\/players\/[A-Z]\/([^/]+)\.htm/); return m ? m[1] : null; };
  const txt = (tr, stat) => { const c = tr.querySelector('[data-stat="' + stat + '"]'); return c ? c.textContent.trim() : ''; };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  window.savePfr = () => {
    const blob = new Blob([JSON.stringify(S)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'pfr-rosters-honors.json'; a.click();
  };
  (async () => {
    for (const job of jobs) {
      let ok = false;
      for (let attempt = 0; attempt < 4 && !ok; attempt++) {
        try {
          const r = await fetch(job.path, { credentials: 'include' });
          if (r.status === 429) { await sleep(65000); continue; }
          if (r.status === 404) { S.errors.push(job.path + ' 404'); ok = true; break; }
          if (!r.ok) throw new Error('HTTP ' + r.status);
          const d = parse(await r.text());
          if (job.kind === 'roster') {
            const seen = new Set();
            d.querySelectorAll('table#roster tbody tr').forEach(tr => {
              const id = pid(tr.querySelector('[data-stat="player"]')); if (!id || seen.has(id)) return; seen.add(id);
              const dy = (txt(tr, 'draft_info').match(/(\d{4})$/) || [])[1];
              if (!dy || Number(dy) < FIRST) return;
              S.rosters.push([id, job.season, job.team, txt(tr, 'pos'), txt(tr, 'g'), txt(tr, 'gs'), txt(tr, 'av'), txt(tr, 'age')]);
            });
            if (!seen.size) throw new Error('empty roster');
          } else if (job.kind === 'probowl' || job.kind === 'allpro') {
            const table = d.querySelector(job.kind === 'probowl' ? 'table#pro_bowl' : 'table#all_pro');
            if (!table) throw new Error('missing table');
            const seen = new Set();
            table.querySelectorAll('tbody tr').forEach(tr => {
              const cell = tr.querySelector('[data-stat="player"]'); const id = pid(cell); if (!id) return;
              const key = id + '|' + txt(tr, 'pos'); if (seen.has(key)) return; seen.add(key);
              const mark = (cell.textContent.trim().match(/[%+*]+$/) || [''])[0];
              (job.kind === 'probowl' ? S.probowl : S.allpro).push([id, job.season, txt(tr, 'pos'), txt(tr, 'team'), mark, txt(tr, 'all_pro_string')]);
            });
          } else {
            d.querySelectorAll('table tbody tr').forEach(tr => {
              const year = (tr.children[0] && tr.children[0].textContent.trim().match(/^(\d{4})/) || [])[1];
              const id = pid(tr); if (year && id && Number(year) >= FIRST) S.awards.push([job.award, Number(year), id]);
            });
          }
          ok = true;
        } catch (e) { if (attempt === 3) S.errors.push(job.path + ' ' + e.message); else await sleep(8000); }
      }
      S.done++;
      await sleep(3300);
    }
    S.status = 'complete'; S.finishedAt = new Date().toISOString();
  })();
  return 'started ' + jobs.length + ' jobs';
})();
