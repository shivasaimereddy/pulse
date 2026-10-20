// A dedicated saved-snapshot explorer. Drive capacity and scanned logical sizes stay separate.
let explorerDrive=null,explorerSource=null,explorerPath=null,explorerSnapshot=null,explorerSelection=null;
let explorerRequest=0,explorerLoading=false,explorerPollBusy=false,explorerScanState=null,explorerStamp=null,explorerStarting=false;
const explorerDialog=$('#storage-explorer');
function driveForExplorer(path,drives){return drives.filter(d=>scanKey(path)===scanKey(d.path)||scanKey(path).startsWith(scanKey(d.path)+'/')).sort((a,b)=>b.path.length-a.path.length)[0];}
function explorerSavedLocations(){return [...folderScanCache.values()].filter(scan=>driveForExplorer(scan.path,data?.disks||[])?.path===explorerDrive).sort((a,b)=>b.updated-a.updated);}
function explorerCurrentDrive(){return data?.disks.find(d=>d.path===explorerDrive);}
function renderExplorerDrive(){
 const drive=explorerCurrentDrive();if(!drive)return;
 set('#explorer-drive-used',bytes(drive.used));set('#explorer-drive-free',bytes(drive.free));set('#explorer-drive-total',bytes(drive.total));
 $('#explorer-drive-bar').style.width=Math.max(0,Math.min(100,drive.percent))+'%';
 const scanning=!!explorerScanState?.running||explorerStarting;
 $('#explorer-scan').disabled=scanning||explorerLoading;
 set('#explorer-scan',folderScanCache.has(scanKey(drive.path))?'Refresh drive scan':'Scan entire drive');
 $('#explorer-scan-progress').hidden=!scanning;
 if(scanning){set('#explorer-progress-title','Scanning '+(explorerScanState?.path||explorerDrive));set('#explorer-progress-detail',`${Number(explorerScanState?.visited||0).toLocaleString()} files checked · ${explorerScanState?.errors||0} unreadable entries · Closing this explorer keeps the scan running.`);}
}
async function openStorageExplorer(){
 if(!data?.disks.length){toast('Waiting for Windows drive readings.');return;}
 if(explorerDialog.open)return;
 const opening=++explorerRequest;explorerDialog.showModal();document.body.classList.add('explorer-open');
 $('#explorer-drive').innerHTML=data.disks.map(d=>`<option value="${escapeHtml(d.path)}">${escapeHtml(d.path)} · ${escapeHtml(d.type)}</option>`).join('');
 const drive=driveForExplorer(storage?.path||'',data.disks)||data.disks[0];
 explorerScanState=activeFolderScan;
 try{await loadSavedScans();}catch{set('#explorer-status','Saved locations could not be loaded. Retry by choosing a drive.');}
 if(!explorerDialog.open||opening!==explorerRequest)return;
 await selectExplorerDrive(drive.path);pollExplorerScan();
}
async function selectExplorerDrive(path){
 explorerDrive=path;$('#explorer-drive').value=path;explorerSource=null;explorerPath=path;explorerSnapshot=null;explorerSelection=null;explorerStamp=null;
 const saved=folderScanCache.get(scanKey(path));
 if(saved)await browseExplorer(saved.path,saved.path);else{++explorerRequest;explorerLoading=false;set('#explorer-status','');renderStorageExplorer();}
}
async function browseExplorer(source,path,more=false){
 const request=++explorerRequest,previous=explorerSnapshot;
 explorerLoading=true;if(!more){explorerSource=source;explorerPath=path;explorerSnapshot=null;explorerSelection=null;}
 set('#explorer-status',more?'Loading more saved contents…':'Opening saved snapshot…');renderStorageExplorer();
 try{
  const offset=more?previous?.nextOffset||0:0;
  const response=await fetch('/api/storage/browse?'+new URLSearchParams({source,path,offset:String(offset),order:'size'}));
  let result=await response.json();
  if(!response.ok){
   const root=folderScanCache.get(scanKey(source));
   if(response.status===404&&scanKey(source)===scanKey(path)&&root?.items?.length)result=root;
   else throw Error(result.error||'This location has no retained folder details. Refresh its original scan to map it.');
  }
  if(request!==explorerRequest||!explorerDialog.open)return;
  if(more)result={...result,items:[...(previous.items||[]),...(result.items||[])]};
  explorerSnapshot=result;explorerStamp=result.updated;set('#explorer-status','');
 }catch(error){if(request===explorerRequest&&explorerDialog.open)set('#explorer-status',error.message+' Your files have not changed.');}
 finally{if(request===explorerRequest){explorerLoading=false;if(explorerDialog.open){renderStorageExplorer();if(!more){explorerDialog.scrollTop=0;$('#explorer-location-name').focus({preventScroll:true});}}}}
}
function renderExplorerBreadcrumbs(){
 const drive=explorerCurrentDrive();if(!drive)return;
 const crumbs=[{path:drive.path,label:drive.path,source:''}];
 if(explorerSource&&scanKey(explorerSource)!==scanKey(drive.path))crumbs.push({path:explorerSource,label:explorerSource.split(/[\\/]/).filter(Boolean).pop(),source:explorerSource});
 const root=explorerSource||drive.path;
 if(explorerPath&&scanKey(explorerPath)!==scanKey(root)){
  const tail=explorerPath.slice(root.replace(/[\\/]+$/,'').length).split(/[\\/]/).filter(Boolean);let current=root.replace(/[\\/]+$/,'');
  for(const part of tail){current+='\\'+part;crumbs.push({path:current,label:part,source:root});}
 }
 $('#explorer-breadcrumbs').innerHTML=crumbs.map((c,index)=>`<button data-explorer-crumb="${escapeHtml(c.path)}" data-explorer-source="${escapeHtml(c.source)}" ${index===crumbs.length-1?'aria-current="location"':''}>${escapeHtml(c.label)}</button>`).join('<span aria-hidden="true">/</span>');
}
function renderExplorerInspector(){
 const scan=explorerSnapshot,item=explorerSelection;
 const label=item?.name||(explorerPath?.split(/[\\/]/).filter(Boolean).pop())||explorerDrive;
 const size=item?.size??scan?.size;
 const model=scan?storageMapItems(scan.items||[]):null;
 const share=item&&model?.total?item.size/model.total*100:null;
 $('#explorer-inspector-content').innerHTML=`<span class="workspace-eyebrow">${item?'SELECTED ITEM':'LOCATION DETAILS'}</span><span class="explorer-item-symbol">${icon(item?.kind==='file'?'apps':'storage')}</span><h3>${escapeHtml(label||'Your storage')}</h3><p class="explorer-item-path">${escapeHtml(item?.path||explorerPath||'')}</p><div class="explorer-item-size">${Number.isFinite(size)?bytes(size):'Not scanned'}</div><p class="explorer-item-size-label">${Number.isFinite(size)?'Saved logical size':'Drive capacity is shown above'}</p>${share!==null?`<div class="explorer-share-track"><i style="width:${Math.min(100,share)}%"></i></div><p class="workspace-note">${share.toFixed(1)}% of displayed contents</p>`:''}${scan?`<dl class="explorer-item-facts"><div><dt>Snapshot</dt><dd>${escapeHtml(new Date(scan.updated*1000).toLocaleString())}</dd></div><div><dt>Coverage</dt><dd>${scan.errors||scan.cancelled||scan.failure||scan.treeLimited?'Limited · review skipped entries':'Readable entries in saved scan'}</dd></div>${item?.modified?`<div><dt>Modified</dt><dd>${escapeHtml(new Date(item.modified*1000).toLocaleDateString())}</dd></div>`:''}</dl>`:''}${item?.kind==='folder'?'<button class="button primary" id="explorer-browse-selected">Open saved folder →</button>':''}${item?.aggregate?'<p class="workspace-note">Smaller entries are grouped to keep the map readable. Review the individual items below the map.</p>':`<button class="button secondary" id="explorer-open-selected">${item?.kind==='file'?'Show in Explorer':'Open in Explorer'} ↗</button>`}<button class="link explorer-back-map" id="explorer-back-map">← Back to map</button><div class="explorer-inspector-note"><strong>Review before acting.</strong><p>Logical size can differ from space on disk. Pulse does not delete files or estimate a safe cleanup amount.</p></div>`;
}
function renderExplorerMap(){
 const scan=explorerSnapshot,map=$('#explorer-map');
 if(!scan){
  map.innerHTML=explorerLoading?'<div class="explorer-empty"><span class="explorer-empty-icon">'+icon('history')+'</span><h3>Opening your saved view…</h3><p>Reading local snapshot details.</p></div>':`<div class="explorer-empty"><span class="explorer-empty-icon">${icon('storage')}</span><span class="workspace-eyebrow">START WITH A BASELINE</span><h3>Your drive has a story.<br>Map it to see the detail.</h3><p>Capacity tells you how much is used. A drive scan shows the folders behind that number.</p><button class="button primary" data-explorer-start>Scan ${escapeHtml(explorerDrive)} →</button><small>Read-only scan · Large drives can take time · Unreadable entries are reported</small></div>`;
  return;
 }
 const model=storageMapItems(scan.items||[]),rect=map.getBoundingClientRect();
 if(!model.items.length){map.innerHTML='<div class="explorer-empty"><h3>No non-empty items in this snapshot.</h3><p>Choose another location or refresh the original scan.</p></div>';return;}
 const width=rect.width||800,height=rect.height||430;
 const hues=[218,174,265,35,329,196,151,285];
 map.innerHTML=layoutStorageMap(model.items,width,height).map(({item,x,y,width:w,height:h},index)=>{
  const compact=w<145||h<95,tiny=w<55||h<35,share=item.size/model.total*100;
  return `<button class="map-tile explorer-map-tile${compact?' compact':''}${h<64?' short':''}${tiny?' tiny':''}${explorerSelection?.name===item.name?' is-selected':''}" style="left:${x/width*100}%;top:${y/height*100}%;width:${w/width*100}%;height:${h/height*100}%;--map-hue:${item.aggregate?220:hues[index%hues.length]}" data-explorer-item="${index}" data-help="${escapeHtml(item.name+' · '+bytes(item.size)+' · '+share.toFixed(1)+'% of displayed contents. Select to inspect.') }" aria-label="${escapeHtml(item.name+' · '+bytes(item.size)+' · '+share.toFixed(1)+'%. Select to inspect.')}" aria-pressed="${explorerSelection?.name===item.name}"><span class="map-tile-surface"><span class="map-tile-heading"><span>${escapeHtml(item.name)}</span>${!compact?'<i aria-hidden="true">'+(item.aggregate?'⋯':item.kind==='folder'?'↗':'·')+'</i>':''}</span><span class="map-tile-size">${bytes(item.size)}${!compact?'<small>'+share.toFixed(1)+'% of view</small>':''}</span></span></button>`;
 }).join('');
}
function renderStorageExplorer(){
 if(!explorerDialog.open)return;
 renderExplorerDrive();renderExplorerBreadcrumbs();renderExplorerInspector();
 const scan=explorerSnapshot,locations=explorerSavedLocations();
 set('#explorer-location-name',scan?(explorerPath.split(/[\\/]/).filter(Boolean).pop()||explorerPath):'Your drive, mapped.');
 set('#explorer-map-meta',scan?`${bytes(storageMapItems(scan.items||[]).total)} in displayed contents · ${new Date(scan.updated*1000).toLocaleString()}`:'Select a saved location below, or scan the entire drive.');
 set('#explorer-coverage',explorerLoading?'Loading snapshot':!scan?'Not yet mapped':scan.errors||scan.cancelled||scan.failure||scan.treeLimited?'Limited coverage':scanKey(explorerSource)!==scanKey(explorerDrive)?'Folder snapshot':'Drive snapshot');
 set('#explorer-map-note',scan?`Select a tile to inspect. Folder sizes include descendants.${scan.nextOffset!=null?' This map covers loaded entries; more are available.':''}`:'Saved locations are separate snapshots. Overlapping sizes are never added together.');
 $('#explorer-load-more').hidden=scan?.nextOffset==null;$('#explorer-load-more').disabled=explorerLoading;
 $('#explorer-locations').hidden=!!scan||!locations.length;
 $('#explorer-locations').innerHTML=locations.length?'<h4>Available snapshots on this drive</h4><div>'+locations.map(location=>`<button data-explorer-location="${escapeHtml(location.path)}"><span>${icon('storage')}</span><span><strong>${escapeHtml(location.path.split(/[\\/]/).filter(Boolean).pop()||location.path)}</strong><small>${escapeHtml(location.path)}</small><small>${escapeHtml(new Date(location.updated*1000).toLocaleString())}</small></span><i aria-hidden="true">→</i></button>`).join('')+'</div>':'';
 $('#explorer-items').innerHTML=scan?'<details class="explorer-contents"><summary class="explorer-list-heading"><strong>Contents by size</strong><span>'+scan.items.length+' loaded'+(scan.filteredCount!==undefined?' / '+scan.filteredCount:'')+'</span><i aria-hidden="true">⌄</i></summary>'+scan.items.map((item,index)=>`<button class="explorer-list-row" data-explorer-row="${index}"><span class="explorer-list-kind">${icon(item.kind==='file'?'apps':'storage')}</span><span>${escapeHtml(item.name)}<small>${item.kind==='file'?'File':'Folder'}</small></span><strong>${bytes(item.size)}</strong><i aria-hidden="true">↗</i></button>`).join('')+'</details>':'';
 renderExplorerMap();
}
async function startExplorerScan(){
 if(explorerScanState?.running||explorerStarting)return;
 explorerStarting=true;$('#explorer-scan').disabled=true;
 try{await post('/api/storage/scan',{path:explorerDrive});explorerScanState={running:true,path:explorerDrive,visited:0};renderStorageExplorer();await pollExplorerScan();}
 catch(error){set('#explorer-status',error.message);}
 finally{explorerStarting=false;if(explorerDialog.open)renderExplorerDrive();}
}
async function pollExplorerScan(){
 if(!explorerDialog.open||explorerPollBusy)return;explorerPollBusy=true;
 try{
  const response=await fetch('/api/storage');if(!response.ok)throw Error('Unable to read scan progress.');
  const state=await response.json();if(!explorerDialog.open)return;explorerScanState=state;
  if(!state.running&&state.updated&&!state.cancelled&&!state.failure){
   if(folderScanCache.get(scanKey(state.path))?.updated!==state.updated)await loadSavedScans();
   if(!explorerDialog.open)return;
   if(driveForExplorer(state.path,data?.disks||[])?.path===explorerDrive&&scanKey(state.path)===scanKey(explorerSource||explorerDrive)&&folderScanCache.get(scanKey(state.path))?.updated===state.updated&&explorerStamp!==state.updated){await browseExplorer(state.path,explorerPath||state.path);}
  }
  renderExplorerDrive();
  if(driveForExplorer(state.path,data?.disks||[])?.path===explorerDrive&&state.failure)set('#explorer-status','Scan did not finish: '+state.failure+'. Previous saved results are kept.');
  else if(driveForExplorer(state.path,data?.disks||[])?.path===explorerDrive&&state.cancelled)set('#explorer-status','Scan stopped. Previous saved results are kept.');
 }catch(error){if(explorerDialog.open)set('#explorer-status',error.message);}
 finally{explorerPollBusy=false;}
}
$('#open-storage-explorer-card').addEventListener('click',openStorageExplorer);
$('#open-storage-explorer-card').addEventListener('keydown',event=>{if(event.target===event.currentTarget&&['Enter',' '].includes(event.key)){event.preventDefault();openStorageExplorer();}});
$('#close-storage-explorer').onclick=()=>explorerDialog.close();
explorerDialog.addEventListener('close',()=>{++explorerRequest;explorerLoading=false;document.body.classList.remove('explorer-open');$('#open-storage-explorer-card').focus();if(view==='storage')pollStorage(true);});
$('#explorer-drive').onchange=()=>selectExplorerDrive($('#explorer-drive').value);
$('#explorer-scan').onclick=startExplorerScan;
$('#explorer-stop').onclick=async()=>{try{await post('/api/storage/cancel');set('#explorer-status','Stopping the scan…');}catch(error){set('#explorer-status',error.message);}};
$('#explorer-load-more').onclick=()=>browseExplorer(explorerSource,explorerPath,true);
explorerDialog.addEventListener('click',event=>{
 const button=event.target.closest('button');if(!button)return;
 if(button.dataset.explorerLocation)browseExplorer(button.dataset.explorerLocation,button.dataset.explorerLocation);
 if(button.dataset.explorerCrumb){const path=button.dataset.explorerCrumb,source=button.dataset.explorerSource;if(!source)selectExplorerDrive(explorerDrive);else browseExplorer(source,path);}
 if(button.dataset.explorerItem!==undefined||button.dataset.explorerRow!==undefined){
  const fromMap=button.dataset.explorerItem!==undefined;
  explorerSelection=fromMap?storageMapItems(explorerSnapshot.items||[]).items[Number(button.dataset.explorerItem)]:explorerSnapshot.items[Number(button.dataset.explorerRow)];
  renderExplorerInspector();if(window.innerWidth<=700)$('#explorer-inspector-content').scrollIntoView({block:'start',behavior:'instant'});explorerDialog.querySelectorAll('[data-explorer-item]').forEach(tile=>tile.setAttribute('aria-pressed',String(storageMapItems(explorerSnapshot.items||[]).items[Number(tile.dataset.explorerItem)]?.name===explorerSelection?.name)));
 }
 if(button.id==='explorer-browse-selected'&&explorerSelection?.kind==='folder')browseExplorer(explorerSource,explorerSelection.path);
 if(button.id==='explorer-back-map')$('.explorer-map-heading').scrollIntoView({block:'start',behavior:'instant'});
 if(button.id==='explorer-open-selected')action({action:'folder',path:explorerSelection?.path||explorerPath});
 if(button.dataset.explorerStart!==undefined)startExplorerScan();
});
let explorerResizeTimer;
window.addEventListener('resize',()=>{clearTimeout(explorerResizeTimer);explorerResizeTimer=setTimeout(()=>{if(explorerDialog.open)renderExplorerMap();},100);});
setInterval(()=>{if(explorerDialog.open)pollExplorerScan();},2500);
