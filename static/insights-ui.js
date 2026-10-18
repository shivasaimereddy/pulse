let insightsPeriod='24h',insightsData=null,insightsRequest=0;
const insightDuration=seconds=>seconds<60?'<1 min':seconds<3600?Math.round(seconds/60)+' min':(seconds/3600).toFixed(1)+' hr';
const insightStamp=timestamp=>new Date(timestamp*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
function persistInsightsView(){try{sessionStorage.setItem('pulse.insightsPeriod',insightsPeriod);}catch{}}
try{const saved=sessionStorage.getItem('pulse.insightsPeriod');if(['1h','24h','7d'].includes(saved))insightsPeriod=saved;}catch{}
function syncInsightsPeriod(){document.querySelectorAll('[data-insights-period]').forEach(button=>{const selected=button.dataset.insightsPeriod===insightsPeriod;button.classList.toggle('selected',selected);button.setAttribute('aria-pressed',String(selected));});}
syncInsightsPeriod();
async function loadInsights(){
 const request=++insightsRequest;$('#refresh-insights').disabled=true;
 if(!insightsData)set('#insights-status','Reading local observations...');
 try{
  const response=await fetch('/api/insights?range='+insightsPeriod);const result=await response.json();
  if(!response.ok)throw Error(result.error||'Performance insights could not be loaded.');
  if(request!==insightsRequest)return;insightsData=result;renderInsights();
 }catch(e){if(request===insightsRequest)set('#insights-status',e.message+(insightsData?' · Showing the last loaded observations.':''));}
 finally{if(request===insightsRequest)$('#refresh-insights').disabled=false;}
}
function renderInsights(){
 if(!insightsData)return;const h=insightsData;
 const freshness=h.lastSaved&&Date.now()/1000-h.lastSaved<20;
 set('#insights-status',h.recordingError?'Recording needs attention: '+h.recordingError:h.since?`${freshness?'Recording locally':'Last recorded'} · ${h.lastSaved?new Date(h.lastSaved*1000).toLocaleString():'waiting for samples'}${h.dropped?' · '+h.dropped+' samples skipped while storage was busy':''}${h.truncated?' · Latest 200 periods shown':''}`:'Your performance record starts now. New observations are saved within about 10 seconds.');
 set('#insights-count',String(h.summary.events));
 set('#insights-cpu-time',h.summary.cpuSeconds?insightDuration(h.summary.cpuSeconds):'0 min');
 set('#insights-memory-time',h.summary.memorySeconds?insightDuration(h.summary.memorySeconds):'0 min');
 const resolution=h.resolution||60;
 const points=h.points,chartStart=points.length?Math.max(h.start,Math.min(points[0].time,h.end-300)):h.start,span=Math.max(60,h.end-chartStart);
 set('#insights-chart-detail',`${resolution/60}-minute averages · recorded portion of selected period · gaps mean no samples`);
 if(!points.length){$('#insights-chart').innerHTML='<div class="insights-chart-empty">Recording your first observations…</div>';}
 else{
  const lines=[['cpu','Processor','#79b8ff'],['memory','Memory','#bc9fe8']].map(([key,label,color])=>{
   let path='',last=null;const dots=[];
   for(const point of points){const x=Math.max(0,Math.min(1000,(point.time+Math.min(resolution/2,Math.max(0,h.end-point.time)/2)-chartStart)/span*1000)),y=140-point[key]*1.4;path+=(last!==null&&point.time-last<=resolution*1.5?'L':'M')+x.toFixed(2)+','+y.toFixed(2)+' ';last=point.time;dots.push(`<circle cx="${x}" cy="${y}" r="2" fill="${color}"><title>${label}: ${point[key].toFixed(1)}% · ${escapeHtml(new Date(point.time*1000).toLocaleString())} · ${point.coverage}s sampled</title></circle>`);}
   return `<path d="${path}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/>${dots.join('')}`;
  }).join('');
  $('#insights-chart').innerHTML=`<svg viewBox="0 0 1000 140" preserveAspectRatio="none" aria-hidden="true"><path d="M0 0H1000M0 70H1000M0 140H1000" stroke="currentColor" opacity=".12"/>${lines}</svg>`;
 }
 const date=timestamp=>new Date(timestamp*1000).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
 $('#insights-chart-labels').innerHTML=`<span>${escapeHtml(date(chartStart))}</span><span>${escapeHtml(date(h.end))}</span>`;
 const open=new Set([...$('#insights-events').querySelectorAll('details[open]')].map(element=>element.dataset.eventId));
 const filter=$('#insights-kind').value;
 const events=h.events.filter(event=>filter==='all'||event.kind===filter);
 $('#insights-events').innerHTML=events.length?events.map(event=>{
  const cpu=event.kind==='cpu',title=cpu?'Sustained processor usage':'Sustained memory usage';
  const status=event.status==='active'?'Ongoing':event.status==='interrupted'?'Recording interrupted':'Ended';
  return `<details class="card insight-event" data-event-id="${escapeHtml(event.id)}" ${open.has(event.id)?'open':''}><summary><span class="tile ${cpu?'blue':'purple'}">${icon(cpu?'cpu':'memory')}</span><span class="insight-event-title"><strong>${title}</strong><small>${escapeHtml(new Date(event.start*1000).toLocaleDateString([],{month:'short',day:'numeric'}))} · ${insightStamp(event.start)}–${insightStamp(event.end)} · ${insightDuration(event.end-event.start)}</small></span><span class="insight-event-metric"><strong>${event.average.toFixed(0)}%</strong><small>average · ${event.peak.toFixed(0)}% peak</small></span><span class="insight-event-state ${event.status==='active'?'active':''}">${status}</span></summary><div class="insight-event-body"><p>${cpu?'Apps with the highest average share of total processor capacity':'Apps with the highest average working-set memory'} during the observed period.</p><div class="insight-app-list">${event.apps.map(app=>`<div class="insight-app"><div><strong>${escapeHtml(app.label)}</strong><small>${escapeHtml(app.name)} · present in ${Math.round(app.presence*100)}% of samples</small></div><div><strong>${cpu?app.cpu.toFixed(1)+'% CPU':bytes(app.memory)}</strong><small>${cpu?bytes(app.peakMemory)+' peak memory':app.cpu.toFixed(1)+'% average CPU'}</small></div><button class="link" data-insight-app="${escapeHtml(app.label)}">Review app ↗</button></div>`).join('')||'<p>App details were unavailable during this period.</p>'}</div><div class="insight-next-step"><span>${cpu?'Inspect the busiest apps and save your work before closing anything.':'Review memory-heavy apps. Close unused projects or browser tabs after saving your work.'}</span><button class="button secondary" data-setting="${cpu?'startup':'power'}">${cpu?'Review startup apps':'Review power settings'} ↗</button></div>${event.status==='interrupted'?'<p class="insight-gap-note">This period stops at the last recorded sample. Sleep, a recording gap, or a service restart may have interrupted it.</p>':''}</div></details>`;
 }).join(''):`<div class="card insights-empty"><span class="tile green">${icon('check')}</span><h3>${h.events.length?'No periods match this filter.':'No sustained pressure recorded.'}</h3><p>${h.events.length?'Choose another resource to explore.':'Short spikes do not count. A period appears after processor usage stays at 75% or memory at 80% for at least one minute while Pulse is recording.'}</p></div>`;
 $('#insights-repeated').hidden=!h.repeated.length;
 $('#insights-repeated-list').innerHTML=h.repeated.map(app=>`<div class="insight-repeat"><div><strong>${escapeHtml(app.label)}</strong><small>${app.events} separate periods · ${bytes(app.peakMemory)} peak memory</small></div><button class="link" data-insight-app="${escapeHtml(app.label)}">Review app ↗</button></div>`).join('');
}
document.querySelectorAll('[data-insights-period]').forEach(button=>button.onclick=()=>{insightsPeriod=button.dataset.insightsPeriod;syncInsightsPeriod();persistInsightsView();loadInsights();});
$('#refresh-insights').onclick=loadInsights;$('#insights-kind').onchange=renderInsights;
document.addEventListener('click',event=>{const button=event.target.closest('button[data-insight-app]');if(!button)return;processFilter='all';all=true;document.querySelectorAll('[data-process-filter]').forEach(control=>{const selected=control.dataset.processFilter==='all';control.classList.toggle('selected',selected);control.setAttribute('aria-pressed',String(selected));});$('#search').value=button.dataset.insightApp;changeView('processes');renderProcesses();toast('Showing current processes. Historical processes may have exited.');});
setInterval(()=>{if(view==='optimize'&&!$('#refresh-insights').disabled)loadInsights();},15000);
