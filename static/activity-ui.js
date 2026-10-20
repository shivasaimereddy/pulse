let activityPeriod='24h',activityKind='all',activityData=null,activityRequest=0,activityLimit=40,activityLoadedAt=null;
try{const saved=JSON.parse(sessionStorage.getItem('pulse.activityView')||'{}');if(['1h','24h','7d'].includes(saved.period))activityPeriod=saved.period;if(['all','performance','storage','gap'].includes(saved.kind))activityKind=saved.kind;}catch{}
function syncActivityView(){
 $('#activity-period').value=activityPeriod;
 document.querySelectorAll('[data-activity-kind]').forEach(button=>{const selected=button.dataset.activityKind===activityKind;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));});
 try{sessionStorage.setItem('pulse.activityView',JSON.stringify({period:activityPeriod,kind:activityKind}));}catch{}
}
const activityDate=value=>new Date(value*1000).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
const activityDay=value=>new Date(value*1000).toLocaleDateString([],{weekday:'long',month:'short',day:'numeric',year:'numeric'});
const activityDelta=value=>(value>0?'+':value<0?'−':'')+bytes(Math.abs(value||0));
async function loadActivity(){
 const request=++activityRequest;
 $('#refresh-activity').disabled=true;$('#activity-events').setAttribute('aria-busy','true');
 if(!activityData)set('#activity-status','Reading local activity…');
 try{
  const response=await fetch('/api/activity?range='+activityPeriod);
  if(response.status===404)throw Error('Restart Pulse from the updated source code to enable Activity timeline.');
  const result=await response.json();
  if(!response.ok)throw Error(result.error||'Activity could not be loaded.');
  if(!Array.isArray(result.events))throw Error('Activity data is unavailable. Restart Pulse from the updated source code.');
  if(request!==activityRequest)return;
  activityData=result;activityLoadedAt=Date.now();renderActivity();
 }catch(error){if(request===activityRequest)set('#activity-status',error.message+(activityData?' Showing the last loaded '+({'1h':'hour','24h':'24 hours','7d':'7 days'}[activityData.period]||'period')+'; these results may be out of date.':''));}
 finally{if(request===activityRequest){$('#refresh-activity').disabled=false;$('#activity-events').setAttribute('aria-busy','false');}}
}
function activityEventContent(event,rangeStart){
 if(event.kind==='performance'){
  const p=event.observation,cpu=p.kind==='cpu';
  return {icon:cpu?'cpu':'memory',tone:cpu?'blue':'purple',label:'PERFORMANCE',title:cpu?'Processor usage stayed high':'Memory usage stayed high',
   metric:p.average.toFixed(0)+'%',metricLabel:'average · '+p.peak.toFixed(0)+'% peak',
   interval:`${activityDate(event.start)} → ${activityDate(event.end)} · ${insightDuration(event.end-event.start)}${p.status==='active'?' · Ongoing':p.status==='interrupted'?' · Recording interrupted':''}`,
   detail:`<p>Apps with the highest observed ${cpu?'average CPU share':'average working-set memory'} during this period.</p><div class="activity-apps">${p.apps.map(app=>`<div><strong>${escapeHtml(app.label||app.name)}</strong><span>${cpu?app.cpu.toFixed(1)+'% CPU':bytes(app.memory)}</span></div>`).join('')||'<p>App details were unavailable.</p>'}</div><p class="activity-evidence-note">Observed together, not proof of cause.${event.start<rangeStart?' This period began before your selected range; averages describe the full period.':''}</p><button class="button secondary" data-activity-open="${escapeHtml(event.id)}">Review recorded period →</button>`};
 }
 if(event.kind==='storage'){
  const c=event.comparison,short=event.path.split(/[\\/]/).filter(Boolean).pop()||event.path;
  return {icon:'storageChanges',tone:'purple',label:'STORAGE COMPARISON',title:short+(c.net>0?' grew':c.net<0?' is smaller':' changed with no net growth'),
   metric:activityDelta(c.net),metricLabel:'net logical size change',
   interval:`Between scans · ${activityDate(event.start)} → ${activityDate(event.end)}`,
   detail:`<p class="activity-path">${escapeHtml(event.path)}</p><div class="activity-storage-evidence"><span><small>Added or grown</small><strong>${activityDelta(c.added)}</strong></span><span><small>Reduced or no longer listed</small><strong>${activityDelta(-c.reduced)}</strong></span></div>${event.highlights.length?'<div class="activity-highlights">'+event.highlights.map(item=>`<div><span>${escapeHtml(item.name)}</span><strong>${activityDelta(item.delta)}</strong></div>`).join('')+'</div>':''}<p class="activity-evidence-note">Detected at the newer scan. Exact change time is unknown. Missing items may have moved or been renamed.${c.limited?' Some saved comparison details have limited coverage.':''}</p><button class="button secondary" data-activity-open="${escapeHtml(event.id)}">Review this comparison →</button>`};
 }
 return {icon:'history',tone:'orange',label:'RECORDING COVERAGE',title:'No saved samples in this interval',metric:'~'+insightDuration(event.end-event.start),metricLabel:'without saved minute buckets',
  interval:`${activityDate(event.start)} → ${activityDate(event.end)}`,
  detail:'<p>Pulse has no saved minute buckets for this interval after recording began. Times are approximate. Sleep, downtime, or a recording problem may explain it; the cause is unknown.</p><button class="button secondary" data-view="history">Review performance history →</button>'};
}
function renderActivity(){
 if(!activityData)return;
 const h=activityData,events=h.events.filter(event=>activityKind==='all'||event.kind===activityKind);
 const fresh=h.lastSaved&&Date.now()/1000-h.lastSaved<30;
 set('#activity-status',(h.recordingError?'Recording needs attention: '+h.recordingError:h.recordingEnabled===false?'Saving performance history is paused':fresh?'Recording locally':h.lastSaved?'Last recorded '+activityDate(h.lastSaved):'Waiting for performance recordings')+' · Timeline loaded '+new Date(activityLoadedAt).toLocaleTimeString()+ (h.truncated?' · Latest available events shown; older events may be omitted':'')+(h.dropped?' · '+h.dropped+' samples skipped':''));
 ['performance','storage','gap'].forEach(kind=>set('#activity-'+kind+'-count',String(h.events.filter(event=>event.kind===kind).length)));
 const open=new Set([...$('#activity-events').querySelectorAll('details[open]')].map(item=>item.dataset.activityId));
 let day=null;
 $('#activity-events').innerHTML=events.slice(0,activityLimit).map(event=>{
  const content=activityEventContent(event,h.start),group=activityDay(event.end),heading=group!==day?`<h3 class="activity-day">${escapeHtml(group)}</h3>`:'';day=group;
  return `${heading}<details class="activity-event" data-activity-id="${escapeHtml(event.id)}" ${open.has(event.id)?'open':''}><summary><span class="activity-event-mark tile ${content.tone}">${icon(content.icon)}</span><span class="activity-event-title"><small>${content.label}</small><strong>${escapeHtml(content.title)}</strong><span>${escapeHtml(content.interval)}</span></span><span class="activity-event-metric"><strong>${escapeHtml(content.metric)}</strong><small>${escapeHtml(content.metricLabel)}</small></span><span class="activity-chevron" aria-hidden="true">⌄</span></summary><div class="activity-event-detail">${content.detail}</div></details>`;
 }).join('')||`<div class="card activity-empty"><span class="tile blue">${icon('activityTimeline')}</span><h3>${h.events.length?'No events match this filter.':'Your timeline is ready to build.'}</h3><p>${h.events.length?'Choose another activity type or time range.':'Keep Pulse running to record sustained activity. Scan a location again later to discover storage changes.'}</p><button class="button secondary" data-view="storage">Explore storage →</button></div>`;
 $('#activity-show-more').hidden=events.length<=activityLimit;
 set('#activity-show-more','Show more events · '+Math.max(0,events.length-Math.min(activityLimit,events.length))+' remaining');
}
async function openActivityEvent(id,button){
 const event=activityData?.events.find(item=>item.id===id);if(!event)return;
 button.disabled=true;
 try{
  if(event.kind==='performance'){
   insightsPeriod=activityData.period;syncInsightsPeriod();persistInsightsView();await changeView('optimize');
   const detail=[...$('#insights-events').querySelectorAll('details')].find(element=>element.dataset.eventId===event.observation.id);
   if(detail){detail.open=true;detail.scrollIntoView({block:'center',behavior:'instant'});const summary=detail.querySelector('summary');summary?.focus();}
   else toast('This recorded period is no longer available in the loaded insights. Refresh the timeline.');
  }else if(event.kind==='storage'){
   const response=await fetch('/api/activity/comparison?id='+event.scanId),comparison=await response.json();
   if(!response.ok)throw Error(comparison.error||'Comparison unavailable. Refresh the timeline.');
   await changeView('changes');storageChanges=[comparison];changesTimelineContext=event.id;
   $('#changes-location').innerHTML=`<option value="${escapeHtml(comparison.path)}">${escapeHtml(comparison.path)}</option>`;$('#changes-location').value=comparison.path;
   changesMode='items';$('#changes-filter').value='all';
   document.querySelectorAll('[data-changes-mode]').forEach(control=>{const selected=control.dataset.changesMode==='items';control.classList.toggle('selected',selected);control.setAttribute('aria-pressed',String(selected));});renderChanges();
  }
 }catch(error){toast(error.message);}
 finally{button.disabled=false;}
}
syncActivityView();
$('#activity-period').onchange=()=>{activityPeriod=$('#activity-period').value;activityLimit=40;syncActivityView();loadActivity();};
$('#refresh-activity').onclick=loadActivity;
$('#activity-show-more').onclick=()=>{activityLimit+=40;renderActivity();};
document.querySelectorAll('[data-activity-kind]').forEach(button=>button.onclick=()=>{activityKind=button.dataset.activityKind;activityLimit=40;syncActivityView();renderActivity();});
document.addEventListener('click',event=>{const button=event.target.closest('button[data-activity-open]');if(button)openActivityEvent(button.dataset.activityOpen,button);});
setInterval(()=>{if(view==='activity'&&!$('#refresh-activity').disabled)loadActivity();},30000);
