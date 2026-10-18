let processMode='groups';
let processFilter='all';
let processAscending=false;
const expandedGroups=new Set();
let selectedProcess=null;
let inspectedProcess=null;
let inspectionRequest=0;
let inspectionController=null;
let processSamples=[];
let processGone=false;

function processLabel(process){return process.label||process.name;}
function processKey(process){return `${process.pid}:${process.created}`;}
function matchesProcess(process) {
  const query=$('#search').value.trim().toLowerCase();
  const match=!query||[process.name,process.label,process.task,process.pid,process.executable].some(value=>String(value||'').toLowerCase().includes(query));
  if(!match)return false;
  if(processFilter==='mine')return process.mine&&!process.system;
  if(processFilter==='system')return process.system||!process.mine;
  if(processFilter==='manageable')return process.canClose;
  if(processFilter==='heavy')return processMode==='groups'||process.cpu>=1||process.memory>=256*1024*1024;
  return true;
}

function filteredProcessRows() {
  const rows=data.processes.filter(matchesProcess);
  return processFilter==='heavy'&&processMode==='groups'
    ?groupedProcesses(rows).filter(group=>group.cpu>=1||group.memory>=256*1024*1024).flatMap(group=>group.processes):rows;
}

function groupedProcesses(rows) {
  const groups=new Map();
  for(const process of rows){
    const key=process.groupKey||process.name;
    if(!groups.has(key))groups.set(key,{key,name:processLabel(process),executable:process.name,processes:[],cpu:0,memory:0,created:0});
    const group=groups.get(key);
    group.processes.push(process);
    group.cpu+=process.cpu;
    group.memory+=process.memory;
    group.created=Math.max(group.created,process.created);
  }
  return Array.from(groups.values());
}

function orderProcesses(rows) {
  return rows.sort((a,b)=>{
    const comparison=sort==='name'?String(a.label||a.name).localeCompare(String(b.label||b.name)):a[sort]-b[sort];
    return (processAscending?1:-1)*comparison||String(a.name).localeCompare(String(b.name));
  });
}

function inspectButton(process) {
  return `<button class="inspect-button" data-inspect-pid="${process.pid}" data-inspect-created="${process.created}" aria-label="Inspect ${escapeHtml(processLabel(process))}, PID ${process.pid}">Details <span>↗</span></button>`;
}

function resourceCells(cpu,memory) {
  return `<td class="resource-cell"><strong>${cpu.toFixed(1)}<small>%</small></strong><div class="resource-track"><i style="width:${Math.min(cpu,100)}%"></i></div></td><td class="resource-cell memory-cell"><strong>${bytes(memory)}</strong><div class="resource-track"><i style="width:${data?.memory.total?Math.min(memory/data.memory.total*100,100):0}%"></i></div></td>`;
}

function individualRow(process,child=false) {
  return `<tr class="${child?'process-child':''}"><td><div class="app-name"><span class="app-icon">${escapeHtml(process.name.slice(0,2).toUpperCase())}</span><div class="process-identity"><button class="process-title" data-inspect-pid="${process.pid}" data-inspect-created="${process.created}">${escapeHtml(processLabel(process))}</button><small>${escapeHtml(process.name)} <span>·</span> PID ${process.pid}${!process.canClose?' <span class="process-protected">· Protected</span>':''}</small></div></div></td>${resourceCells(process.cpu,process.memory)}<td>${inspectButton(process)}</td></tr>`;
}

