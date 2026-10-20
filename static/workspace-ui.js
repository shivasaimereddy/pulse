// Overview and storage investigation surfaces. No automatic system actions.

let leaderSort='cpu',workspacePrevious=null,workspaceRecordBusy=false,workspaceRecordAt=0;

function updateMarkup(selector,html){const element=$(selector);if(element.contains?.(document.activeElement))return;if(element.innerHTML!==html)element.innerHTML=html;}

function renderWorkspaceOverview(){

 if(!data)return;

 const groups=groupedProcesses(data.processes).sort((a,b)=>b[leaderSort]-a[leaderSort]).slice(0,4);

 updateMarkup('#overview-leaders',groups.map((group,index)=>`<button class="leader-row" data-review-group="${escapeHtml(group.name)}"><span class="leader-rank">${index+1}</span><span class="leader-name"><strong>${escapeHtml(group.name)}</strong><small>${group.processes.length} ${group.processes.length===1?'process':'processes'}</small></span><span class="leader-value"><strong>${leaderSort==='cpu'?group.cpu.toFixed(1)+'%':bytes(group.memory)}</strong><small>${leaderSort==='cpu'?bytes(group.memory)+' memory':group.cpu.toFixed(1)+'% CPU'}</small></span><span aria-hidden="true">↗</span></button>`).join('')||'<p>No readable app activity in this sample.</p>');

 set('#essential-memory',bytes(data.memory.available));

 const available=data.memory.total?Math.max(0,Math.min(100,data.memory.available/data.memory.total*100)):0;

 set('#essential-memory-detail',Math.round(available)+'% available · '+bytes(data.memory.total)+' total');

 $('#essential-memory-bar').style.width=available+'%';

 $('#essential-battery-bar').style.width=(data.battery?Math.max(0,Math.min(100,data.battery.percent)):0)+'%';

 const previous=workspacePrevious,elapsed=previous?data.timestamp-previous.timestamp:0;

 if(previous&&elapsed>0&&elapsed<=(typeof liveDisplayInterval==='number'?Math.max(10,liveDisplayInterval/1000*1.75):10)&&data.io&&previous.io){

  const read=Math.max(0,(data.io.read-previous.io.read)/elapsed),write=Math.max(0,(data.io.write-previous.io.write)/elapsed);

  set('#essential-disk','↓ '+bytes(read)+'/s');set('#essential-disk-detail','Read · ↑ '+bytes(write)+'/s write');

 }else if(elapsed!==0||!previous){set('#essential-disk','—');set('#essential-disk-detail','Waiting for consecutive live readings');}

 if(!previous||data.timestamp!==previous.timestamp)workspacePrevious=data;

 if(Date.now()-workspaceRecordAt>15000)loadWorkspaceRecording();

}

async function loadWorkspaceRecording(){

 if(workspaceRecordBusy)return;workspaceRecordBusy=true;workspaceRecordAt=Date.now();

 try{

  const response=await fetch('/api/insights?range=24h');if(!response.ok)throw Error();

  const record=await response.json(),latest=record.events?.[0],fresh=record.lastSaved&&Date.now()/1000-record.lastSaved<30;

  updateMarkup('#overview-recording',`<div class="recording-indicator"><i class="live-dot" aria-hidden="true"></i><strong>${record.recordingError?'Recording needs attention':record.recordingEnabled===false?'Saving is paused':fresh?'Recording locally':'Waiting for saved readings'}</strong></div><div class="recording-number"><strong>${Number(record.summary.events)||0}</strong><span>sustained periods<br>in the last 24 hours</span></div>${latest?`<div class="recording-latest"><small>Latest recorded period</small><strong>${latest.kind==='cpu'?'Processor':'Memory'} · ${Math.round(latest.average)}% average</strong><span>${escapeHtml(new Date(latest.start*1000).toLocaleString())} · ${Math.max(1,Math.round((latest.end-latest.start)/60))} min</span></div>`:''}<p class="workspace-note">${record.recordingError?'Open Performance Insights to review the recording error.':record.lastSaved?'Last saved '+escapeHtml(new Date(record.lastSaved*1000).toLocaleTimeString())+'. Gaps mean no recorded samples.':'Your record builds while the local service is running.'}</p>`);

 }catch{updateMarkup('#overview-recording','<p class="workspace-note">Recording status unavailable. Previously saved history is not a live recording indicator.</p>');}

 finally{workspaceRecordBusy=false;}

}

