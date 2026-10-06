(() => {
  'use strict';
  const archive = document.getElementById('archive-view');
  const profileView = document.getElementById('profile-view');
  const view = document.getElementById('career-view');
  if (!archive || !view) return;
  const SHORT = { QB:'QB', RB:'RB', FB:'FB', WR:'WR', TE:'TE', T:'T', G:'G', C:'C', DE:'EDGE', DT:'IDL', LB:'LB', CB:'CB', S:'S', K:'K', P:'P', LS:'LS' };
  const PLURAL = { QB:'QBs', RB:'RBs', FB:'fullbacks', WR:'WRs', TE:'TEs', T:'tackles', G:'guards', C:'centers', DE:'edge rushers', DT:'interior linemen', LB:'off-ball linebackers', CB:'corners', S:'safeties', K:'kickers', P:'punters', LS:'long snappers' };
  const SINGULAR = { QB:'QB', RB:'RB', FB:'fullback', WR:'WR', TE:'TE', T:'tackle', G:'guard', C:'center', DE:'edge rusher', DT:'interior lineman', LB:'off-ball linebacker', CB:'corner', S:'safety', K:'kicker', P:'punter', LS:'long snapper' };
  const USAGE = new Set(['g','gs','snap50','snap_share','snap_active','side_snaps','st_snaps']);
  const ROLE_GROUPS = new Set(['DE','DT','LB']);
  let index = null;
  let indexPromise = null;
  const groupCache = new Map();
  const state = { group:'WR', metric:null, round:'all', basis:'played', sort:'best', dir:-1, search:'', cls:'', view:'arrive', gsort:'hindsight', gdir:-1 };
  const VIEWS = [['arrive','When they arrive'],['trends','Year by year'],['players','Every player'],['grades','Grades']];
  const FAMILY = { QB:'QB', RB:'RB', FB:'RB', WR:'WR', TE:'TE', T:'OL', G:'OL', C:'OL', DE:'EDGE', DT:'IDL', LB:'LB', CB:'CB', S:'S', K:'ST', P:'ST', LS:'ST' };
  let gradesPromise = null;
  let renderVersion = 0;
  let lastHash = '#careers';

  function el(tag, className, text, parent) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (parent) parent.appendChild(node);
    return node;
  }
  function svg(tag, attrs, parent) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (parent) parent.appendChild(node);
    return node;
  }
  function pct(value, digits = 0) { return value === null || value === undefined ? '' : (value * 100).toFixed(digits) + '%'; }
  function fmt(value, format, compact) {
    if (value === null || value === undefined || Number.isNaN(value)) return '';
    if (format === 'pct') return (value * 100).toFixed(compact ? 0 : 1) + '%';
    if (format === 'dec1') return Number(value).toFixed(1);
    if (format === 'dec2') return Number(value).toFixed(2);
    return Math.round(value).toLocaleString();
  }
  function signed(value, format) {
    if (value === null || value === undefined) return '';
    const text = fmt(Math.abs(value), format === 'int' && !Number.isInteger(value) ? 'dec1' : format);
    return (value > 0 ? '+' : value < 0 ? '-' : '') + text;
  }
  function metricInfo(key) { return index.catalog[key]; }
  function lower(text) { return text.charAt(0).toLowerCase() + text.slice(1); }

  function parseHash() {
    const match = location.hash.match(/^#careers(?:=([A-Z]+))?(?:&(.*))?$/);
    if (!match) return null;
    const params = new URLSearchParams(match[2] || '');
    return { group: match[1] || null, metric: params.get('metric'), round: params.get('round'), basis: params.get('basis'), view: params.get('view') };
  }
  function syncHash() {
    const hash = '#careers=' + state.group + '&view=' + state.view + '&metric=' + state.metric + '&round=' + state.round + '&basis=' + state.basis;
    lastHash = hash;
    if (location.hash !== hash) history.replaceState(null, '', hash);
  }
  function setNav(active) {
    document.querySelectorAll('[data-nav]').forEach(link => {
      if (link.dataset.nav === active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
  }
  function loadIndex() {
    if (!indexPromise) indexPromise = fetch('data/careers/index.json').then(response => {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    }).then(data => (index = data)).catch(error => { indexPromise = null; throw error; });
    return indexPromise;
  }
  function loadGroup(key) {
    if (!groupCache.has(key)) groupCache.set(key, fetch('data/careers/' + key + '.json').then(response => {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    }).catch(error => { groupCache.delete(key); throw error; }));
    return groupCache.get(key);
  }

  async function show(params) {
    archive.hidden = true; profileView.hidden = true; view.hidden = false; setNav('careers');
    document.title = 'Career Arcs | NFL Draft Archive';
    const version = ++renderVersion;
    if (!index) { view.replaceChildren(); el('div', 'career-loading', 'Loading career arcs...', view); }
    try {
      await loadIndex();
      if (version !== renderVersion) return;
      const keys = index.groups.map(group => group.key);
      const previousGroup = state.group;
      state.group = keys.includes(params.group) ? params.group : (keys.includes(state.group) ? state.group : 'WR');
      if (state.group !== previousGroup) { state.sort = 'best'; state.dir = -1; state.search = ''; state.cls = ''; }
      state.round = index.roundBuckets[params.round] ? params.round : state.round;
      state.basis = ['all', 'played'].includes(params.basis) ? params.basis : state.basis;
      state.view = VIEWS.some(([key]) => key === params.view) ? params.view : state.view;
      const data = await loadGroup(state.group);
      if (version !== renderVersion) return;
      state.metric = data.metrics.includes(params.metric) ? params.metric : (data.metrics.includes(state.metric) && state.group === previousGroup ? state.metric : data.default);
      render(data);
      syncHash();
    } catch {
      if (version !== renderVersion) return;
      view.replaceChildren();
      const empty = el('div', 'profile-empty', null, view);
      el('strong', '', 'Career arcs could not be loaded', empty);
      el('span', '', 'Serve the app over HTTP (python -m http.server) and retry.', empty);
      const retry = el('button', 'profile-retry', 'Retry', view); retry.type = 'button';
      retry.addEventListener('click', () => show(parseHash() || {}));
    }
  }
  function hide() {
    if (view.hidden) return;
    ++renderVersion;
    view.hidden = true;
    const hash = location.hash;
    if (hash === '' || hash === '#' || hash === '#archive') { archive.hidden = false; setNav('archive'); }
  }
  function route() {
    const params = parseHash();
    if (params) show(params);
    else { hide(); if (!/^#player=/.test(location.hash)) setNav('archive'); else setNav(''); }
  }

  function render(data) {
    const scrollY = window.scrollY;
    const fresh = view.dataset.group !== data.key;
    view.dataset.group = data.key;
    view.replaceChildren();
    const intro = el('section', 'career-intro', null, view);
    const text = el('div', '', null, intro);
    el('h1', '', 'Career Arcs', text).id = 'career-title';
    el('p', '', 'How drafted players develop, season by season. Year 1 is the draft season. Trends use completed seasons from 2017 to ' + index.lastCompletedSeason + '; the ' + index.inProgress.season + ' season (through Week ' + index.inProgress.throughWeek + ') appears in player rows only.', text);
    const coverage = el('div', 'coverage', null, intro);
    el('strong', '', index.totalPlayers.toLocaleString() + ' drafted players', coverage);
    el('span', '', 'Regular season · data as of ' + index.asOf, coverage);
    const nav = el('nav', 'career-positions', null, view); nav.setAttribute('aria-label', 'Choose a position');
    index.groups.forEach(group => {
      const button = el('button', 'career-position', null, nav); button.type = 'button';
      button.setAttribute('aria-pressed', String(group.key === data.key));
      button.setAttribute('aria-label', group.label + ', ' + group.players + ' players');
      el('span', 'pos-key', SHORT[group.key] || group.key, button);
      el('span', 'pos-count', group.players, button);
      button.addEventListener('click', () => { location.hash = '#careers=' + group.key + '&view=' + state.view + '&round=' + state.round + '&basis=' + state.basis; });
    });
    const heading = el('div', 'career-heading', null, view);
    el('h2', '', data.label, heading);
    const bucket = data.buckets[state.round];
    el('span', '', bucket.players + ' drafted players' + (state.round !== 'all' ? ' in ' + bucket.label.toLowerCase() : '') + ' · ' +
      (ROLE_GROUPS.has(data.key) ? 'grouped by NFL role (edge, interior, off-ball) where tagged, otherwise draft position' : 'drafted as ' + data.positions.filter(p => p !== 'CB / WR').join(' / ')), heading);
    renderControls(data);
    const tabs = el('div', 'career-views', null, view); tabs.setAttribute('role', 'tablist'); tabs.setAttribute('aria-label', 'Career arcs views');
    VIEWS.forEach(([key, label]) => {
      const button = el('button', 'career-view-tab', label, tabs); button.type = 'button'; button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', String(state.view === key));
      button.addEventListener('click', () => { state.view = key; render(data); syncHash(); });
    });
    if (state.view === 'arrive') renderAnswer(data);
    else if (state.view === 'trends') renderTrend(data);
    else if (state.view === 'players') renderGrid(data);
    else renderGrades(data);
    renderMethod(data);
    if (fresh) window.scrollTo({ top: 0, behavior: 'instant' }); else window.scrollTo({ top: scrollY, behavior: 'instant' });
  }

  function renderControls(data) {
    const bar = el('div', 'career-controls', null, view);
    const metricWrap = el('label', 'career-control', null, bar);
    if (state.view === 'grades') metricWrap.hidden = true;
    el('span', 'career-control-label', 'Metric', metricWrap);
    const select = el('select', 'filter-select', null, metricWrap);
    const groups = [['Playing time', key => USAGE.has(key)], ['Production', key => !USAGE.has(key) && metricInfo(key).kind === 'count'], ['Efficiency & usage rates', key => !USAGE.has(key) && metricInfo(key).kind === 'rate']];
    groups.forEach(([label, test]) => {
      const keys = data.metrics.filter(test);
      if (!keys.length) return;
      const optgroup = el('optgroup', '', null, select); optgroup.label = label;
      keys.forEach(key => { const option = el('option', '', metricInfo(key).label, optgroup); option.value = key; });
    });
    select.value = state.metric;
    select.addEventListener('change', () => { state.metric = select.value; if (state.sort !== 'name' && state.sort !== 'draft') state.sort = 'best'; render(data); syncHash(); });
    const roundWrap = el('div', 'career-control', null, bar);
    el('span', 'career-control-label', 'Drafted in', roundWrap);
    const rounds = el('div', 'segmented', null, roundWrap); rounds.setAttribute('role', 'group'); rounds.setAttribute('aria-label', 'Draft round group');
    Object.entries(index.roundBuckets).forEach(([key, label]) => {
      const button = el('button', '', label.replace('Rounds ', 'Rd ').replace('Round ', 'Rd ').replace('All rounds', 'All'), rounds); button.type = 'button';
      button.setAttribute('aria-label', label); button.setAttribute('aria-pressed', String(state.round === key));
      button.addEventListener('click', () => { state.round = key; render(data); syncHash(); });
    });
    const rate = metricInfo(state.metric).kind === 'rate';
    const basisWrap = el('div', 'career-control', null, bar);
    if (state.view === 'grades' || state.view === 'arrive') basisWrap.hidden = true;
    el('span', 'career-control-label', 'Averages include', basisWrap);
    const basis = el('div', 'segmented', null, basisWrap); basis.setAttribute('role', 'group'); basis.setAttribute('aria-label', 'Averaging basis');
    [['all', 'All drafted'], ['played', 'Only players who played']].forEach(([key, label]) => {
      const button = el('button', '', label, basis); button.type = 'button'; button.disabled = rate;
      button.setAttribute('aria-pressed', String(!rate && state.basis === key));
      button.title = key === 'all' ? 'Every drafted player whose class has reached that year. A season without games counts as zero.' : 'Only players who appeared in at least one game that season.';
      button.addEventListener('click', () => { state.basis = key; render(data); syncHash(); });
    });
    if (rate && state.view !== 'grades') {
      const q = metricInfo(state.metric).qualifier;
      el('span', 'career-control-note', 'Rate stat: qualified seasons only' + (q ? ' (' + q.minimum + '+ ' + (metricInfo(q.metric)?.short || q.metric).toLowerCase() + ')' : ''), bar);
    }
  }

  function modeIndex(counts) {
    let best = -1, at = -1;
    counts.forEach((count, i) => { if (count > best) { best = count; at = i; } });
    return best > 0 ? at : -1;
  }
  function renderAnswer(data) {
    const bucket = data.buckets[state.round];
    const panel = el('section', 'career-panel', null, view); panel.setAttribute('aria-labelledby', 'answer-heading');
    const head = el('div', 'career-panel-head', null, panel);
    el('h3', '', 'When do ' + PLURAL[data.key] + ' arrive?', head).id = 'answer-heading';
    const classes = index.timing.classes;
    el('span', '', 'Breakout timing uses the ' + classes[0] + '-' + classes[1] + ' classes, which have five completed seasons', head);
    const body = el('div', 'career-panel-body', null, panel);
    const grid = el('div', 'career-answer', null, body);
    const notes = el('ul', 'career-takeaways', null, grid);
    const label = PLURAL[data.key];
    const lead = bucket.timing[0];
    const say = (parent, parts, caution) => {
      const li = el('li', caution ? 'is-caution' : '', null, parent);
      parts.forEach(part => typeof part === 'string' ? li.append(part) : el('strong', '', part[0], li));
    };
    if (lead) {
      const reached = lead.firstYear.reduce((a, b) => a + b, 0);
      if (lead.cohort && reached) {
        const mode = modeIndex(lead.firstYear);
        say(notes, [[reached + ' of ' + lead.cohort], ' ' + label + ' drafted ' + lead.classes[0] + '-' + lead.classes[1] + ' reached ', [lower(lead.label)], ' within five seasons (' + pct(reached / lead.cohort) + ').']);
        say(notes, ['Most common first time: ', ['Year ' + (mode + 1)], ' (' + pct(lead.firstYear[mode] / reached) + ' of those who got there). As rookies: ', [pct(lead.firstYear[0] / reached)], '. By the end of Year 2: ' + pct((lead.firstYear[0] + lead.firstYear[1]) / reached) + '; by Year 3: ' + pct((lead.firstYear[0] + lead.firstYear[1] + lead.firstYear[2]) / reached) + '.']);
      } else if (lead.cohort) {
        say(notes, ['None of the ' + lead.cohort + ' ' + label + ' in this group reached ', [lower(lead.label)], ' within five seasons.'], true);
      }
    }
    const peak = bucket.peaks[state.metric];
    const info = metricInfo(state.metric);
    if (peak && peak.established.cohort) {
      const counts = peak.established.counts;
      const total = counts.reduce((a, b) => a + b, 0);
      const mode = modeIndex(counts);
      if (total) say(notes, ['Among those established players, the best ' + lower(info.label) + ' season in Years 1-5 came most often in ', ['Year ' + (mode + 1)], ' (' + pct(counts[mode] / total) + '); ' + (counts[0] ? 'only ' + pct(counts[0] / total) + ' peaked as rookies.' : 'none of them peaked as rookies.')]);
    }
    const rates = bucket.milestones[0];
    if (rates) {
      const usable = rates.years.filter(y => y.cohort >= index.minimumSample && y.rate !== null);
      if (usable.length) {
        const top = usable.reduce((a, b) => (b.rate > a.rate ? b : a));
        const first = rates.years[0];
        say(notes, ['Share of ', ['all'], ' drafted ' + label + ' with ' + lower(rates.label) + ' in a given season: ', [pct(first.rate, 1) + ' in Year 1'], ', peaking at ', [pct(top.rate, 1) + ' in Year ' + top.cy], '.']);
      }
    }
    const change = bucket.change[state.metric];
    if (change && info.kind === 'count') {
      const positive = change.filter(c => c.n >= index.minimumSample && c.median !== null);
      if (positive.length) {
        const growth = positive.filter(c => (info.lowerIsBetter ? c.median < 0 : c.median > 0));
        const last = growth.length ? growth[growth.length - 1] : null;
        if (last) say(notes, ['Same-player growth: the typical ' + SINGULAR[data.key] + ' who played both seasons still improved his ' + lower(info.label) + ' through ', ['Year ' + last.cy], ' (median change ' + signed(last.median, info.format) + ' from Year ' + (last.cy - 1) + ').']);
      }
    }
    if (bucket.players < index.minimumSample) say(notes, ['Small sample: only ' + bucket.players + ' players. Treat percentages as anecdotes.'], true);
    const side = el('div', '', null, grid);
    const timingGroup = el('div', 'timing-group', null, side);
    el('p', 'timing-caption', 'First season reaching each milestone, as a share of players who reached it within five years.', timingGroup);
    const table = el('table', 'timing-table', null, el('div', 'timing-scroll', null, timingGroup));
    el('caption', 'sr-only', 'First season reaching each milestone', table);
    const header = table.createTHead().insertRow();
    ['Milestone', 'Reached', 'Y1', 'Y2', 'Y3', 'Y4', 'Y5'].forEach(text => { const th = el('th', '', text, header); th.scope = 'col'; });
    const tbody = table.createTBody();
    bucket.timing.forEach(milestone => {
      const row = tbody.insertRow();
      const th = el('th', '', milestone.label, row); th.scope = 'row';
      const reached = milestone.firstYear.reduce((a, b) => a + b, 0);
      const cell = el('td', 'timing-reached', milestone.cohort ? pct(reached / milestone.cohort) : '', row);
      cell.title = reached + ' of ' + milestone.cohort + ' players (' + milestone.classes.join('-') + ' classes)';
      timingCells(row, milestone.firstYear, reached);
    });
    if (peak) {
      const peakGroup = el('div', 'timing-group', null, side);
      el('p', 'timing-caption', 'Season of career-best ' + lower(info.label) + ' within Years 1-5 (share of players).', peakGroup);
      const peakTable = el('table', 'timing-table', null, el('div', 'timing-scroll', null, peakGroup));
      el('caption', 'sr-only', 'Season of career-best ' + info.label, peakTable);
      const peakHead = peakTable.createTHead().insertRow();
      ['Players', 'n', 'Y1', 'Y2', 'Y3', 'Y4', 'Y5'].forEach(text => { const th = el('th', '', text, peakHead); th.scope = 'col'; });
      const peakBody = peakTable.createTBody();
      [['Reached ' + lower(peak.establishedBy), peak.established], ['Everyone who recorded any', peak.all]].forEach(([labelText, values]) => {
        const row = peakBody.insertRow(); const th = el('th', '', labelText, row); th.scope = 'row';
        const total = values.counts.reduce((a, b) => a + b, 0);
        el('td', 'timing-reached', total, row);
        timingCells(row, values.counts, total);
      });
    } else {
      el('p', 'career-panel-note', 'Career-best timing is shown for counting stats. Rate stats change with playing time, so pick a counting stat to see when players peak.', side);
    }
  }
  function timingCells(row, counts, total) {
    const mode = modeIndex(counts);
    const max = Math.max(...counts, 1);
    counts.forEach((count, i) => {
      const td = el('td', '', null, row);
      const span = el('span', 'timing-cell' + (i === mode ? ' is-mode' : ''), total ? pct(count / total) : '', td);
      if (count) { span.style.background = 'color-mix(in srgb, var(--red) ' + Math.round(12 + 58 * count / max) + '%, transparent)'; span.classList.add('has-bar'); }
      td.title = count + ' of ' + total + ' in Year ' + (i + 1);
    });
  }

  function niceMax(value, format) {
    if (format === 'pct') return Math.min(1, Math.ceil(value * 10) / 10 || .1);
    if (value <= 0) return 1;
    const power = Math.pow(10, Math.floor(Math.log10(value)));
    const scaled = value / power;
    const step = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 2.5 ? 2.5 : scaled <= 5 ? 5 : 10;
    return step * power;
  }
  function renderTrend(data) {
    const bucket = data.buckets[state.round];
    const info = metricInfo(state.metric);
    const rate = info.kind === 'rate';
    const basis = rate ? 'all' : state.basis;
    const years = bucket.stats[state.metric][basis];
    const panel = el('section', 'career-panel', null, view); panel.setAttribute('aria-labelledby', 'trend-heading');
    const head = el('div', 'career-panel-head', null, panel);
    el('h3', '', info.label + ' by career year', head).id = 'trend-heading';
    el('span', '', rate ? 'Qualified seasons only' : basis === 'all' ? 'All drafted players (no games = 0)' : 'Players who appeared that season', head);
    const body = el('div', 'career-panel-body', null, panel);
    el('p', 'timing-caption', info.description + (info.chartedFrom2018 ? ' Charting starts in 2018, so 2017 seasons are excluded.' : ''), body);
    const wrap = el('div', 'arc-chart-wrap', null, body);
    const legend = el('div', 'arc-legend', null, wrap);
    [['legend-p90', 'Top 10% (90th percentile)'], ['legend-p75', '75th percentile'], ['legend-median', 'Median'], ['legend-mean', 'Average', true]].forEach(([cls, label, dashed]) => {
      const item = el('span', cls, null, legend); el('i', dashed ? 'is-dashed' : '', null, item); el('span', '', label, item).style.color = 'var(--secondary)';
    });
    drawChart(wrap, years, info, data);
    const scroll = el('div', 'arc-table-scroll', null, body); scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', info.label + ' year-by-year table');
    const table = el('table', 'arc-table', null, scroll);
    el('caption', 'sr-only', info.label + ' by career year for ' + data.label, table);
    const header = table.createTHead().insertRow();
    const corner = el('th', '', 'Career year', header); corner.scope = 'col';
    years.forEach(year => { const th = el('th', '', 'Year ' + year.cy, header); th.scope = 'col'; });
    const tbody = table.createTBody();
    const small = year => (year.n || 0) < index.minimumSample;
    const addRow = (label, values, opts = {}) => {
      const row = tbody.insertRow(); if (opts.key) row.className = 'is-key';
      const th = el('th', '', label, row); th.scope = 'row'; if (opts.title) th.title = opts.title;
      values.forEach((value, i) => { const td = el('td', '', value, row); if (opts.small?.[i]) td.classList.add('is-small'); if (opts.best === i) td.classList.add('is-best'); });
    };
    const section = text => { const row = tbody.insertRow(); row.className = 'section-row'; const th = el('th', '', text, row); th.scope = 'rowgroup'; years.forEach(() => el('td', '', '', row)); };
    const smallFlags = years.map(small);
    addRow('Players whose class reached this year', years.map(y => y.cohort.toLocaleString()));
    addRow('Played at least one game', years.map(y => y.cohort ? pct(y.played / y.cohort) : ''));
    addRow(rate ? 'Qualified seasons' : basis === 'all' ? 'Players in average' : 'Players who played', years.map(y => (y.n || 0).toLocaleString()), { small: smallFlags });
    const medians = years.map(y => (small(y) ? null : y.median));
    const bestMedian = medians.reduce((best, value, i) => (value === null ? best : best === -1 || (info.lowerIsBetter ? value < medians[best] : value > medians[best]) ? i : best), -1);
    addRow('Average', years.map(y => fmt(y.mean, info.format)), { small: smallFlags });
    addRow('Median', years.map(y => fmt(y.median, info.format)), { small: smallFlags, key: true, best: bestMedian });
    addRow('75th percentile', years.map(y => fmt(y.p75, info.format)), { small: smallFlags });
    addRow('Top 10% starts at (90th)', years.map(y => fmt(y.p90, info.format)), { small: smallFlags });
    addRow('Best season', years.map(y => fmt(y.max, info.format)), { small: smallFlags });
    const change = bucket.change[state.metric];
    if (change) {
      section('Same player, year over year (played both seasons)');
      addRow('Median change from prior year', ['', ...change.map(c => signed(c.median, info.format))], { small: [false, ...change.map(c => c.n < index.minimumSample)], title: 'Removes survivor bias: compares each player with himself.' });
      addRow('Improved vs prior year', ['', ...change.map(c => pct(c.improved))], { small: [false, ...change.map(c => c.n < index.minimumSample)] });
      addRow('Players compared', ['', ...change.map(c => c.n.toLocaleString())]);
    }
    section('Share of all drafted ' + PLURAL[data.key] + ' reaching each milestone');
    bucket.milestones.forEach(milestone => {
      const rates = milestone.years.map(y => y.rate);
      const smallRows = milestone.years.map(y => y.cohort < index.minimumSample);
      const best = rates.reduce((b, v, i) => (v === null || smallRows[i] ? b : b === -1 || v > rates[b] ? i : b), -1);
      addRow(milestone.label, rates.map(v => pct(v, 1)), { small: smallRows, best });
    });
    el('p', 'career-panel-note', 'Italic grey values come from fewer than ' + index.minimumSample + ' players. Red marks the strongest year. "All drafted" counts every player whose class has reached that year, so later years also reflect who is still in the league; the same-player rows remove that effect.', body);
  }
  function drawChart(parent, years, info, data) {
    const W = Math.round(Math.max(340, Math.min(1000, parent.clientWidth || 1000))), compact = W < 600, H = compact ? 250 : 300, M = { l: compact ? 46 : 62, r: compact ? 10 : 18, t: 16, b: 50 };
    const series = ['p90', 'p75', 'median', 'mean'];
    const values = years.flatMap(y => series.map(s => y[s])).filter(v => v !== null && v !== undefined);
    const chart = svg('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'arc-chart', role: 'img' }, parent);
    if (!values.length) { svg('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle' }, chart).textContent = 'No qualifying seasons for this selection'; return; }
    const minValue = Math.min(0, ...values);
    const top = niceMax(Math.max(...values), info.format);
    const bottom = minValue < 0 ? -niceMax(-minValue, info.format) : 0;
    const x = i => M.l + (W - M.l - M.r) * (years.length === 1 ? .5 : i / (years.length - 1));
    const y = v => M.t + (H - M.t - M.b) * (1 - (v - bottom) / (top - bottom));
    for (let i = 0; i <= 4; i++) {
      const value = bottom + (top - bottom) * i / 4;
      svg('line', { x1: M.l, x2: W - M.r, y1: y(value), y2: y(value), class: 'grid-line' }, chart);
      svg('text', { x: M.l - 10, y: y(value) + 4, 'text-anchor': 'end' }, chart).textContent = fmt(value, info.format === 'int' ? 'int' : info.format, true);
    }
    years.forEach((year, i) => {
      const smallSample = (year.n || 0) < index.minimumSample;
      const label = svg('text', { x: x(i), y: H - M.b + 22, 'text-anchor': 'middle', class: 'axis-label' + (smallSample ? ' small-sample' : '') }, chart); label.textContent = (compact ? 'Y' : 'Year ') + year.cy;
      svg('text', { x: x(i), y: H - M.b + 40, 'text-anchor': 'middle', class: smallSample ? 'small-sample' : '' }, chart).textContent = (compact ? '' : 'n=') + (year.n || 0);
    });
    series.forEach(name => {
      // Faded line through every point; solid only between years with an adequate sample.
      const points = years.map((year, i) => (year[name] === null || year[name] === undefined ? null :
        { at: x(i).toFixed(1) + ',' + y(year[name]).toFixed(1), ok: (year.n || 0) >= index.minimumSample }));
      let faded = '', solid = '';
      points.forEach((point, i) => {
        if (!point) return;
        faded += (faded && points[i - 1] ? 'L' : 'M') + point.at;
        if (point.ok && points[i + 1]?.ok) solid += 'M' + point.at + 'L' + points[i + 1].at;
      });
      if (faded) svg('path', { d: faded, class: 'series series-' + name + ' series-faded' }, chart);
      if (solid) svg('path', { d: solid, class: 'series series-' + name }, chart);
      years.forEach((year, i) => {
        const value = year[name];
        if (value === null || value === undefined || name === 'mean') return;
        const dot = svg('circle', { cx: x(i), cy: y(value), r: name === 'median' ? 5 : 3.5, class: 'dot dot-' + name + ((year.n || 0) < index.minimumSample ? ' series-faded' : '') }, chart);
        svg('title', {}, dot).textContent = 'Year ' + year.cy + ' ' + name + ': ' + fmt(value, info.format);
      });
    });
    years.forEach((year, i) => {
      const width = (W - M.l - M.r) / Math.max(1, years.length - 1);
      const zone = svg('rect', { x: x(i) - width / 2, y: M.t, width, height: H - M.t - M.b, class: 'hover-zone' }, chart);
      svg('title', {}, zone).textContent = 'Year ' + year.cy + ' (n=' + (year.n || 0) + ')\nMedian ' + fmt(year.median, info.format) + '\n75th ' + fmt(year.p75, info.format) + '\n90th ' + fmt(year.p90, info.format) + '\nAverage ' + fmt(year.mean, info.format);
      chart.insertBefore(zone, chart.firstChild);
    });
    const medians = years.filter(year => (year.n || 0) >= index.minimumSample && year.median !== null && year.median !== undefined);
    chart.setAttribute('aria-label', info.label + ' for ' + data.label + ' by career year. ' + medians.map(year => 'Year ' + year.cy + ' median ' + fmt(year.median, info.format)).join(', ') + '.');
  }

  function renderGrid(data) {
    const info = metricInfo(state.metric);
    const rate = info.kind === 'rate';
    const summable = !rate && info.format !== 'pct';
    const column = data.gridColumns.indexOf(state.metric);
    const panel = el('section', 'career-panel', null, view); panel.setAttribute('aria-labelledby', 'grid-heading');
    const head = el('div', 'career-panel-head', null, panel);
    el('h3', '', 'Every ' + SINGULAR[data.key] + ', year by year', head).id = 'grid-heading';
    el('span', '', info.label + ' · click a column to sort', head);
    const body = el('div', 'career-panel-body', null, panel);
    const toolbar = el('div', 'grid-toolbar', null, body);
    const searchWrap = el('div', 'search-field', null, toolbar);
    searchWrap.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"></circle><path d="m15.5 15.5 5 5"></path></svg>';
    const search = el('input', 'search-input', null, searchWrap); search.type = 'search'; search.placeholder = 'Search player, college or team'; search.value = state.search;
    search.setAttribute('aria-label', 'Search ' + data.label);
    const classSelect = el('select', 'filter-select', null, toolbar); classSelect.setAttribute('aria-label', 'Filter by draft class');
    el('option', '', 'All draft classes', classSelect).value = '';
    [...new Set(data.players.map(p => p.year))].sort((a, b) => b - a).forEach(year => { el('option', '', year + ' class', classSelect).value = String(year); });
    classSelect.value = state.cls;
    const count = el('span', 'result-count', '', toolbar);
    const lowerBetter = info.lowerIsBetter;
    const completed = data.players.flatMap(p => p.s.filter(s => !s[3] && s[2] > 0 && s[column] !== null).map(s => s[column])).sort((a, b) => a - b);
    const rank = value => {
      if (!completed.length || value === null) return 0;
      let lo = 0, hi = completed.length;
      while (lo < hi) { const mid = (lo + hi) >> 1; if (completed[mid] < value) lo = mid + 1; else hi = mid; }
      const p = lo / completed.length;
      return lowerBetter ? 1 - p : p;
    };
    const bucketTest = { all: () => true, r1: r => r === 1, r23: r => r === 2 || r === 3, r47: r => r >= 4 }[state.round];
    const rows = data.players.filter(p => bucketTest(p.round)).map(p => {
      const byYear = new Map(p.s.map(s => [s[0], s]));
      const values = [];
      for (let cy = 1; cy <= index.gridYears; cy++) { const s = byYear.get(cy); values.push(s ? { g: s[2], live: !!s[3], teams: s[4], honor: s[5], value: s[2] > 0 ? s[column] : null, season: s[1] } : null); }
      const done = values.filter(v => v && !v.live && v.g > 0 && v.value !== null).map(v => v.value);
      const all = values.filter(v => v && v.g > 0 && v.value !== null).map(v => v.value);
      const best = all.length ? (lowerBetter ? Math.min(...all) : Math.max(...all)) : null;
      const total = !summable ? null : values.reduce((sum, v) => sum + (v && v.g > 0 && v.value !== null ? v.value : 0), 0);
      return { p, values, best, total, done };
    });
    const scroll = el('div', 'career-grid-scroll', null, body); scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Player grid');
    const table = el('table', 'career-grid', null, scroll);
    el('caption', 'sr-only', info.label + ' by career year for every ' + data.label + ' drafted 2017-2026', table);
    const header = table.createTHead().insertRow();
    const columns = [['name', 'Player'], ['draft', 'Drafted'], ...Array.from({ length: index.gridYears }, (_, i) => ['y' + (i + 1), 'Y' + (i + 1)]), ['best', lowerBetter ? 'Best (low)' : 'Best'], ...(summable ? [['total', 'Total']] : [])];
    columns.forEach(([key, label]) => {
      const th = el('th', '', null, header); th.scope = 'col';
      const button = el('button', '', label, th); button.type = 'button';
      if (key.startsWith('y')) button.title = 'Career year ' + key.slice(1) + ' (Year 1 = draft season)';
      if (state.sort === key) { th.setAttribute('aria-sort', state.dir > 0 ? 'ascending' : 'descending'); el('span', 'sort-arrow', state.dir > 0 ? '▲' : '▼', button); }
      button.addEventListener('click', () => {
        if (state.sort === key) state.dir = -state.dir; else { state.sort = key; state.dir = key === 'name' || key === 'draft' ? 1 : -1; }
        renderBody();
        table.querySelectorAll('thead th').forEach(cell => { cell.removeAttribute('aria-sort'); cell.querySelector('.sort-arrow')?.remove(); });
        th.setAttribute('aria-sort', state.dir > 0 ? 'ascending' : 'descending'); el('span', 'sort-arrow', state.dir > 0 ? '▲' : '▼', button);
      });
    });
    const tbody = table.createTBody();
    function sortValue(row) {
      if (state.sort === 'name') return row.p.name;
      if (state.sort === 'draft') return row.p.year * 1000 + row.p.pick;
      if (state.sort === 'best') return row.best;
      if (state.sort === 'total') return row.total;
      const v = row.values[Number(state.sort.slice(1)) - 1];
      return v && v.g > 0 ? v.value : null;
    }
    function renderBody() {
      const query = state.search.trim().toLocaleLowerCase();
      const visible = rows.filter(row => (!state.cls || String(row.p.year) === state.cls) &&
        (!query || [row.p.name, row.p.college, row.p.team, row.p.pos, ...row.values.map(v => v?.teams || '')].join(' ').toLocaleLowerCase().includes(query)));
      visible.sort((a, b) => {
        const va = sortValue(a), vb = sortValue(b);
        if (va === null || va === undefined) return vb === null || vb === undefined ? a.p.year - b.p.year || a.p.pick - b.p.pick : 1;
        if (vb === null || vb === undefined) return -1;
        if (typeof va === 'string') return va.localeCompare(vb) * state.dir;
        return (va - vb) * state.dir || a.p.year - b.p.year || a.p.pick - b.p.pick;
      });
      const fragment = document.createDocumentFragment();
      visible.forEach(row => {
        const tr = el('tr', '', null, fragment);
        const th = el('th', '', null, tr); th.scope = 'row';
        const link = el('a', '', row.p.name, th); link.href = '#player=' + row.p.id;
        if (row.p.pos !== data.positions[0] || ROLE_GROUPS.has(data.key)) el('span', 'grid-pos', row.p.pos, th);
        el('td', 'grid-draft', row.p.year + ' · R' + row.p.round + ' #' + row.p.pick, tr).title = row.p.team + ' · ' + row.p.college;
        row.values.forEach((v, i) => {
          const td = el('td', '', null, tr);
          if (!v) { td.title = 'Season not reached yet'; return; }
          const where = (v.teams ? v.teams + ' · ' : '') + v.season + (v.live ? ' (in progress)' : '');
          if (v.g === 0) { td.textContent = '--'; td.className = 'cell-dnp'; td.title = 'Did not play in ' + v.season; return; }
          if (v.value === null) { td.textContent = '·'; td.className = 'cell-nq'; td.title = where + ': below the qualifier for this rate (' + v.g + ' games)'; return; }
          td.textContent = fmt(v.value, info.format, info.format === 'pct');
          td.title = where + ', ' + v.g + ' games' + (v.honor ? ' · ' + ({ AP: 'First-team All-Pro', AP2: 'Second-team All-Pro', PB: 'Pro Bowl' })[v.honor] : '');
          if (v.honor) el('sup', 'honor-badge honor-' + v.honor.toLowerCase(), v.honor === 'AP2' ? 'AP' : v.honor, td);
          if (v.live) td.classList.add('cell-live');
          const heat = rank(v.value);
          if (heat > .5) td.style.background = 'color-mix(in srgb, var(--red) ' + Math.round((heat - .5) * 2 * 38) + '%, transparent)';
        });
        el('td', 'grid-summary', fmt(row.best, info.format, info.format === 'pct'), tr);
        if (summable) el('td', 'grid-summary', fmt(row.total, info.format), tr);
      });
      tbody.replaceChildren(fragment);
      count.textContent = visible.length + ' of ' + rows.length + ' players';
    }
    search.addEventListener('input', () => { state.search = search.value; renderBody(); });
    classSelect.addEventListener('change', () => { state.cls = classSelect.value; renderBody(); });
    renderBody();
    const legend = el('div', 'grid-legend', null, body);
    [['PB', 'Pro Bowl'], ['AP', 'All-Pro (red = first team)'], ['--', 'did not play that season'], ['·', 'played, below the rate qualifier'], ['blank', 'season not reached yet'], ['*', index.inProgress.season + ' in progress through Week ' + index.inProgress.throughWeek]].forEach(([mark, text]) => {
      const item = el('span', '', null, legend); el('b', '', mark, item); item.append(' ' + text);
    });
    el('span', '', 'Shading: higher percentile among all completed ' + data.label.toLowerCase() + ' seasons' + (lowerBetter ? ' (lower values shade darker)' : ''), legend);
  }

  function tierClass(grade) {
    if (grade === null || grade === undefined) return 't-none';
    return grade >= 7.5 ? 't-rare' : grade >= 7 ? 't-pb' : grade >= 6.7 ? 't-hes' : grade >= 6.5 ? 't-qs' : grade >= 6.3 ? 't-as' : grade >= 6.1 ? 't-ss' : grade >= 6 ? 't-bu' : grade >= 5.7 ? 't-fr' : 't-dns';
  }
  function gradeCell(tr, value, extra) {
    const td = el('td', 'grade-cell ' + tierClass(value), null, tr);
    if (value === null || value === undefined) { td.textContent = '--'; td.classList.add('cell-dnp'); return td; }
    el('span', 'grade-dot', null, td); td.append(Number(value).toFixed(2) + (extra || ''));
    return td;
  }
  function renderGrades(data) {
    const panel = el('section', 'career-panel', null, view); panel.setAttribute('aria-labelledby', 'grades-heading');
    const head = el('div', 'career-panel-head', null, panel);
    el('h3', '', data.label + ': draft grades vs. how careers turned out', head).id = 'grades-heading';
    el('span', '', 'One 5.0-8.0 scale for every grade', head);
    const body = el('div', 'career-panel-body', null, panel);
    const loading = el('p', 'timing-caption', 'Loading grades...', body);
    if (!gradesPromise) gradesPromise = fetch('data/grades-compact.json').then(r => { if (!r.ok) throw new Error(); return r.json(); }).catch(e => { gradesPromise = null; throw e; });
    const version = renderVersion;
    gradesPromise.then(grades => {
      if (version !== renderVersion) return;
      loading.remove();
      const legend = el('div', 'grade-legend', null, body);
      grades.scale.forEach(tier => { const item = el('span', 'grade-legend-item ' + tierClass(tier.min || 5.0), null, legend); el('span', 'grade-dot', null, item); item.append((tier.min ? tier.min.toFixed(1) + '+ ' : 'Under 5.7 ') + tier.label); });
      const family = FAMILY[data.key];
      const ev = grades.evaluation2017to2021[family];
      const intro = el('div', 'grade-explain', null, body);
      [['NFL.com grade', 'The published pre-draft scouting grade (its scale shifted over the years, so compare within a class).'],
       ['Archive draft grade', 'Our pre-draft grade: NFL.com\'s grade, athletic testing and college production, weighted by how 2017-2021 picks actually turned out. Each of those classes is graded by a model that never saw its own results.'],
       ['Hindsight grade', 'What he turned out to be: his best three seasons of Approximate Value ranked against his position, with Pro Bowls, All-Pros and major awards as floors. Provisional under three seasons.'],
       ['Current grade', 'His level now: the last three seasons of AV (weighted toward the latest), capped for players not on a roster.']]
        .forEach(([label, text]) => { const item = el('div', '', null, intro); el('strong', '', label, item); el('span', '', text, item); });
      if (ev) {
        const score = el('div', 'grade-scorecard', null, body);
        el('strong', '', 'Who saw it coming? ' + ev.players + ' ' + family + ' picks from 2017-2021', score);
        const bars = el('div', 'grade-score-bars', null, score);
        [['NFL.com grade', ev.nflSpearman], ['Archive draft grade', ev.archiveSpearman], ['Actual draft slot', ev.pickSpearman]].forEach(([label, value]) => {
          const row = el('div', 'grade-score-row', null, bars); el('span', '', label, row);
          const bar = el('div', 'report-bar', null, row); el('span', 'report-bar-fill' + (value === Math.max(ev.nflSpearman, ev.archiveSpearman, ev.pickSpearman) ? ' is-high' : ''), null, bar).style.width = Math.max(2, value * 100) + '%';
          el('span', 'grade-score-value', value.toFixed(2), row);
        });
        el('p', 'report-note', 'Rank agreement with hindsight grades (Spearman; 1.00 = perfect order, 0 = no relationship). Teams\' actual draft order usually wins: they also have medicals, interviews and their own film.', score);
      }
      const bucketTest = { all: () => true, r1: r => r === 1, r23: r => r === 2 || r === 3, r47: r => r >= 4 }[state.round];
      const rows = data.players.filter(p => bucketTest(p.round)).map(p => {
        const g = grades.players[p.id] || [];
        return { p, nfl: g[0] || null, draft: g[1], hindsight: g[2], current: g[3], provisional: !!g[4], delta: g[2] != null && g[1] != null ? g[2] - g[1] : null };
      });
      const toolbar = el('div', 'grid-toolbar', null, body);
      const searchWrap = el('div', 'search-field', null, toolbar);
      searchWrap.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5"></circle><path d="m15.5 15.5 5 5"></path></svg>';
      const search = el('input', 'search-input', null, searchWrap); search.type = 'search'; search.placeholder = 'Search player, college or team'; search.value = state.search;
      search.setAttribute('aria-label', 'Search ' + data.label + ' grades');
      const count = el('span', 'result-count', '', toolbar);
      const scroll = el('div', 'career-grid-scroll', null, body); scroll.tabIndex = 0; scroll.setAttribute('role', 'region'); scroll.setAttribute('aria-label', 'Grades table');
      const table = el('table', 'career-grid grades-table', null, scroll);
      el('caption', 'sr-only', 'Grades for every ' + SINGULAR[data.key], table);
      const header = table.createTHead().insertRow();
      const cols = [['name', 'Player'], ['draftslot', 'Drafted'], ['nfl', 'NFL.com'], ['draft', 'Archive draft'], ['hindsight', 'Hindsight'], ['current', 'Current'], ['delta', 'Beat projection']];
      const tbody = table.createTBody();
      cols.forEach(([key, label]) => {
        const th = el('th', '', null, header); th.scope = 'col';
        const button = el('button', '', label, th); button.type = 'button';
        if (key === 'delta') button.title = 'Hindsight grade minus archive draft grade';
        if (state.gsort === key) { th.setAttribute('aria-sort', state.gdir > 0 ? 'ascending' : 'descending'); el('span', 'sort-arrow', state.gdir > 0 ? '▲' : '▼', button); }
        button.addEventListener('click', () => { if (state.gsort === key) state.gdir = -state.gdir; else { state.gsort = key; state.gdir = key === 'name' || key === 'draftslot' ? 1 : -1; } render(data); });
      });
      const draw = () => {
        const query = state.search.trim().toLocaleLowerCase();
        const visible = rows.filter(r => !query || [r.p.name, r.p.college, r.p.team].join(' ').toLocaleLowerCase().includes(query));
        const value = r => state.gsort === 'name' ? r.p.name : state.gsort === 'draftslot' ? r.p.year * 1000 + r.p.pick : r[state.gsort];
        visible.sort((a, b) => {
          const va = value(a), vb = value(b);
          if (va === null || va === undefined) return 1;
          if (vb === null || vb === undefined) return -1;
          return (typeof va === 'string' ? va.localeCompare(vb) : va - vb) * state.gdir || a.p.year - b.p.year || a.p.pick - b.p.pick;
        });
        const fragment = document.createDocumentFragment();
        visible.forEach(r => {
          const tr = el('tr', '', null, fragment);
          const th = el('th', '', null, tr); th.scope = 'row';
          const link = el('a', '', r.p.name, th); link.href = '#player=' + r.p.id;
          el('span', 'grid-pos', r.p.pos, th);
          el('td', 'grid-draft', r.p.year + ' · R' + r.p.round + ' #' + r.p.pick, tr).title = r.p.team + ' · ' + r.p.college;
          const nfl = el('td', 'grade-cell', r.nfl == null ? '--' : Number(r.nfl).toFixed(2), tr); if (r.nfl == null) nfl.classList.add('cell-dnp');
          gradeCell(tr, r.draft);
          gradeCell(tr, r.hindsight, r.provisional ? '*' : '');
          gradeCell(tr, r.current);
          const d = el('td', 'grade-delta', r.delta == null ? '--' : (r.delta > 0 ? '+' : '') + r.delta.toFixed(2), tr);
          if (r.delta != null) d.classList.add(r.delta >= .3 ? 'is-up' : r.delta <= -.3 ? 'is-down' : 'is-even');
        });
        tbody.replaceChildren(fragment);
        count.textContent = visible.length + ' of ' + rows.length + ' players';
      };
      search.addEventListener('input', () => { state.search = search.value; draw(); });
      draw();
      el('p', 'report-note', '* Provisional hindsight grade (fewer than three completed seasons). Beat projection = hindsight minus archive draft grade; red = beat it by 0.30+, grey = fell 0.30+ short.', body);
    }).catch(() => { loading.textContent = 'Grades could not be loaded. Run build-grades.py and rebuild.'; });
  }
  function renderMethod(data) {
    const details = el('details', 'career-method', null, view);
    el('summary', '', 'How these numbers work · sources & downloads', details);
    const list = el('ul', '', null, details);
    [
      'Year 1 is the season of the draft (a 2021 pick\'s Year 1 is 2021). Every season after the draft counts, including seasons lost to injury or spent out of the league.',
      'All drafted: every player whose class has completed that career year. A season without games counts as zero for counting stats, so averages describe the whole draft pool, including busts.',
      'Only players who played: seasons with at least one game. This shows what active players produce, but later years are survivors.',
      'Same-player change compares each player with himself across consecutive seasons he played. It is the cleanest read on real development.',
      'Season snap share = snaps on his side of the ball divided by all of his team\'s snaps that season, including games missed. Games at 50%+ snaps is a starter measure that also covers offensive linemen.',
      'Rate stats (shares, per-attempt and per-target figures) only use seasons that meet the listed qualifier. PFR charting (pressures, coverage, drops, aDOT, broken tackles, on-target %) starts in 2018.',
      'Breakout timing uses the ' + index.timing.classes.join('-') + ' classes (2018-' + index.timing.classes[1] + ' for charted stats), each with five completed seasons, so every player had the same chance to reach Year 5.',
      'Edge, interior and off-ball groups follow the NFL role tag in the nflverse player table when one exists (for example, T.J. Watt was drafted as a linebacker but plays edge). Other positions use the draft listing.',
      'Games played, games started (every position, including offensive line), Approximate Value, Pro Bowls, All-Pro teams and awards come from Pro Football Reference team roster, Pro Bowl, All-Pro and award pages, collected in a browser session at under 20 pages per minute.',
      'Approximate Value (AV) is PFR\'s one-number estimate of a season\'s value, comparable across positions: roughly 1-3 backup, 4-7 starter, 8-11 good starter, 12+ Pro Bowl level. It is the best single measure for offensive linemen, who have no box-score stats.',
      'Penalty detail (holding, false starts, pass interference, roughing the passer, offsides) is counted from NFL play-by-play: accepted regular-season penalties charged to the player.',
      'Box-score stats come from nflverse public releases of NFL play-by-play, with PFR snap counts, PFR advanced charting, NFL schedules (QB starts and records) and PFR draft records. Each profile links to the player\'s PFR page.'
    ].forEach(text => el('li', '', text, list));
    const downloads = el('div', 'career-downloads', null, details); downloads.style.padding = '0 22px 20px';
    [['nfl-career-arcs-2017-2026.xlsx', 'Excel workbook: every position, Year 1-10 columns'], ['nfl-career-seasons-2017-2026.csv', 'Every player-season (CSV)'], ['data/careers/' + data.key + '.json', data.label + ' data (JSON)'], ['data/nfl-careers.json', 'Full career dataset (JSON)']].forEach(([href, label]) => {
      const link = el('a', '', label, downloads); link.href = href; link.download = href.split('/').pop();
    });
  }

  let resizeTimer, lastCompact = innerWidth < 640;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const compact = innerWidth < 640;
      if (compact !== lastCompact && !view.hidden && index && groupCache.has(state.group)) groupCache.get(state.group).then(render);
      lastCompact = compact;
    }, 200);
  });
  window.NFLCareerArcs = { lastHash: () => lastHash, groupLabel: key => PLURAL[key], short: key => SHORT[key] };
  window.addEventListener('hashchange', route);
  route();
})();