function renderProcesses() {
  if(!data)return;
  const topCpu=[...data.processes].sort((a,b)=>b.cpu-a.cpu)[0];
  const topMemory=[...data.processes].sort((a,b)=>b.memory-a.memory)[0];
  set('#process-cpu-summary',data.cpu.toFixed(0)+'%');
  set('#process-memory-summary',data.memory.percent.toFixed(0)+'%');
  set('#process-count-summary',String(data.processes.length));
  set('#process-group-summary',`${groupedProcesses(data.processes).length} app & process groups`);
  set('#process-top-cpu',topCpu?`Top process: ${processLabel(topCpu)} · ${topCpu.cpu.toFixed(1)}%`:'No process readings');
  set('#process-top-memory',topMemory?`Top process: ${processLabel(topMemory)} · ${bytes(topMemory.memory)}`:'No process readings');
  const filtered=filteredProcessRows();
  let rows=processMode==='groups'?groupedProcesses(filtered):filtered;
  rows=orderProcesses(rows);
  const total=rows.length;
  const visible=all?rows:rows.slice(0,12);
  $('#process-list').innerHTML=visible.map(row=>{
    if(processMode==='individual')return individualRow(row);
    const expanded=expandedGroups.has(row.key);
    const single=row.processes.length===1;
    const details=single?inspectButton(row.processes[0]):`<button class="inspect-button" data-expand-processes="${escapeHtml(row.key)}" aria-expanded="${expanded}">${expanded?'Hide':'See'} ${row.processes.length} processes</button>`;
    return `<tr class="process-group ${expanded?'expanded':''}"><td><div class="app-name"><span class="app-icon">${escapeHtml(row.executable.slice(0,2).toUpperCase())}</span><div class="process-identity">${single?`<button class="process-title" data-inspect-pid="${row.processes[0].pid}" data-inspect-created="${row.processes[0].created}">${escapeHtml(row.name)}</button>`:`<button class="process-title" data-expand-processes="${escapeHtml(row.key)}" aria-expanded="${expanded}">${escapeHtml(row.name)} <span class="group-chevron">${expanded?'⌃':'⌄'}</span></button>`}<small>${row.processes.length} ${single?'process':'processes'} <span>·</span> ${escapeHtml(row.executable)}${single?' · PID '+row.processes[0].pid:''}${row.processes.every(p=>!p.canClose)?' · Protected':''}</small></div></div></td>${resourceCells(row.cpu,row.memory)}<td>${details}</td></tr>${expanded&&!single?orderProcesses([...row.processes]).map(p=>individualRow(p,true)).join(''):''}`;
  }).join('')||'<tr><td colspan="4" class="empty">No matches. Try another name, PID, or filter.</td></tr>';
  set('#process-name-heading',processMode==='groups'?'App / process group':'Process / identity');
  set('#table-info',`${visible.length} of ${total} ${processMode==='groups'?'groups':'processes'} · ${filtered.length} matching processes${paused?' · Display paused':''}`);
  set('#show-all',all?'Show fewer':'Show all '+total);
  $('#show-all').hidden=total<=12;
  set('#sort-cpu',sort==='cpu'?'Processor '+(processAscending?'↑':'↓'):'Processor');
  set('#sort-memory',sort==='memory'?'Memory '+(processAscending?'↑':'↓'):'Memory');
  $('#process-sort').value=`${sort==='created'?'created':sort}-${processAscending?'asc':'desc'}`;
  set('#pause-process-list',paused?'Resume list':'Pause list');
  $('#pause-process-list').setAttribute('aria-pressed',String(paused));
  if($('#process-dialog').open)updateInspectorLive();
}

function detailField(label,value,mono=false) {
  return `<div class="inspector-field"><dt>${label}</dt><dd data-detail-field="${label}"${mono?' class="mono"':''}>${value===null||value===undefined||value===''?'<span class="unavailable-value">Unavailable from Windows</span>':escapeHtml(value)}</dd></div>`;
}