function renderScanLibrary(){

 const scans=[...folderScanCache.values()].sort((a,b)=>b.updated-a.updated).slice(0,6);

 updateMarkup('#scan-library-list',scans.length?scans.map(scan=>`<button class="scan-library-item" data-library-path="${escapeHtml(scan.path)}" data-help="${escapeHtml(scan.path)} · Scanned ${escapeHtml(new Date(scan.updated*1000).toLocaleString())}${scan.errors?' · Some entries unreadable':''}"><span class="tile blue">${icon('storage')}</span><span><strong>${escapeHtml(scan.path.split(/[\\/]/).filter(Boolean).pop()||scan.path)}</strong><small>${escapeHtml(new Date(scan.updated*1000).toLocaleDateString())}${scan.errors?' · Some entries unreadable':''}</small></span><span aria-hidden="true">→</span></button>`).join(''):'<div class="library-empty"><strong>Your first scan becomes a baseline.</strong><p>Choose a location below. Return later to browse it without rescanning, or scan again to discover changes.</p></div>');

}

function storageFindingModel(scan){

 const items=[...(scan.items||[])].sort((a,b)=>b.size-a.size),files=[...(scan.files||[])].sort((a,b)=>b.size-a.size);

 const measured=Number.isFinite(scan.size)?scan.size:items.reduce((sum,item)=>sum+item.size,0);

 return {largest:items[0],file:files[0],measured,partial:!!(scan.running||scan.cancelled||scan.failure||scan.indexMissing||scan.treeLimited||scan.errors),filtered:scan.filteredCount!==undefined&&($('#storage-search').value!==''||Number($('#storage-minimum').value)>0)};

}

function renderStorageFindings(scan){

 const container=$('#storage-findings');container.hidden=!scan.updated||scan.running||folderLoading;

 if(container.hidden)return;

 const model=storageFindingModel(scan),largest=model.largest;

 const percent=largest&&model.measured?Math.min(100,largest.size/model.measured*100):0;

 updateMarkup('#storage-findings',`<div class="finding-header"><span class="workspace-eyebrow">SCAN PERSPECTIVE</span><span class="finding-badge">${model.partial?'Limited coverage':model.filtered?'Filtered view':Date.now()/1000-scan.updated>86400?'Older snapshot':'Saved snapshot'}</span></div><div class="finding-grid"><div><small>${model.filtered?'Largest matching item':'Largest listed item'}</small><strong>${largest?escapeHtml(largest.name):'No listed contents'}</strong><p>${largest?bytes(largest.size)+(model.measured?' · '+percent.toFixed(0)+'% of measured folder size':''):'Try another location or reset your filters.'}</p></div><div><small>Largest individual file found</small><strong>${model.file?escapeHtml(model.file.name):'No file details available'}</strong><p>${model.file?bytes(model.file.size):'File coverage depends on the saved scan.'}</p></div></div><p class="workspace-note">${model.partial?'Some entries or browsing details are missing. Totals and rankings describe only what this snapshot retained.':'Logical file sizes, not a reclaimable-space estimate. Folder contents and largest files overlap.'} ${scan.source?'Browsing a snapshot of '+escapeHtml(scan.source)+'.':''}</p><div class="finding-actions">${largest?`<button class="button secondary" ${largest.kind==='file'?'data-folder':'data-scan-path'}="${escapeHtml(largest.path)}">Review largest item ↗</button>`:''}<button class="link" data-storage-large>Review files over 1 GB</button><button class="link" data-storage-compare>Compare this location →</button></div>`);

}

document.addEventListener('click',async event=>{

 const button=event.target.closest('button');if(!button)return;

 if(button.dataset.libraryPath){await exploreFolder(button.dataset.libraryPath);$('.folder-card').scrollIntoView({block:'start',behavior:'instant'});}

 if(button.dataset.leaderSort){leaderSort=button.dataset.leaderSort;document.querySelectorAll('[data-leader-sort]').forEach(control=>{const selected=control.dataset.leaderSort===leaderSort;control.classList.toggle('selected',selected);control.setAttribute('aria-pressed',String(selected));});renderWorkspaceOverview();}

 if(button.dataset.reviewGroup){sort=leaderSort;processAscending=false;processFilter='all';all=true;$('#search').value=button.dataset.reviewGroup;document.querySelectorAll('[data-process-filter]').forEach(control=>{const selected=control.dataset.processFilter==='all';control.classList.toggle('selected',selected);control.setAttribute('aria-pressed',String(selected));});changeView('processes');}

 if(button.dataset.storageLarge!==undefined){resultMode='files';$('#storage-minimum').value='1073741824';$('#storage-search').value='';syncStorageTabs();await updateStorageFilter();}

 if(button.dataset.storageCompare!==undefined){const source=storage?.source||storage?.path;await changeView('changes');if(source&&storageChanges.some(location=>scanKey(location.path)===scanKey(source))){$('#changes-location').value=storageChanges.find(location=>scanKey(location.path)===scanKey(source)).path;renderChanges();}}

});

if(data)renderWorkspaceOverview();

renderScanLibrary();
