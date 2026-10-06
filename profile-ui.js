(() => {
  'use strict';
  const archiveAPI = window.NFLDraftArchive;
  if (!archiveAPI) return;
  const { data, teams, openYear, currentTeams, currentTeamLabel } = archiveAPI;
  const archive = document.getElementById('archive-view');
  const view = document.getElementById('profile-view');
  const records = new Map();
  const profileCache = new Map();
  let currentId = null;
  let archiveScroll = 0;
  let archiveFocus = null;
  let controller;
  let requestVersion = 0;
  let returnHash = '#archive';
  let host = view;
  let currentTab = 'overview';
  const TABS = [['overview','Overview'],['scouting','Scouting'],['career','NFL career'],['measurements','Measurements'],['college','College'],['sources','Sources']];
  Object.entries(data).forEach(([year, picks]) => picks.forEach(row => {
    const [round,pick,team,via,name,position,college] = row;
    records.set(year+'-'+pick, { id:year+'-'+pick,year:Number(year),round,pick,team,via,name,position,college });
  }));
  const metrics = [
    ['height','Height','in',['height']],
    ['weight','Weight','lb',['weight']],
    ['handSize','Hand size','in',['handSize','hand_size','hands']],
    ['armLength','Arm length','in',['armLength','arm_length','arms']],
    ['wingspan','Wingspan','in',['wingspan']],
    ['fortyYardDash','40-yard dash','s',['fortyYardDash','forty_yard_dash','forty','fortyYard']],
    ['tenYardSplit','10-yard split','s',['tenYardSplit','ten_yard_split','tenSplit']],
    ['twentyYardSplit','20-yard split','s',['twentyYardSplit','twenty_yard_split']],
    ['threeConeDrill','Three-cone drill','s',['threeConeDrill','three_cone','threeCone']],
    ['twentyYardShuttle','20-yard shuttle','s',['twentyYardShuttle','short_shuttle','shuttle']],
    ['sixtyYardShuttle','60-yard shuttle','s',['sixtyYardShuttle','sixty_yard_shuttle']],
    ['verticalJump','Vertical jump','in',['verticalJump','vertical_jump','vertical']],
    ['broadJump','Broad jump','in',['broadJump','broad_jump','broad']],
    ['benchPress','Bench press','reps',['benchPress','bench_press','bench']]
  ];
  const metricsByKey = new Map(metrics.map(metric => [metric[0],metric]));
  const positionPriority = {
    QB:['handSize','height','weight','fortyYardDash','twentyYardShuttle','threeConeDrill'],
    OL:['armLength','handSize','height','weight','tenYardSplit','benchPress'],
    OT:['armLength','handSize','height','weight','tenYardSplit','benchPress'],
    OG:['armLength','handSize','height','weight','tenYardSplit','benchPress'],
    G:['armLength','handSize','height','weight','tenYardSplit','benchPress'],
    C:['armLength','handSize','height','weight','tenYardSplit','benchPress'],
    WR:['fortyYardDash','twentyYardShuttle','threeConeDrill','verticalJump','handSize','height'],
    RB:['fortyYardDash','tenYardSplit','twentyYardShuttle','verticalJump','weight','height'],
    FB:['weight','benchPress','tenYardSplit','twentyYardShuttle','height','fortyYardDash'],
    TE:['armLength','handSize','fortyYardDash','threeConeDrill','weight','height'],
    DE:['armLength','tenYardSplit','threeConeDrill','broadJump','weight','height'],
    DT:['weight','armLength','tenYardSplit','benchPress','twentyYardShuttle','height'],
    DL:['armLength','weight','tenYardSplit','benchPress','threeConeDrill','height'],
    EDGE:['armLength','tenYardSplit','threeConeDrill','broadJump','weight','height'],
    LB:['fortyYardDash','tenYardSplit','twentyYardShuttle','threeConeDrill','weight','height'],
    OLB:['armLength','fortyYardDash','threeConeDrill','broadJump','weight','height'],
    ILB:['fortyYardDash','twentyYardShuttle','threeConeDrill','verticalJump','weight','height'],
    CB:['fortyYardDash','twentyYardShuttle','threeConeDrill','verticalJump','armLength','height'],
    DB:['fortyYardDash','twentyYardShuttle','threeConeDrill','verticalJump','armLength','height'],
    S:['fortyYardDash','twentyYardShuttle','threeConeDrill','verticalJump','weight','height'],
    FS:['fortyYardDash','twentyYardShuttle','threeConeDrill','verticalJump','weight','height'],
    SS:['fortyYardDash','twentyYardShuttle','threeConeDrill','verticalJump','weight','height'],
    K:['height','weight'],
    P:['height','weight'],
    LS:['height','weight','armLength','handSize','benchPress','fortyYardDash']
  };
  function el(tag, className, text, parent) {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (parent) parent.appendChild(n);
    return n;
  }
  function safeURL(value) {
    if(typeof value!=='string' || !value.trim())return null;
    try { const url = new URL(value, location.href); return ['https:','http:'].includes(url.protocol) ? url.href : null; }
    catch { return null; }
  }
  function sourceLink(label,url,parent,className='') {
    const href=safeURL(url);
    if (!href) return el('span',className,label,parent);
    const a=el('a',className,label,parent); a.href=href; a.target='_blank'; a.rel='noopener noreferrer';
    return a;
  }
  function localLink(label,href,parent,className='') {
    const a=el('a',className,label,parent); a.href=href; return a;
  }
  function section(parent,id,title,caption) {
    const s=el('section','profile-section',null,parent); s.id=id; s.setAttribute('aria-labelledby',id+'-heading');
    const heading=el('div','profile-section-title',null,s);
    el('h2','',title,heading).id=id+'-heading';
    if(caption) el('span','section-caption',caption,heading);
    return s;
  }
  function empty(parent,title,message) {
    const n=el('div','profile-empty',null,parent); el('strong','',title,n); if(message) el('span','',message,n); return n;
  }
  function normalizeReadings(profile,metric) {
    const measurement=profile.workouts?.measurements || profile.measurements || {};
    const key=metric[3].find(key=>measurement[key]!==undefined);
    if(!key) return [];
    const values=Array.isArray(measurement[key]) ? measurement[key] : [measurement[key]];
    return values.map(item => typeof item==='object' && item!==null ? item : {value:item,unit:metric[2]})
      .filter(item=>item.value!==null && item.value!==undefined && item.value!=='' && item.value!=='N/A');
  }
  function preferred(readings) {
    const combine=readings.filter(item=>item.event==='NFL Scouting Combine');
    return combine.find(item=>/^official$/i.test(item.designation || '')) || combine[0] || readings.find(item=>/^official$/i.test(item.designation || '') && !/unspecified/i.test(item.event || '')) || readings.find(item=>item.date && !/unspecified/i.test(item.event || '')) || readings.find(item=>/^official$/i.test(item.designation || '')) || readings[0];
  }
  function displayValue(reading,key) {
    if(!reading) return 'Not reported';
    const value=reading.value;
    const unit=reading.unit || metricsByKey.get(key)?.[2] || '';
    if(key==='height' && ['in','inch','inches'].includes(unit) && Number.isFinite(Number(value))) {
      const inches=Number(value); return Math.floor(inches/12)+'′ '+Math.round((inches%12)*100)/100+'″';
    }
    return String(value);
  }
  function unitLabel(reading,key) {
    if(!reading) return '';
    if(key==='height' && ['in','inch','inches'].includes(reading.unit || 'in')) return '';
    const unit=reading.unit || metricsByKey.get(key)?.[2] || '';
    return ({in:'in',inch:'in',inches:'in',lb:'lb',lbs:'lb',s:'sec',sec:'sec',reps:'reps'})[unit] || unit;
  }
  function eventLabel(reading) {
    const event=reading.event || 'Event not specified';
    const designation=reading.designation==='not-reported' ? null : reading.designation;
    return String(event)+(designation ? ' · '+String(designation).toLowerCase().replaceAll('_',' ') : '');
  }
  function getSource(profile,reading) {
    return (profile.workouts?.sources || []).find(source=>source.id===reading?.sourceId);
  }
  let benchmarkPromise;
  let metricDialog;
  let metricDialogVersion=0;
  function loadMetricContext() {
    if(!benchmarkPromise) {
      benchmarkPromise=Promise.all(['measurement-benchmarks.json','measurement-definitions.json'].map(async file=>{
        const response=await fetch('data/'+file);
        if(!response.ok)throw new Error('Metric context unavailable');
        return response.json();
      })).catch(error=>{benchmarkPromise=null;throw error;});
    }
    return benchmarkPromise;
  }
  function metricInfoButton(parent,metric,reading,record) {
    const button=el('button','metric-info-button','i',parent);button.type='button';
    button.setAttribute('aria-label','About '+metric[1]+' and '+record.position+' benchmarks');
    button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-controls','metric-info-dialog');
    button.dataset.metric=metric[0];
    if(reading){button.dataset.value=reading.value;button.dataset.event=reading.event || '';}
    button.addEventListener('click',()=>openMetricInfo(metric,reading,record));
    return button;
  }
  function closeMetricInfo() {
    ++metricDialogVersion;
    if(metricDialog?.open)metricDialog.close();
  }
  function benchmarkPosition(position,benchmarks) {
    const aliases=benchmarks.positionAliases || benchmarks.positionMap || {};
    if(aliases[position])return aliases[position];
    const groups=benchmarks.positions || benchmarks.benchmarks || benchmarks;
    if(groups[position])return position;
    const fallback={T:'OT',G:'OG',FS:'S',SS:'S',ILB:'LB',NT:'DT'};
    return fallback[position] || position;
  }
  function benchmarkValue(value,unit) {
    if(value===null || value===undefined || !Number.isFinite(Number(value)))return 'Not reported';
    const suffix=({s:'sec',in:'in',lb:'lb',reps:'reps'})[unit] || unit || '';
    return Number(value).toLocaleString(undefined,{maximumFractionDigits:2})+(suffix?' '+suffix:'');
  }
  function renderMetricContext(parent,metric,reading,record,benchmarks,definitions) {
    const definition=(definitions.metrics || definitions.definitions || definitions)[metric[0]] || {};
    const position=benchmarkPosition(record.position,benchmarks);
    const groups=benchmarks.positions || benchmarks.benchmarks || benchmarks;
    const stats=groups[position]?.[metric[0]];
    const unit=definition.unit || metric[2];
    const direction=definition.direction || 'size';
    el('p','metric-definition',definition.definition || 'A verified definition is not available in the saved metric guide.',parent);
    if(definition.interpretation)el('p','metric-interpretation',definition.interpretation,parent);
    const observation=el('div','metric-observation',null,parent);
    el('span','',record.name+' / '+record.position,observation);
    const result=el('strong','',reading?displayValue(reading,metric[0])+(unitLabel(reading,metric[0])?' '+unitLabel(reading,metric[0]):''):'Result not reported',observation);
    if(reading)el('span','metric-observation-event',eventLabel(reading),observation);
    if(!stats || !stats.n){
      empty(parent,'No '+position+' benchmark available','The collected records do not supply a positional comparison for this measurement.');
    } else {
      const heading=el('h3','metric-cohort-heading',position+' draft-player benchmark',parent);
      const list=el('dl','metric-benchmark-grid',null,parent);
      [['Average',benchmarkValue(stats.mean,unit)],['Median',benchmarkValue(stats.median,unit)],['Middle 50%',benchmarkValue(stats.p25,unit)+' to '+benchmarkValue(stats.p75,unit)],['Sample',Number(stats.n).toLocaleString()+(stats.n===1?' player':' players')]].forEach(([label,value])=>{
        const item=el('div','',null,list);el('dt','',label,item);el('dd','',value,item);
      });
      const values=(stats.values || []).map(Number).filter(Number.isFinite);
      const player=reading && Number(reading.value);
      const minimumSample=benchmarks.minimumRankSample || 20;
      const rankable=stats.rankable!==false && Number(stats.n)>=minimumSample;
      const crossEvent=/official.*combine/i.test(stats.eventScope || '') && reading && !(reading.event==='NFL Scouting Combine' && /^official$/i.test(reading.designation || ''));
      if(reading && crossEvent)el('p','metric-cross-event-note','Cross-event estimate: this observation is from '+eventLabel(reading)+', compared with official combine results. Testing conditions and timing may differ.',parent);
      if(reading && Number.isFinite(player) && values.length && rankable){
        const ties=values.filter(value=>value===player).length;
        const below=values.filter(value=>value<player).length;
        const above=values.filter(value=>value>player).length;
        const percentile=100*((direction==='lower'?above:below)+ties*0.5)/values.length;
        const topShare=100-percentile;
        const size=direction==='size';
        const ranking=el('div','metric-percentile',null,parent);
        el('div','metric-percentile-label',size?'Size percentile':crossEvent?'Estimated performance percentile':'Performance percentile',ranking);
        const score=el('div','metric-percentile-score',percentile.toFixed(1),ranking);el('span','','th percentile',score);
        let band=topShare<=10?'Top 10%':topShare<=20?'Top 20%':topShare<=50?'Top 50%':'Outside the top 50%';
        el('div','metric-percentile-band',band+(size?' by measurement size':''),ranking);
        const graphic=el('div','metric-percentile-graphic',null,ranking);graphic.setAttribute('role','img');graphic.setAttribute('aria-label',percentile.toFixed(1)+' percentile among '+position+' players in this sample');
        const track=el('div','metric-percentile-track',null,graphic);el('div','metric-percentile-fill',null,track).style.width=percentile+'%';el('span','metric-percentile-marker',null,track).style.left=percentile+'%';
        const scale=el('div','metric-percentile-scale',null,graphic);['0','50','100'].forEach(label=>el('span','',label,scale));
        el('p','metric-percentile-description',size?'Top '+topShare.toFixed(1)+'% by measurement size in this '+position+' sample. Larger measurements receive higher percentiles; this is not an athletic-ability ranking.':'Top '+topShare.toFixed(1)+'% for this drill in the '+position+' sample. '+(direction==='lower'?'Lower times receive higher percentiles.':'Higher results receive higher percentiles.'),ranking);
        el('p','metric-method-note','Tied results share their midpoint rank. The percentile evaluates this selected observation, not an overall scouting grade.',ranking);
      } else if(!rankable) {
        el('p','metric-method-note','This positional sample contains only '+stats.n+' recorded '+(stats.n===1?'result':'results')+'. Summary values are shown, but percentiles require at least '+minimumSample+' players.',parent);
      } else {
        el('p','metric-method-note','A player percentile cannot be calculated without a reported numeric result. The positional benchmark remains available above.',parent);
      }
      const note=el('div','metric-cohort-note',null,parent);
      if(stats.cohort || benchmarks.cohort)el('p','',stats.cohort || benchmarks.cohort,note);
      if(stats.eventScope || benchmarks.eventScope)el('p','',stats.eventScope || benchmarks.eventScope,note);
      if(stats.selectionRule || benchmarks.selectionRule)el('p','',stats.selectionRule || benchmarks.selectionRule,note);
      el('p','','Positional figures describe the drafted players with reported measurements in this archive, not every current NFL player.',note);
    }
    if(definition.sourceUrl){const source=el('p','metric-definition-source',null,parent);sourceLink(definition.sourceLabel || 'Measurement definition source',definition.sourceUrl,source);}
  }
  async function openMetricInfo(metric,reading,record) {
    if(!metricDialog){
      metricDialog=el('dialog','metric-info-dialog',null,document.body);metricDialog.id='metric-info-dialog';
      metricDialog.setAttribute('aria-labelledby','metric-info-title');
      metricDialog.addEventListener('click',event=>{if(event.target===metricDialog){const rect=metricDialog.getBoundingClientRect();if(event.clientX<rect.left || event.clientX>rect.right || event.clientY<rect.top || event.clientY>rect.bottom)closeMetricInfo();}});
      metricDialog.addEventListener('cancel',()=>{++metricDialogVersion;});
      metricDialog.addEventListener('close',()=>document.body.classList.remove('has-metric-dialog'));
    }
    const version=++metricDialogVersion;metricDialog.replaceChildren();
    const head=el('div','metric-dialog-header',null,metricDialog);el('h2','',metric[1],head).id='metric-info-title';
    const close=el('button','metric-dialog-close','\u00d7',head);close.type='button';close.setAttribute('aria-label','Close measurement information');close.addEventListener('click',closeMetricInfo);
    const body=el('div','metric-dialog-body',null,metricDialog);body.setAttribute('aria-live','polite');body.setAttribute('aria-busy','true');
    el('p','metric-interpretation','Loading definition and positional comparisons...',body);
    if(!metricDialog.open)metricDialog.showModal();
    document.body.classList.add('has-metric-dialog');
    close.focus();
    try{
      const [benchmarks,definitions]=await loadMetricContext();
      if(version!==metricDialogVersion || !metricDialog.open)return;
      body.replaceChildren();renderMetricContext(body,metric,reading,record,benchmarks,definitions);body.setAttribute('aria-busy','false');
    }catch{
      if(version!==metricDialogVersion || !metricDialog.open)return;
      body.replaceChildren();body.setAttribute('aria-busy','false');empty(body,'Measurement guide could not be loaded','Retry to load the saved definitions and position benchmarks.');
      const retry=el('button','profile-retry','Retry measurement guide',body);retry.type='button';retry.addEventListener('click',()=>openMetricInfo(metric,reading,record));
    }
  }
  function topbar(record) {
    const bar=el('div','profile-topbar',null,view);
    localLink(returnHash.startsWith('#careers')?'← Back to career arcs':'← Back to draft results',returnHash,bar,'profile-back');
    const nav=el('nav','profile-pick-nav',null,bar); nav.setAttribute('aria-label','Navigate draft picks');
    const previous=records.get(record.year+'-'+(record.pick-1));
    const next=records.get(record.year+'-'+(record.pick+1));
    if(previous){const link=localLink('← Previous pick','#player='+previous.id,nav,'profile-pick-link');link.setAttribute('aria-label','Previous pick: '+previous.name);link.dataset.pickId=previous.id;}
    if(next){const link=localLink('Next pick →','#player='+next.id,nav,'profile-pick-link');link.setAttribute('aria-label','Next pick: '+next.name);link.dataset.pickId=next.id;}
  }
  function hero(record) {
    const hero=el('header','profile-hero',null,view);
    const identity=el('div','profile-identity',null,hero);
    if(teams[record.team]) {
      const image=el('img','profile-team-logo',null,identity); image.src='assets/teams/'+teams[record.team]+'.png'; image.alt=record.team; image.width=100; image.height=100;
    }
    const text=el('div','',null,identity);
    const title=el('h1','',record.name,text); title.id='player-title'; title.tabIndex=-1;
    const line=el('div','profile-position-line',null,text);
    el('span','position',record.position,line); el('span','',record.college || 'College not reported',line);
    const pick=el('div','profile-draft-card',null,hero);
    el('div','pick-caption','Overall pick',pick); el('div','pick-display','#'+record.pick,pick); el('div','draft-caption',record.year+' draft · Round '+record.round,pick);
    const membership=currentTeams.players[record.id];
    const team=el('p','profile-team-line',null,view);
    el('span','','Drafted by ',team);el('strong','',record.team,team);
    if(record.via) el('span','',' (pick via '+record.via+')',team);
    el('span','',' · Now: ',team);
    sourceLink(currentTeamLabel(membership),membership?.team?membership.sourceUrl:(membership?.statusSourceUrl || membership?.sourceUrl),team,'profile-read-more');
    el('span','',' · checked '+currentTeams.asOf,team);
  }
  function tierClass(grade) {
    if(grade===null || grade===undefined)return 't-none';
    return grade>=7.5?'t-rare':grade>=7?'t-pb':grade>=6.7?'t-hes':grade>=6.5?'t-qs':grade>=6.3?'t-as':grade>=6.1?'t-ss':grade>=6?'t-bu':grade>=5.7?'t-fr':'t-dns';
  }
  function gradeStrip(profile,record) {
    const g=profile.grades;if(!g)return;
    const draft=profile.scoutingReports?.draft || {};
    const strip=el('section','grade-strip',null,view);strip.setAttribute('aria-label','Grades');
    const card=(label,value,tierText,caption,cls)=>{
      const c=el('div','grade-card '+cls,null,strip);
      el('span','grade-label',label,c);
      el('strong','grade-value',value==null?'--':Number(value).toFixed(2),c);
      el('span','grade-tier',tierText || (value==null?'Not graded':''),c);
      if(caption)el('span','grade-caption',caption,c);
    };
    card('NFL.com grade',g.nfl,draft.gradeRankClass?ordinal(draft.gradeRankClass)+' of '+draft.classGraded+' in class':'',
      'Published pre-draft scouting grade','is-nfl');
    card('Archive draft grade',g.draft,g.draftTier,g.draftOutOfSample?'Pre-draft data only; graded without his class\'s results':'Pre-draft data only',tierClass(g.draft));
    card('Hindsight grade',g.hindsight,g.hindsightTier,g.hindsight==null?'No completed season yet':g.hindsightProvisional?'Provisional: fewer than 3 seasons':'Best 3 seasons vs. his position',tierClass(g.hindsight));
    card('Current grade',g.current,g.currentTier,g.currentBasis?String(g.currentBasis).charAt(0).toUpperCase()+String(g.currentBasis).slice(1):'',tierClass(g.current));
    const link=localLink('How the grades work →','#careers='+(g.group || 'WR')+'&view=grades',strip,'grade-help');
    link.setAttribute('aria-label','How the archive grades work');
  }
  function table(parent,label,columns) {
    const scroll=el('div','profile-table-scroll',null,parent); scroll.tabIndex=0; scroll.setAttribute('role','region'); scroll.setAttribute('aria-label',label);
    const table=el('table','profile-data-table',null,scroll); el('caption','sr-only',label,table);
    const header=table.createTHead().insertRow(); columns.forEach(column=>{const cell=el('th','',typeof column==='string'?column:column.label,header);cell.scope='col';if(column.description)cell.title=column.description;});
    return {table,body:table.createTBody()};
  }
  const careerFormats={
    pct:value=>(value*100).toFixed(1)+'%',
    dec1:value=>Number(value).toFixed(1),
    dec2:value=>Number(value).toFixed(2),
    int:value=>Math.round(value).toLocaleString(),
    text:value=>String(value)
  };
  function careerValue(value,format) {
    if(value===null || value===undefined || value==='') return '';
    return (careerFormats[format] || careerFormats.int)(value);
  }
  function renderNFLCareer(profile,record) {
    const career=profile.nflCareer;
    const live=career?.inProgress;
    const s=section(host,'nfl-career','NFL career',live?'Regular season · '+live.season+' through Week '+live.throughWeek:'Regular season');
    if(!career){empty(s,'NFL career statistics not collected','Rebuild the archive with collect-nfl-careers.py and build-career-arcs.py.');return;}
    const arcs=window.NFLCareerArcs;
    const summary=el('p','nfl-career-summary',null,s);
    const played=career.games>0;
    if(played){
      const line=el('span','',null,summary);el('strong','',career.games.toLocaleString()+(career.games===1?' game':' games'),line);
      const liveGames=career.categories[0]?.seasons.some(row=>row.inProgress && row.g);
      line.append(' · '+career.seasonsPlayed+' completed '+(career.seasonsPlayed===1?'season':'seasons')+' with games'+(liveGames?' plus '+live.season:''));
    }
    (career.groups || []).forEach(group=>localLink('How '+(arcs?.groupLabel(group) || group)+' develop by year →','#careers='+group,summary));
    if(career.pfrUrl)sourceLink('Pro Football Reference page',career.pfrUrl,summary);
    const honors=career.honors;
    if(played && honors){
      const chips=el('div','nfl-career-honors',null,s);
      const chip=(label,list,top)=>{if(!list.length)return;const c=el('span',top?'is-top':'',null,chips);el('strong','',list.length+'x '+label,c);c.append(' ('+list.join(', ')+')');};
      if(honors.avKnown){const c=el('span','',null,chips);el('strong','',honors.av+' career AV',c);c.title='Approximate Value summed across seasons (Pro Football Reference).';}
      chip('First-team All-Pro',honors.allPro,true);chip('Second-team All-Pro',honors.allPro2,false);chip('Pro Bowl',honors.proBowls,true);
      chip('All-Pro (special teams)',honors.allProST || [],false);chip('Pro Bowl (special teams)',honors.proBowlsST || [],false);
      honors.awards.forEach(award=>el('span','is-top',award,chips));
    }
    if(!played){empty(s,'No regular-season NFL games yet','No regular-season snaps recorded from '+record.year+' through '+(live?live.season+' Week '+live.throughWeek:'the latest season')+'. Practice-squad and reserve time does not register as games.');return;}
    const pills=el('div','career-pills',null,s);pills.setAttribute('role','tablist');pills.setAttribute('aria-label','Career tables');
    const blocks=[];
    career.categories.forEach((category,index)=>{
      const block=el('div','profile-category',null,s);el('h3','sr-only',category.label,block);
      const pill=el('button','career-pill',category.label,pills);pill.type='button';pill.setAttribute('role','tab');
      blocks.push([pill,block]);
      pill.addEventListener('click',()=>blocks.forEach(([p,b])=>{const on=p===pill;p.setAttribute('aria-selected',String(on));b.hidden=!on;}));
      pill.setAttribute('aria-selected',String(index===0));block.hidden=index!==0;
      const columns=[{label:'Year',description:'Career year (Year 1 = draft season)'},{label:'Season'},{label:'Team'},...category.columns.map(column=>({label:column.label,description:(column.title?column.title+': ':'')+column.description}))];
      const built=table(block,record.name+' '+category.label.toLowerCase()+' by season',columns);
      built.table.querySelectorAll('thead th').forEach((th,i)=>{if(i>2)th.classList.add('num');});
      category.seasons.forEach(season=>{
        const row=built.body.insertRow();
        if(!season.g)row.className='is-dnp';
        if(season.inProgress)row.classList.add('is-live');
        el('th','','Y'+season.cy,row).scope='row';
        el('td','',season.season+(season.inProgress?' (Wk '+live.throughWeek+')':''),row);
        el('td','',season.g?(season.teams || []).join(' / ') || 'NFL':'Did not play',row);
        category.columns.forEach(column=>el('td','num',season.g?careerValue(season.values[column.key],column.format):'',row));
      });
      const totals=category.career?.values || {};
      if(Object.keys(totals).length){
        const row=built.body.insertRow();row.className='career-row';el('th','','Career',row).scope='row';el('td','','Through '+(live?live.season+' Wk '+live.throughWeek:'latest'),row);el('td','','',row);
        category.columns.forEach(column=>el('td','num',careerValue(totals[column.key],column.format),row));
      }
    });
    el('p','profile-note','Year 1 is the '+record.year+' season. Blank cells mean the stat did not apply or was not charted: PFR charting (pressures, coverage, drops) starts in 2018. Games, starts, Approximate Value and honors come from Pro Football Reference team rosters and award pages. Rate stats appear only when the season meets the volume qualifier. Season snap share counts all of the team\'s snaps, including games missed.',s);
  }
  function renderMeasurements(profile,record) {
    const s=section(host,'measurements','Measurements & workouts','Position focus: '+record.position);
    const keys=positionPriority[record.position] || ['height','weight','fortyYardDash','tenYardSplit','verticalJump','twentyYardShuttle'];
    const rail=el('div','profile-key-metrics'+(['K','P'].includes(record.position)?' is-specialist':''),null,s);
    keys.forEach(key=>{
      const metric=metricsByKey.get(key), readings=normalizeReadings(profile,metric), value=preferred(readings);
      const box=el('div','profile-key-metric',null,rail);const label=el('div','profile-metric-label',null,box);el('span','',metric[1],label);metricInfoButton(label,metric,value,record);
      const number=el('div','profile-metric-value'+(!value?' is-missing':''),displayValue(value,key),box);
      if(value && unitLabel(value,key)) el('span','profile-metric-unit',unitLabel(value,key),number);
      if(value){const source=getSource(profile,value);const event=el('div','profile-metric-event',null,box);sourceLink(eventLabel(value),source?.url || value.sourceUrl,event);}
    });
    el('p','profile-note','Official results are shown first when supplied. Other reported events remain separate below; mixed-source records are not presented as official combine results.',s);
    const details=el('details','profile-workout-details',null,s);
    const reportedCount=metrics.reduce((count,metric)=>count+normalizeReadings(profile,metric).length,0);
    el('summary','','All measurements & event results ('+reportedCount+' reported readings)',details);
    const {body}=table(details,'All reported measurements and workout events',['Measurement','Result','Event / designation','Source']);
    metrics.forEach(metric=>{
      const readings=normalizeReadings(profile,metric);
      (readings.length?readings:[null]).forEach(reading=>{
        const row=body.insertRow();const th=el('th','',null,row);th.scope='row';const label=el('div','metric-table-label',null,th);el('span','',metric[1],label);metricInfoButton(label,metric,reading,record);
        el('td','metric-reading',displayValue(reading,metric[0])+(unitLabel(reading,metric[0])?' '+unitLabel(reading,metric[0]):''),row);
        el('td','',reading?eventLabel(reading):'—',row);
        const sourceCell=el('td','',null,row); const source=getSource(profile,reading);
        if(source || reading?.sourceUrl) sourceLink(source?.label || 'Reported source',source?.url || reading.sourceUrl,sourceCell);
        else el('span','',reading?'Source not specified':'—',sourceCell);
      });
    });
    const supplemental=profile.publishedWorkouts || [];
    if(supplemental.length){
      const category=el('div','profile-category',null,s);el('h3','','Additional published workouts',category);
      const {body}=table(category,'Additional published workouts',['Event','Date / status','Published result','Source']);
      supplemental.forEach(workout=>{const row=body.insertRow();el('th','',workout.event || workout.label || 'Workout',row).scope='row';el('td','',(workout.date || 'Date not reported')+(workout.status?' · '+workout.status:''),row);const result=el('td','published-workout-description',null,row);if(workout.summary)el('div','',workout.summary,result);if(Array.isArray(workout.metrics) && workout.metrics.length)workout.metrics.forEach(metric=>el('div','',metric.label+': '+metric.value+(metric.unit?' '+metric.unit:'')+(metric.designation?' ('+metric.designation+')':''),result));else if(!workout.summary)el('span','','No measured results published',result);sourceLink(workout.sourceLabel || 'Source',workout.sourceUrl,el('td','',null,row));});
    }
    el('p','profile-note',typeof profile.privateWorkoutsStatus==='string'?profile.privateWorkoutsStatus:'Private-workout results: no separately verified measured results in this profile’s collected sources. Team visits and workout invitations do not supply drill results.',s);
  }
  function renderCollege(profile) {
    const college=profile.collegeStats || {};
    const s=section(host,'college','College career');
    const summary=college.summary || profile.collegeCareerSummary || profile.careerSummary;
    if(summary) el('p','profile-summary',typeof summary==='string'?summary:summary.text || '',s);
    const categories=(college.categories || []).filter(category=>(category.seasons || []).length || category.career?.values);
    const experience=Array.isArray(college.experience)?college.experience:(college.experience?.rows || profile.collegeExperience || []);
    if(!categories.length && !experience.length){
      const notApplicable=college.status==='not-applicable';
      empty(s,notApplicable?'No college football career':'College statistics not reported in collected sources',college.note || college.reason || (notApplicable?'This player did not have a conventional college football statistical career.':'A verified season-by-season statistical table was not found. Missing stats are not recorded as zero.'));
    }
    categories.forEach(category=>{
      const block=el('div','profile-category',null,s);el('h3','',category.label || category.key || 'College statistics',block);
      const columns=(category.columns || []).map(column=>typeof column==='string'?{key:column,label:column}:column);
      const {body}=table(block,(category.label || 'College')+' season and career statistics',['Season','School',...columns]);
      (category.seasons || []).forEach(season=>{
        const row=body.insertRow();el('th','',season.seasonLabel || season.year || season.label || 'Not reported',row).scope='row';
        el('td','',typeof season.team==='object'?season.team.displayName || season.team.name:season.team || season.school || 'Not reported',row);
        columns.forEach(column=>el('td','',season.values?.[column.key] ?? '—',row));
      });
      if(category.career?.values && Object.keys(category.career.values).length){
        const row=body.insertRow();row.className='career-row';el('th','','Career',row).scope='row';el('td','','All listed schools',row);
        columns.forEach(column=>el('td','',category.career.values[column.key] ?? '—',row));
        if(category.career.basis) el('p','profile-category-note',category.career.basis,block);
      }
    });
    if(experience.length){
      const block=el('div','profile-category',null,s);el('h3','','Participation & additional college production',block);
      const fields=[['games','Games'],['starts','Starts'],['snaps','Snaps'],['sacksAllowed','Sacks allowed'],['hitsAllowed','Hits allowed'],['hurriesAllowed','Hurries allowed'],['pressuresAllowed','Pressures allowed'],['tacklesForLoss','Tackles for loss'],['passesBrokenUp','Passes broken up']].filter(([key])=>experience.some(row=>row[key]!==undefined && row[key]!==null));
      const {body}=table(block,'College participation and additional production',['Season','School',...fields.map(([,label])=>label),'Source']);
      experience.forEach(record=>{const row=body.insertRow();if(record.year==='Career' || record.seasonLabel==='Career')row.className='career-row';el('th','',record.seasonLabel || record.year || 'Not reported',row).scope='row';el('td','',record.team || profile.college || 'Not reported',row);fields.forEach(([key])=>el('td','',record[key] ?? '—',row));const sourceCell=el('td','',null,row);sourceLink(record.sourceLabel || 'School record',record.sourceUrl,sourceCell);if(record.metricAttribution)el('div','profile-metric-attribution',record.metricAttribution,sourceCell);});
    }
    if(college.coverageNote) el('p','profile-note',college.coverageNote,s);
    if(categories.length || experience.length) el('p','profile-note','Season and career figures follow the linked college source. A dash means a value was not reported. Tables preserve transfers and do not substitute NFL statistics.',s);
    if(college.sourceUrl) sourceLink('View college statistical record',college.sourceUrl,s,'profile-read-more');
    else (college.sources || []).forEach(source=>{const p=el('p','profile-category-note',null,s);sourceLink(source.label || 'College statistics source',source.url,p);});
  }
  function ordinal(value) {
    const n=Math.round(value);const tail=n%100>=11 && n%100<=13?'th':({1:'st',2:'nd',3:'rd'})[n%10] || 'th';return n+tail;
  }
  function percentileBar(parent,pct,lowerNote) {
    const bar=el('div','report-bar',null,parent);bar.setAttribute('role','img');bar.setAttribute('aria-label',ordinal(pct)+' percentile');
    const fill=el('span','report-bar-fill'+(pct>=80?' is-high':pct<=20?' is-low':''),null,bar);fill.style.width=Math.max(2,pct)+'%';
    if(lowerNote)bar.title=lowerNote;
    return bar;
  }
  function reportHead(panel,kicker,title) {
    const head=el('div','report-head',null,panel);el('span','report-kicker',kicker,head);el('h3','',title,head);return head;
  }
  function renderDraftReport(grid,profile,record) {
    const report=profile.scoutingReports?.draft;
    const scouting=profile.workouts?.scouting || profile.scouting || {};
    const panel=el('article','report-panel',null,grid);panel.setAttribute('aria-label','Draft-day report');
    reportHead(panel,record.year+' NFL Draft · pre-draft','Draft-day report');
    if(!report){empty(panel,'Draft-day report not built','Run build-scouting-reports.py.');return;}
    const meta=el('dl','report-meta',null,panel);
    [['NFL.com grade',report.grade!=null?Number(report.grade).toFixed(2):'Not reported'],
     ['Grade rank, class',report.gradeRankClass?ordinal(report.gradeRankClass)+' of '+report.classGraded:''],
     ['Grade rank, '+record.position,report.gradeRankPosition?ordinal(report.gradeRankPosition)+' of '+report.positionGraded:''],
     ['Archive draft grade',profile.grades?.draft!=null?Number(profile.grades.draft).toFixed(2)+' · '+profile.grades.draftTier:''],
     ['Selected','#'+record.pick+' overall'],
     ['Projected',report.projection || ''],
     ['Comparison',report.comparison || '']].filter(([,value])=>value).forEach(([label,value])=>{const item=el('div','',null,meta);el('dt','',label,item);el('dd','',value,item);});
    writeupBlock(panel,report);
    if(report.athletic?.length){
      const block=el('div','report-block',null,panel);el('h4','','Athletic profile',block);
      const list=el('div','report-rows',null,block);
      report.athletic.forEach(test=>{
        const row=el('div','report-row',null,list);
        const label=el('span','report-row-label',test.label,row);
        if(test.kind==='size')el('span','report-tag','size',label);
        if(test.crossEvent)el('span','report-tag','pro day',label).title='Compared with official combine results; testing conditions differ.';
        el('span','report-row-value',(test.key==='height'?Math.floor(test.value/12)+'′ '+Math.round((test.value%12)*100)/100+'″':test.value+' '+test.unit),row);
        percentileBar(row,test.percentile,test.kind==='lower'?'Faster times rank higher':'');
        el('span','report-row-pct',ordinal(test.percentile),row);
      });
      el('p','report-note','Percentiles compare drafted '+record.position+'s in this archive (2017-2026). Size measures rank by size, not ability.',block);
    }
    if(report.production?.length){
      const block=el('div','report-block',null,panel);el('h4','','College production vs. his draft class',block);
      const list=el('div','report-rows',null,block);
      report.production.forEach(item=>{
        const row=el('div','report-row is-text',null,list);
        el('span','report-row-label',item.label.charAt(0).toUpperCase()+item.label.slice(1),row);
        const text=el('span','report-row-text',null,row);
        if(item.final!=null)text.append(Number(item.final).toLocaleString()+' in '+item.finalYear+(item.finalRank?' ('+ordinal(item.finalRank)+' of '+item.finalOf+')':''));
        if(item.career!=null)text.append((item.final!=null?' · ':'')+'career '+Number(item.career).toLocaleString()+(item.careerRank?' ('+ordinal(item.careerRank)+' of '+item.careerOf+')':''));
      });
    }
    if(scouting.strengthQuote || scouting.weaknessQuote || scouting.overviewQuote){
      const block=el('div','report-block',null,panel);el('h4','','Published evaluation (excerpt)',block);
      [['Overview',scouting.overviewQuote],['Strength',scouting.strengthQuote],['Concern',scouting.weaknessQuote]].filter(([,quote])=>quote).forEach(([label,quote])=>{
        const q=el('div','report-quote',null,block);el('span','report-quote-label',label,q);el('blockquote','',quote,q);
      });
    }
    if(scouting.sourceUrl){
      const byline=el('p','profile-byline',null,panel);
      if(scouting.author)el('span','',scouting.author+' · ',byline);
      sourceLink('Read the full published scouting report',scouting.sourceUrl,byline,'scouting-source-link');
    } else if(!report.grade && !report.athletic?.length) {
      empty(panel,'No published pre-draft evaluation collected','Measurements alone do not establish a player’s strengths or weaknesses.');
    }
  }
  const STATE_LABELS={rising:'Best season yet','near-peak':'Near his peak','below-peak':'Below his peak',developing:'Developing',out:'Not on a roster',early:'Early career','not-played':'No NFL games yet'};
  function renderCurrentReport(grid,profile,record) {
    const report=profile.scoutingReports?.current;
    const panel=el('article','report-panel',null,grid);panel.setAttribute('aria-label','Current report');
    reportHead(panel,report?report.season+' season · through Week '+report.throughWeek:'Current season','Current report');
    if(!report){empty(panel,'Current report not built','Run build-scouting-reports.py.');return;}
    const status=el('div','report-status',null,panel);
    el('span','report-state report-state-'+report.state,STATE_LABELS[report.state] || report.state,status);
    sourceLink(report.status+(report.rosterStatus && report.onRoster?' · '+report.rosterStatus:''),report.statusSourceUrl,status,'report-status-link');
    if(profile.grades?.current!=null)el('span','report-grade '+tierClass(profile.grades.current),'Current grade '+Number(profile.grades.current).toFixed(2)+' · '+profile.grades.currentTier,status);
    writeupBlock(panel,report);
    if(report.state!=='not-played')avChart(panel,report);
    const ranked=[['Strengths',report.strengths,'is-strength'],['Weak spots',report.concerns,'is-concern']].filter(([,list])=>list?.length);
    rankedBlock(panel,report,ranked);
    if(report.thisSeason){
      const block=el('div','report-block',null,panel);el('h4','',report.season+' so far',block);
      const line=el('p','report-this-season',null,block);
      const bits=[report.thisSeason.g+' G',(report.thisSeason.gs ?? 0)+' GS',report.thisSeason.snapShare!=null?(report.thisSeason.snapShare*100).toFixed(0)+'% of snaps':null,...report.thisSeason.line.map(item=>item.text+' '+item.label)].filter(Boolean);
      line.textContent=bits.join(' · ');
    }
    const links=el('p','profile-byline',null,panel);
    if(report.espnUrl){sourceLink('Latest news & analysis (ESPN)',report.espnUrl,links,'scouting-source-link');links.append(' · ');}
    if(report.pfrUrl)sourceLink('Pro Football Reference page',report.pfrUrl,links,'scouting-source-link');
  }
  function avChart(parent,report) {
    const seasons=(report.av || []).filter(row=>row.g>0 || row.av!=null);
    if(!seasons.length)return;
    {
      const block=el('div','report-block',null,parent);el('h4','','Approximate Value by season',block);
      const chart=el('div','av-chart',null,block);chart.setAttribute('role','img');
      const max=Math.max(12,...seasons.map(row=>row.av || 0));
      chart.setAttribute('aria-label','Approximate Value by season: '+seasons.map(row=>row.season+' '+(row.av==null?'in progress':row.av)).join(', '));
      (report.av || []).forEach(row=>{
        const col=el('div','av-col'+(row.av==null && row.g?' is-live':'')+(!row.g?' is-dnp':''),null,chart);
        col.title=row.season+' (Year '+row.cy+'): '+(row.g?row.g+' G, '+(row.gs ?? '?')+' GS, '+(row.av==null?'AV pending':row.av+' AV'):'did not play')+(row.ap?' · First-team All-Pro':row.pb?' · Pro Bowl':'');
        const bar=el('div','av-bar'+(row.ap?' is-ap':row.pb?' is-pb':''),null,el('div','av-track',null,col));
        bar.style.height=(row.av?Math.max(4,row.av/max*100):row.g?3:0)+'%';
        el('span','av-value',row.av==null?(row.g?'--':''):row.av,col);
        el('span','av-year',"'"+String(row.season).slice(2),col);
      });
      el('p','report-note','Bars: PFR Approximate Value (12+ is Pro Bowl level). Red = first-team All-Pro, outlined = Pro Bowl. AV for the current season is published after it ends.',block);
    }
  }
  function rankedBlock(panel,report,ranked) {
    if(ranked.length){
      const block=el('div','report-block',null,panel);el('h4','',report.latest.season+' season vs. all drafted '+report.groupLabel.toLowerCase(),block);
      const list=el('div','report-rows',null,block);
      ranked.forEach(([title,items,cls])=>{
        el('div','report-subhead '+cls,title,list);
        items.forEach(item=>{const row=el('div','report-row',null,list);el('span','report-row-label',item.label,row);el('span','report-row-value',item.text,row);percentileBar(row,item.percentile);el('span','report-row-pct',ordinal(item.percentile),row);});
      });
      el('p','report-note','Percentiles rank this season against every 2017-2025 season by drafted '+report.groupLabel.toLowerCase()+' (8+ games for totals; rate stats need their volume qualifier). Lower is better for penalties, drops, missed tackles and coverage allowed.',block);
    }
  }
  function writeupBlock(panel,report,grade,tierText) {
    if(report.writeup){
      el('p','report-writeup',report.writeup,panel);
      const details=el('details','report-numbers',null,panel);el('summary','','By the numbers',details);el('p','report-summary',report.summary,details);
    } else el('p','report-summary',report.summary,panel);
  }
  function renderScouting(profile,record) {
    const s=section(host,'scouting','Scouting reports','Draft day vs. today');
    const grid=el('div','report-grid',null,s);
    renderDraftReport(grid,profile,record);
    renderCurrentReport(grid,profile,record);
    el('p','profile-note',profile.scoutingReports?.note || 'Reports are built from the published grades, testing and statistics in this archive.',s);
  }
  function renderSources(profile,record) {
    const footer=el('section','profile-sources',null,host);footer.id='sources';el('h2','','Sources & coverage',footer);
    const all=[...(profile.workouts?.sources || []),...(profile.collegeStats?.sources || [])];
    const membership=currentTeams.players[record.id];
    if(membership?.sourceUrl)all.push({label:'Current NFL roster / player record',url:membership.sourceUrl});
    if(membership?.statusSourceUrl)all.push({label:'Current league status',url:membership.statusSourceUrl});
    const scouting=profile.workouts?.scouting || profile.scouting;
    if(scouting?.sourceUrl)all.push({label:'Published scouting report'+(scouting.author?' — '+scouting.author:''),url:scouting.sourceUrl});
    if(profile.collegeStats?.sourceUrl)all.push({label:'College statistical record',url:profile.collegeStats.sourceUrl});
    if(profile.workouts?.bio?.sourceUrl)all.push({label:'Player biography',url:profile.workouts.bio.sourceUrl});
    (profile.publishedWorkouts || []).forEach(workout=>all.push({label:workout.sourceLabel || workout.event || 'Published workout',url:workout.sourceUrl}));
    all.push({label:record.year+' draft selections & trade history',url:'https://en.wikipedia.org/wiki/'+record.year+'_NFL_draft#Player_selections'});
    if(profile.nflCareer?.pfrUrl)all.push({label:'Pro Football Reference player page',url:profile.nflCareer.pfrUrl});
    if(profile.nflCareer)all.push({label:'NFL career statistics, PFR snap counts and charting (nflverse public releases)',url:'https://github.com/nflverse/nflverse-data/releases'});
    (Array.isArray(profile.collegeStats?.experience)?profile.collegeStats.experience:[]).forEach(row=>{if(row.sourceUrl)all.push({label:row.sourceLabel || 'College participation record',url:row.sourceUrl});});
    const seen=new Set(),list=el('ol','',null,footer);
    all.forEach(source=>{const url=safeURL(source.url);if(url && !seen.has(url)){seen.add(url);sourceLink(source.label || 'Source',url,el('li','',null,list));}});
    el('p','profile-note','This profile shows information supported by the listed sources. “Not reported” means a result was not supplied in the collected records; it does not establish that the player did not perform the drill.',footer);
    if(profile.generatedAt || profile.updatedAt){const value=profile.updatedAt || profile.generatedAt;el('p','profile-category-note','Profile data collected: '+String(value).slice(0,10),footer);}
    const download=localLink('Download this player’s data (JSON)','data/profiles/'+record.id+'.json',el('p','profile-category-note',null,footer),'profile-read-more');download.download=record.id+'.json';
  }
  function renderOverview(profile,record) {
    const grid=el('div','overview-grid',null,host);
    const main=el('section','overview-card overview-scouting',null,grid);
    el('h2','','Scouting report',main);
    const draft=profile.scoutingReports?.draft,current=profile.scoutingReports?.current;
    const part=(kicker,title,report,extra)=>{
      if(!report)return;
      const block=el('div','overview-report',null,main);
      const head=el('div','overview-report-head',null,block);el('span','report-kicker',kicker,head);el('h3','',title,head);
      if(extra)extra(head);
      el('p','report-writeup',report.writeup || report.summary,block);
    };
    part(record.year+' NFL Draft','Draft day',draft,head=>{if(profile.grades?.draft!=null)el('span','report-grade '+tierClass(profile.grades.draft),'Archive '+Number(profile.grades.draft).toFixed(2)+' · '+profile.grades.draftTier,head);});
    part(current?current.season+' · Week '+current.throughWeek:'Now','Today',current,head=>{if(profile.grades?.current!=null)el('span','report-grade '+tierClass(profile.grades.current),'Current '+Number(profile.grades.current).toFixed(2)+' · '+profile.grades.currentTier,head);});
    const more=el('button','overview-more','Full draft-day and current reports →',main);more.type='button';more.addEventListener('click',()=>selectTab('scouting',true));
    const side=el('aside','overview-side',null,grid);
    const glance=el('section','overview-card',null,side);el('h2','','Career at a glance',glance);
    const career=profile.nflCareer,honors=career?.honors;
    const stats=el('dl','glance-stats',null,glance);
    const done=(career?.categories?.[0]?.seasons || []).filter(row=>!row.inProgress);
    const starts=done.reduce((sum,row)=>sum+(row.values?.gs || 0),0);
    [['Games',career?career.games:0],['Starts',starts],['Career AV',honors?.avKnown?honors.av:'--'],['Pro Bowls',honors?.proBowls?.length || 0],['All-Pro (1st)',honors?.allPro?.length || 0],['Seasons',career?.seasonsPlayed || 0]]
      .forEach(([label,value])=>{const item=el('div','',null,stats);el('dt','',label,item);el('dd','',value,item);});
    if(honors?.awards?.length){const chips=el('div','nfl-career-honors',null,glance);honors.awards.forEach(award=>el('span','is-top',award,chips));}
    if(current && current.state!=='not-played')avChart(glance,current);
    const goCareer=el('button','overview-more','Season-by-season stats →',glance);goCareer.type='button';goCareer.addEventListener('click',()=>selectTab('career',true));
    const tests=(draft?.athletic || []).filter(test=>test.kind!=='size').sort((a,b)=>Math.abs(b.percentile-50)-Math.abs(a.percentile-50)).slice(0,4);
    if(tests.length){
      const card=el('section','overview-card',null,side);el('h2','','Testing standouts',card);
      const list=el('div','report-rows',null,card);
      tests.forEach(test=>{const row=el('div','report-row',null,list);el('span','report-row-label',test.label,row);el('span','report-row-value',test.value+' '+test.unit,row);percentileBar(row,test.percentile);el('span','report-row-pct',ordinal(test.percentile),row);});
      const goTests=el('button','overview-more','All measurements →',card);goTests.type='button';goTests.addEventListener('click',()=>selectTab('measurements',true));
    }
  }
  let tabButtons=new Map(),tabPanels=new Map();
  function selectTab(key,focus) {
    if(!tabPanels.has(key))key='overview';
    currentTab=key;
    tabButtons.forEach((button,name)=>{const on=name===key;button.setAttribute('aria-selected',String(on));button.tabIndex=on?0:-1;});
    tabPanels.forEach((panel,name)=>{panel.hidden=name!==key;});
    if(currentId){
      const hash='#player='+currentId+(key!=='overview'?'&tab='+key:'');
      if(location.hash!==hash)history.replaceState(null,'',hash);
      view.querySelectorAll('[data-pick-id]').forEach(link=>{link.href='#player='+link.dataset.pickId+(key!=='overview'?'&tab='+key:'');});
    }
    if(focus){tabButtons.get(key)?.focus();const top=view.querySelector('.profile-tabs');if(top && top.getBoundingClientRect().top<0)top.scrollIntoView({block:'start'});}
  }
  function renderProfile(profile,record) {
    view.replaceChildren(); topbar(record);hero(record);gradeStrip(profile,record);
    const bar=el('div','profile-tabs',null,view);bar.setAttribute('role','tablist');bar.setAttribute('aria-label','Profile sections');
    tabButtons=new Map();tabPanels=new Map();
    TABS.forEach(([key,label])=>{
      const button=el('button','profile-tab',label,bar);button.type='button';button.setAttribute('role','tab');button.id='tab-'+key;button.setAttribute('aria-controls','panel-'+key);
      const panel=el('div','profile-panel',null,view);panel.id='panel-'+key;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby','tab-'+key);panel.hidden=true;
      tabButtons.set(key,button);tabPanels.set(key,panel);
      button.addEventListener('click',()=>selectTab(key));
    });
    bar.addEventListener('keydown',event=>{
      const keys=[...tabButtons.keys()];const index=keys.indexOf(currentTab);
      if(event.key==='ArrowRight' || event.key==='ArrowLeft'){event.preventDefault();selectTab(keys[(index+(event.key==='ArrowRight'?1:keys.length-1))%keys.length],true);}
    });
    const renderers=[['overview',()=>renderOverview(profile,record)],['scouting',()=>renderScouting(profile,record)],['career',()=>renderNFLCareer(profile,record)],
      ['measurements',()=>renderMeasurements(profile,record)],['college',()=>renderCollege(profile)],['sources',()=>renderSources(profile,record)]];
    renderers.forEach(([key,render])=>{host=tabPanels.get(key);render();});
    host=view;
    selectTab(currentTab);
  }
  async function showProfile(id) {
    closeMetricInfo();
    const record=records.get(id);
    if(!currentId){archiveScroll=window.scrollY;archiveFocus=archive.querySelector('[data-profile="'+id+'"]');}
    currentId=id;archive.hidden=true;view.hidden=false;view.setAttribute('aria-busy','true');
    document.title=(record?.name || 'Player profile')+' | NFL Draft Archive';
    controller?.abort();controller=new AbortController();const version=++requestVersion;
    view.replaceChildren();
    if(!record){view.setAttribute('aria-busy','false');localLink('← Back to draft results','#archive',view,'profile-back');empty(view,'Player profile not found','Choose a player from the draft results to open a valid profile.');window.scrollTo({top:0,behavior:'instant'});view.focus({preventScroll:true});return;}
    topbar(record);const loading=el('div','profile-loading',null,view);el('h1','',record.name,loading);el('p','','Loading NFL career, measurements, college statistics and scouting…',loading);
    window.scrollTo({top:0,behavior:'instant'});view.focus({preventScroll:true});
    try {
      let profile=profileCache.get(id);
      if(!profile){const response=await fetch('data/profiles/'+id+'.json',{signal:controller.signal});if(!response.ok)throw new Error('HTTP '+response.status);profile=await response.json();profileCache.set(id,profile);}
      if(version!==requestVersion)return;
      renderProfile(profile,record);view.setAttribute('aria-busy','false');document.getElementById('player-title').focus({preventScroll:true});
    } catch(error) {
      if(error.name==='AbortError' || version!==requestVersion)return;
      view.setAttribute('aria-busy','false');view.replaceChildren();topbar(record);hero(record);empty(view,'Profile data could not be loaded','The saved profile file could not be reached. Retry to load this player’s measurements, statistics and report.');
      const button=el('button','profile-retry','Retry loading profile',view);button.type='button';button.addEventListener('click',()=>showProfile(id));
    }
  }
  function showArchive() {
    closeMetricInfo();
    if(!currentId)return;
    controller?.abort();++requestVersion;const previous=currentId;currentId=null;view.hidden=true;archive.hidden=false;document.title='NFL Draft Archive | 2017–2026';
    const matchingLink=archive.querySelector('[data-profile="'+previous+'"]');
    if(!archiveFocus){const year=records.get(previous)?.year || Math.max(...Object.keys(data).map(Number));openYear(String(year),false);archiveFocus=archive.querySelector('[data-profile="'+previous+'"]');archiveScroll=0;}
    requestAnimationFrame(()=>{window.scrollTo({top:archiveScroll,behavior:'instant'});(archiveFocus || matchingLink)?.focus({preventScroll:true});});
  }
  function leaveProfile() {
    if(!currentId)return;
    controller?.abort();++requestVersion;currentId=null;view.hidden=true;
  }
  function route(event) {
    closeMetricInfo();
    const match=location.hash.match(/^#player=(\d{4}-\d+)(?:&tab=([a-z]+))?$/);
    if(match){
      const sameProfile=match[1]===currentId && !view.hidden;
      currentTab=match[2] || 'overview';
      if(sameProfile && tabPanels.size){selectTab(currentTab);return;}
      const previous=event?.oldURL ? new URL(event.oldURL).hash : '';
      if(previous.startsWith('#careers'))returnHash=previous;
      else if(!previous.startsWith('#player='))returnHash='#archive';
      showProfile(match[1]);
    }
    else if(location.hash.startsWith('#careers'))leaveProfile();
    else if(location.hash==='#archive' || location.hash==='' || location.hash==='#')showArchive();
  }
  archive.addEventListener('click',event=>{const link=event.target.closest('[data-profile]');if(link){archiveScroll=window.scrollY;archiveFocus=link;}});
  window.addEventListener('hashchange',route);
  route();
})();