function updateInspectorLive() {
  if(!selectedProcess)return;
  const live=data?.processes.find(p=>processKey(p)===processKey(selectedProcess));
  if(live&&!processGone){
    const time=data.timestamp;
    if(!processSamples.length||processSamples.at(-1).time!==time){
      processSamples.push({time,cpu:live.cpu,memory:live.memory/data.memory.total*100});
      processSamples=processSamples.slice(-60);
    }
    if($('#inspector-live-cpu'))set('#inspector-live-cpu',live.cpu.toFixed(1)+'%');
    if($('#inspector-live-memory'))set('#inspector-live-memory',bytes(live.memory));
  }
  if($('#inspector-chart'))$('#inspector-chart').innerHTML=chart(processSamples,'cpu','#3895ee',true)+chart(processSamples,'memory','#a084d6',true);
  if($('#inspector-live-note'))set('#inspector-live-note',processGone?'Process exited · last observed readings':paused?'Display paused · recording continues':'CPU and share of total RAM · while inspector is open');
}

function renderInspector() {
  const p=inspectedProcess;
  if(!p)return;
  set('#inspector-title',p.label||p.name);
  set('#inspector-subtitle',`${p.name} · PID ${p.pid}`);
  $('#inspector-content').innerHTML=`<div class="inspector-resources"><div><small>Processor</small><strong id="inspector-live-cpu">—</strong></div><div><small>Memory</small><strong id="inspector-live-memory">${bytes(p.memory)}</strong></div><div><small>Threads</small><strong id="inspector-threads">${p.threads??'—'}</strong></div></div>
    <div class="inspector-activity"><div id="inspector-chart" class="plot"></div><p id="inspector-live-note"></p></div>
    <div class="identity-callout ${p.canClose?'manageable':''}"><span>${icon(p.canClose?'check':'apps')}</span><div><h3>${p.canClose?'Available to manage':'Why this process is protected'}</h3><p>${escapeHtml(p.protectionReason||'This process belongs to your account and is outside the Windows system directory. Save your work and quit the app normally when possible.')}</p><small>Protection is an action restriction, not a security or trust assessment.</small></div></div>
    <div class="inspector-section"><h3>What is it running?</h3><dl>${detailField('Executable',p.executable,true)}${p.script?detailField('Script',p.script,true):''}${p.task?detailField('Runtime task',p.task):''}${detailField('Working folder',p.workingFolder,true)}${detailField('Command line',p.command,true)}</dl><p class="command-note">Command details are read on demand and stay out of the history database.${p.commandRedacted?' Common secret arguments were hidden.':' Common secret arguments are masked when recognized.'}</p></div>
    <div class="inspector-section"><h3>Process identity</h3><dl class="identity-grid">${detailField('Started',new Date(p.created*1000).toLocaleString())}${detailField('State',p.status)}${detailField('Account',p.owner)}${detailField('Handles',p.handles)}${detailField('Total I/O reads',p.ioCounters?bytes(p.ioCounters.read):null)}${detailField('Total I/O writes',p.ioCounters?bytes(p.ioCounters.write):null)}</dl></div>
    <div class="inspector-section"><h3>Where did it come from?</h3>${p.parent?`<button class="related-process" data-inspect-pid="${p.parent.pid}" data-inspect-created="${p.parent.created}"><span><small>Parent process</small><b>${escapeHtml(p.parent.name)}</b></span><span>PID ${p.parent.pid} ↗</span></button>`:'<p class="related-empty">The parent has exited, was reused, or is not readable.</p>'}<h4>${p.children.length} direct child ${p.children.length===1?'process':'processes'}${p.children.length===100?' (first 100)':''}</h4>${p.children.map(child=>`<button class="related-process" data-inspect-pid="${child.pid}" data-inspect-created="${child.created}"><b>${escapeHtml(child.name)}</b><span>PID ${child.pid} ↗</span></button>`).join('')||'<p class="related-empty">No readable direct child processes.</p>'}</div>
    ${p.unavailable.length?`<p class="inspection-limits">Some fields could not be read: ${escapeHtml(p.unavailable.join(', '))}. Pulse continues without requesting administrator access.</p>`:''}
    <div class="inspector-actions"><h3>Useful next steps</h3><div class="inspector-action-grid">${p.executable?'<button class="button secondary" data-process-folder="executable">Executable folder ↗</button>':''}${p.script?'<button class="button secondary" data-process-folder="script">Script folder ↗</button>':''}${p.workingFolder?'<button class="button secondary" data-process-folder="working">Working folder ↗</button>':''}<button id="refresh-process-details" class="button secondary">Refresh details</button><button id="copy-process-report" class="button secondary">Copy process report</button></div><button id="inspector-end" class="button ${p.canClose?'danger':'secondary'}" ${p.canClose&&!processGone?`data-close="${p.pid}" data-close-created="${p.created}"`:'disabled'}>${p.canClose?'End this process…':'Protected from ending'}</button><p>Ends this one process only. Unsaved work may be lost. Other processes in the group are not ended together.</p></div>`;
  updateInspectorLive();
}

async function loadProcessDetails(force=false) {
  if(!selectedProcess)return;
  const selected=selectedProcess;
  const request=++inspectionRequest;
  inspectionController?.abort();
  const controller=new AbortController();
  inspectionController=controller;
  try {
    if(!token)await session();
    const url=`/api/process?pid=${selected.pid}&created=${selected.created}`;
    let response=await fetch(url,{headers:{'X-Pulse-Token':token},signal:controller.signal});
    if(response.status===403){await session();response=await fetch(url,{headers:{'X-Pulse-Token':token},signal:controller.signal});}
    const value=await response.json();
    if(request!==inspectionRequest)return;
    if(!response.ok){
      if(response.status===410||response.status===409){processGone=true;$('#inspector-content').querySelectorAll('[data-process-folder],#inspector-end').forEach(b=>b.disabled=true);}
      throw Error(value.error||'Process details are unavailable.');
    }
    const firstLoad=!inspectedProcess;
    const permissionChanged=inspectedProcess&&inspectedProcess.canClose!==value.canClose;
    inspectedProcess=value;
    set('#inspector-status','Live identity · refreshed every 6 seconds');
    $('#inspector-status').className='inspector-status-live';
    if(firstLoad||force||permissionChanged)renderInspector();
    else {
      updateInspectorLive();
      if($('#inspector-threads'))set('#inspector-threads',String(value.threads??'—'));
      for(const [label,text] of [['State',value.status],['Handles',value.handles],['Total I/O reads',value.ioCounters?bytes(value.ioCounters.read):null],['Total I/O writes',value.ioCounters?bytes(value.ioCounters.write):null]]){const field=$('#inspector-content').querySelector(`[data-detail-field="${label}"]`);if(field)field.textContent=text??'Unavailable from Windows';}
      const end=$('#inspector-end');
      if(end)end.disabled=!value.canClose||processGone;
    }
  } catch(e) {
    if(e.name==='AbortError'||request!==inspectionRequest)return;
    set('#inspector-status',e.message);
    $('#inspector-status').className='inspector-status-ended';
    if(!inspectedProcess)$('#inspector-content').innerHTML='<div class="inspector-unavailable">The inspector identifies a process by both its PID and start time. Select a current process from the list to inspect it.</div>';
    updateInspectorLive();
  }
}

function openProcessInspector(pid,created) {
  selectedProcess={pid:Number(pid),created:Number(created)};
  inspectedProcess=null;
  processGone=false;
  processSamples=[];
  const live=data?.processes.find(p=>processKey(p)===processKey(selectedProcess));
  $('#inspector-heading').innerHTML=`<span class="inspector-app-icon">${icon('apps')}</span><div><h2 id="inspector-title">${escapeHtml(live?processLabel(live):'Process '+pid)}</h2><p id="inspector-subtitle">PID ${pid}</p></div>`;
  set('#inspector-status','Reading identity from Windows…');
  $('#inspector-status').className='';
  $('#inspector-content').innerHTML='<div class="inspector-loading">Finding the command, location, and parent process…</div>';
  if(!$('#process-dialog').open)$('#process-dialog').showModal();
  loadProcessDetails();
}

function exportProcessSnapshot() {
  if(!data)return;
  const rows=[['Name','Identity','PID','Processor %','Memory bytes','Started','Can manage'],...orderProcesses(filteredProcessRows()).map(p=>[p.name,processLabel(p),p.pid,p.cpu,p.memory,new Date(p.created*1000).toISOString(),p.canClose?'Yes':'No'])];
  const csv=rows.map(row=>row.map(value=>{let text=String(value);if(/^[=+\-@\t\r]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}).join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8;'}));
  const link=document.createElement('a');link.href=url;link.download='pulse-processes-'+new Date().toISOString().replaceAll(':','-')+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  toast('Snapshot exported. Includes filtered processes, without command lines.');
}

document.querySelectorAll('[data-process-mode]').forEach(button=>button.onclick=()=>{
  processMode=button.dataset.processMode;all=false;
  document.querySelectorAll('[data-process-mode]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});renderProcesses();
});
document.querySelectorAll('[data-process-filter]').forEach(button=>button.onclick=()=>{
  processFilter=button.dataset.processFilter;all=false;
  document.querySelectorAll('[data-process-filter]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});renderProcesses();
});
$('#search').oninput=()=>{all=false;renderProcesses();};
$('#process-sort').onchange=()=>{[sort]= $('#process-sort').value.split('-');processAscending=$('#process-sort').value.endsWith('asc');renderProcesses();};
$('#sort-cpu').onclick=()=>{processAscending=sort==='cpu'?!processAscending:false;sort='cpu';renderProcesses();};
$('#sort-memory').onclick=()=>{processAscending=sort==='memory'?!processAscending:false;sort='memory';renderProcesses();};
$('#show-all').onclick=()=>{all=!all;renderProcesses();};
$('#pause-process-list').onclick=()=>{$('#pause').click();renderProcesses();};
$('#open-task-manager').onclick=()=>action({action:'task-manager'});
$('#export-processes').onclick=exportProcessSnapshot;
$('#close-inspector').onclick=()=>$('#process-dialog').close();
$('#process-dialog').addEventListener('close',()=>{inspectionRequest++;inspectionController?.abort();selectedProcess=null;});
document.addEventListener('click',async event=>{
  const button=event.target.closest('button');
  if(!button)return;
  if(button.dataset.inspectPid)openProcessInspector(button.dataset.inspectPid,button.dataset.inspectCreated);
  if(button.dataset.sort&&button.dataset.view==='processes'){processAscending=false;renderProcesses();}
  if(button.id==='refresh-process-details')loadProcessDetails(true);
  if(button.dataset.expandProcesses){const key=button.dataset.expandProcesses;expandedGroups.has(key)?expandedGroups.delete(key):expandedGroups.add(key);renderProcesses();}
  if(button.dataset.processFolder&&selectedProcess&&!processGone)action({action:'process-folder',pid:selectedProcess.pid,created:selectedProcess.created,target:button.dataset.processFolder});
  if(button.id==='copy-process-report'&&inspectedProcess){
    const p=inspectedProcess;
    const report=`Pulse process report\n${p.label||p.name} · PID ${p.pid}\nStarted: ${new Date(p.created*1000).toLocaleString()}\nExecutable: ${p.executable||'Unavailable'}\nWorking folder: ${p.workingFolder||'Unavailable'}\nCommand: ${p.command||'Unavailable'}\nParent: ${p.parent?p.parent.name+' · PID '+p.parent.pid:'Unavailable'}\nProtection: ${p.protectionReason||'Eligible to manage'}\nCommand redaction is best effort; review before sharing.`;
    try{await navigator.clipboard.writeText(report);toast('Process report copied. Review command details before sharing.');}catch{toast('Clipboard access was unavailable. You can select and copy fields from this panel.');}
  }
});
setInterval(()=>{if($('#process-dialog').open&&!paused&&!processGone&&!$('#confirm-dialog').open)loadProcessDetails();},6000);
