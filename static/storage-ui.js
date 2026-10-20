let storageDetails=null,storageTab='windows',resultMode='folders',storageLoading=false,lastStorageDetail=0;
let showPartialScan=false;
let activeFolderScan=null,selectedStoragePath=null,savedScansLoaded=false,savedScanStamp=null;
const folderScanCache=new Map();
const scanKey=path=>(path||'').replace(/\\/g,'/').replace(/\/+$/,'').toLowerCase();
let folderLoading=false,folderResultKey=null,restoredStorageListScroll=null;
function saveStorageView(){
 try{sessionStorage.setItem('pulse.storageView',JSON.stringify({path:selectedStoragePath,source:storage?.source||null,mode:resultMode,tab:storageTab,search:$('#storage-search').value,minimum:$('#storage-minimum').value,sort:$('#storage-sort').value,listScroll:$('#storage-list').scrollTop||0}));}catch{}
}
function restoreStorageView(){
 try{
  const saved=JSON.parse(sessionStorage.getItem('pulse.storageView')||'null');
  if(!saved||typeof saved!=='object')return;
  selectedStoragePath=typeof saved.path==='string'?saved.path:null;
  if(Number.isFinite(saved.listScroll))restoredStorageListScroll={path:selectedStoragePath,mode:saved.mode,top:Math.max(0,saved.listScroll)};
  restoredStorageSource=typeof saved.source==='string'?saved.source:null;
  resultMode=saved.mode==='files'?'files':'folders';storageTab=saved.tab==='wsl'?'wsl':'windows';
  $('#storage-search').value=typeof saved.search==='string'?saved.search:'';
  $('#storage-minimum').value=['0','10485760','104857600','1073741824'].includes(saved.minimum)?saved.minimum:'0';
  $('#storage-sort').value=['size','name','modified','oldest'].includes(saved.sort)?saved.sort:'size';
 }catch{}
 syncStorageTabs();
}
let restoredStorageSource=null;
function syncStorageTabs(){
 document.querySelectorAll('[data-result-mode]').forEach(b=>{const selected=b.dataset.resultMode===resultMode;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));});
 document.querySelectorAll('[data-storage-tab]').forEach(b=>{const selected=b.dataset.storageTab===storageTab;b.classList.toggle('selected',selected);b.setAttribute('aria-pressed',String(selected));});
 $('#windows-storage-pane').hidden=storageTab!=='windows';$('#wsl-storage-pane').hidden=storageTab!=='wsl';
}
function browseResultKey(source,path){return JSON.stringify([scanKey(source),folderScanCache.get(scanKey(source))?.updated,scanKey(path),$('#storage-search').value,$('#storage-minimum').value,$('#storage-sort').value]);}
const folderColors=['#63a6ed','#b7a2df','#7fc6b5','#ecc087','#95b6ca','#d6dbe5'];
function emptyFolderScan(path){return {path,items:[],files:[],running:false,updated:null,errors:0};}
async function loadSavedScans(){
 const response=await fetch('/api/storage/saved');const payload=await response.json();
 if(!response.ok)throw Error(payload.error||'Saved scans are unavailable.');
 for(const item of payload.scans)folderScanCache.set(scanKey(item.path),item);
 // Match the bounded database rather than keeping every explored location in memory.
 const retained=new Set(payload.scans.map(item=>scanKey(item.path)));
 for(const key of folderScanCache.keys())if(!retained.has(key))folderScanCache.delete(key);
 savedScansLoaded=true;if(typeof renderScanLibrary==='function')renderScanLibrary();
 set('#saved-scan-note',payload.available?'Last successful scans for up to 20 locations are saved on this laptop, including after a restart.':'Scan history is unavailable.');
 $('#saved-scan-locations').innerHTML='<option value="">Recent scans...</option>'+payload.scans.map(item=>`<option value="${escapeHtml(item.path)}">${escapeHtml(item.path)} · ${new Date(item.updated*1000).toLocaleString()}</option>`).join('');
}
function followScanLocation(path){
 if(!path)return;const select=$('#scan-scope');
 if(!Array.from(select.options).some(option=>option.value===path)){
  select.querySelectorAll('[data-custom]').forEach(option=>option.remove());
  const option=new Option(path,path);option.dataset.custom='true';select.add(option);
 }
 select.value=path;
}
let folderBrowseRequest=0;
async function showFolderScan(path, source=null){
 const request=++folderBrowseRequest;
 const same=scanKey(selectedStoragePath)===scanKey(path)&&scanKey(storage?.path)===scanKey(path);
 selectedStoragePath=path;showPartialScan=false;
 const direct=folderScanCache.get(scanKey(path));
 const parent=direct?.indexVersion===2&&!source?direct:source?folderScanCache.get(scanKey(source)):[...folderScanCache.values()].filter(scan=>scan.browsable&&scanKey(path).startsWith(scanKey(scan.path)+'/')).sort((a,b)=>b.updated-a.updated)[0];
 const key=parent?browseResultKey(parent.path,path):null;
 if(!same||folderResultKey!==key)$('#storage-list').scrollTop=0;
 if(same&&key&&folderResultKey===key&&storage.filteredCount!==undefined){folderLoading=false;renderFolderResults();saveStorageView();return;}
 folderLoading=false;
 if(!same||(!parent&&!direct)){storage=activeFolderScan?.running&&scanKey(activeFolderScan.path)===scanKey(path)?activeFolderScan:(!source&&direct)||emptyFolderScan(path);folderResultKey=null;}
 followScanLocation(path);
 const fetchSaved=parent&&(parent.indexVersion===2||scanKey(path)!==scanKey(parent.path));
 if(!fetchSaved){renderFolderResults();saveStorageView();return;}
 folderLoading=true;renderFolderResults();saveStorageView();
 try{
  const response=await fetch(folderBrowseUrl(parent.path,path));const result=await response.json();
  if(request!==folderBrowseRequest)return;
  if(!response.ok){
   if(response.status!==404)throw Error(result.error||'Saved folder could not be read.');
   storage={...emptyFolderScan(path),updated:parent.updated,indexMissing:true,missingSource:parent.path,source:parent.path};
  }else{storage=result;folderResultKey=key;}
 }catch(e){if(request===folderBrowseRequest)toast(e.message||'Saved folder could not be opened. Try again.');}
 finally{if(request===folderBrowseRequest){folderLoading=false;renderFolderResults();saveStorageView();}}
}
function folderBrowseUrl(source,path,offset=0){
 return '/api/storage/browse?'+new URLSearchParams({source,path,offset:String(offset),search:$('#storage-search').value,minimum:$('#storage-minimum').value||'0',order:$('#storage-sort').value||'size'});
}
let loadingMoreFolders=false;
async function loadMoreFolders(){
 if(folderLoading||loadingMoreFolders||storage?.nextOffset==null)return;
 loadingMoreFolders=true;
 const request=folderBrowseRequest,shown=storage;
 $('#storage-load-more').disabled=true;
 try{
  const response=await fetch(folderBrowseUrl(shown.source||shown.path,shown.path,shown.nextOffset));
  const result=await response.json();if(!response.ok)throw Error(result.error||'More results could not be loaded.');
  if(request!==folderBrowseRequest)return;
  storage={...result,items:[...shown.items,...result.items]};renderFolderResults();
 }catch(e){toast(e.message);}finally{loadingMoreFolders=false;$('#storage-load-more').disabled=false;}
}
function updateStorageFilter(){
 saveStorageView();
 if(resultMode==='folders'&&storage?.indexVersion===2&&!storage.running)return showFolderScan(storage.path,storage.source||storage.path);
 else renderFolderResults();
}
async function exploreFolder(path){
 if(activeFolderScan?.running)return toast('Stop the current scan before changing locations.');
 const source=storage?.source||storage?.path;
 const within=source&&scanKey(path).startsWith(scanKey(source)+'/');
 if(source&&scanKey(path)===scanKey(source))return showFolderScan(path);
 await showFolderScan(path,within?source:null);
}
async function startFolderScan(path){
 if(activeFolderScan?.running)return toast('Stop the current scan before exploring another folder.');
 try{await post('/api/storage/scan',path?{path}:{});++folderBrowseRequest;selectedStoragePath=path||selectedStoragePath;storage=emptyFolderScan(selectedStoragePath);folderResultKey=null;folderLoading=false;saveStorageView();await pollStorage();}catch(e){toast(e.message);}
}
function renderStorageDrives(){
 if(!data)return;
 const total=data.disks.reduce((s,d)=>s+d.total,0),free=data.disks.reduce((s,d)=>s+d.free,0);
 set('#storage-used',bytes(total-free));set('#storage-total',`used of ${bytes(total)}`);set('#storage-free',bytes(free));
 $('#capacity-ring').style.setProperty('--used',`${total?(total-free)/total*100:0}%`);
 $('#drives').innerHTML=data.disks.map(d=>`<article class="card drive-card"><div class="drive-card-top"><span class="tile blue">${icon('storage')}</span><div><h3>${escapeHtml(d.path)}</h3><small>${escapeHtml(d.type)} · Windows volume</small></div><span class="pill ${d.percent>=85?'warn':''}">${d.percent>=85?'Getting full':'Available'}</span></div><div class="drive-card-space"><strong>${bytes(d.free)}</strong><span>free of ${bytes(d.total)}</span></div><div class="progress"><i style="width:${d.percent}%;background:${d.percent>=85?'#e2ac5b':'#7daee4'}"></i></div><div class="drive-card-bottom"><span>${d.percent.toFixed(0)}% used</span><button class="link" data-scan-path="${escapeHtml(d.path)}">Explore drive →</button></div></article>`).join('');
}
function renderFolderResults(){
 if(!storage)return;const s=storage,running=!!activeFolderScan?.running;
 followScanLocation(s.path);if(typeof renderStorageFindings==='function')renderStorageFindings(s);
 const status=folderLoading?'Loading saved results...':s.indexMissing?'This folder was scanned, but its details were not retained in the older snapshot. Refresh the original scan once to enable saved browsing.':s.failure?`Scan could not finish: ${s.failure}`:s.saving?'Saving folder index...':s.running?'Scanning... results appear as folders finish.':s.cancelled?'Scan stopped. These are partial results. The last successful scan is still saved.':s.updated?(s.source?'From saved scan · ':'Saved scan · ')+new Date(s.updated*1000).toLocaleString():'No saved scan for this location. Choose Scan location to start.';
 set('#scan-status',`${status}${s.errors?` ${s.errors.toLocaleString()} inaccessible entries skipped.`:''}`);
 $('#clear-storage-history').disabled=running||!folderScanCache.size;$('#scan').disabled=running;$('#scan-custom').disabled=running;$('#scan-scope').disabled=running;$('#saved-scan-locations').disabled=running;$('#cancel-scan').hidden=!running;$('#cancel-scan').disabled=!!s.saving;
 set('#scan',s.running?'Scanning...':s.updated?'Scan again':'Scan location');
 set('#storage-view-help',resultMode==='files'?'The 50 largest individual files anywhere inside this folder.':'Immediate contents. Folder sizes include everything inside. Open a folder to browse saved results.');
 $('#refresh-storage-index').hidden=!s.indexMissing&&!s.treeLimited;
 set('#scan-index-note',s.treeLimited&&!s.indexMissing?'This older scan has incomplete browsing details. Refresh it once to retain all readable folders.':'');
 set('#folder-path',s.path);$('#folder-path').title=s.path;
 $('#folder-up').disabled=running||!s.path||/^[A-Za-z]:[\\/]?$/.test(s.path);$('#open-scan-folder').disabled=!s.path;
 const listedBytes=(s.items||[]).reduce((sum,item)=>sum+item.size,0);
 const scanned=Number.isFinite(s.size)?s.size:listedBytes;
 $('#scan-stats').hidden=!s.updated&&!s.running;
 $('#scan-stats').innerHTML=`<span><b>${bytes(scanned)}</b> measured in folder</span><span><b>${Number.isFinite(s.visited)?s.visited.toLocaleString():'—'}</b> files checked</span><span><b>${s.errors||0}</b> unreadable entries</span>`;
 const previous=s.previous,comparable=s.filteredCount===undefined&&previous&&!s.running&&!s.cancelled&&!s.failure&&!s.errors&&!previous.errors&&s.totalItems<=500&&previous.totalItems<=500;
 const delta=comparable?listedBytes-previous.listedBytes:null;
 set('#scan-change',delta===null?'':`${delta>0?'+':delta<0?'-':''}${bytes(Math.abs(delta))} ${delta>0?'more':delta<0?'less':'change'} in listed items since ${new Date(previous.updated*1000).toLocaleString()}.`);
 $('#export-storage').disabled=!s.updated||s.running;
 const largest=(s.items||[]).slice(0,5),rest=Math.max(0,scanned-largest.reduce((sum,x)=>sum+x.size,0));
 const breakdown=[...largest,...(rest?[{name:'Other contents',size:rest}]:[])];
 $('#folder-breakdown').hidden=true;$('#folder-breakdown').innerHTML=scanned?`<div class="folder-segments">${breakdown.map((item,i)=>`<span style="width:${item.size/scanned*100}%;background:${folderColors[i]}" title="${escapeHtml(item.name)} · ${bytes(item.size)}"></span>`).join('')}</div><div class="folder-segment-legend">${breakdown.map((item,i)=>`<span><i style="background:${folderColors[i]}"></i>${escapeHtml(item.name)}</span>`).join('')}</div>`:'';
 let rows=[...(resultMode==='files'?s.files||[]:s.items||[])];
 const query=$('#storage-search').value.toLowerCase(),minimum=Number($('#storage-minimum').value),order=$('#storage-sort').value;
 if(resultMode==='files'||s.indexVersion!==2||s.filteredCount===undefined)rows=rows.filter(item=>item.name.toLowerCase().includes(query)&&item.size>=minimum);
 if(resultMode==='files'||s.indexVersion!==2||s.filteredCount===undefined)rows.sort(order==='name'?(a,b)=>a.name.localeCompare(b.name):order==='modified'?(a,b)=>(b.modified||0)-(a.modified||0):order==='oldest'?(a,b)=>(a.modified||0)-(b.modified||0):(a,b)=>b.size-a.size);
 if(typeof renderStorageMap==='function')renderStorageMap(rows,s);
 const max=Math.max(1,...rows.map(item=>item.size));
 $('#storage-list').innerHTML=rows.map(item=>{
  const file=item.kind==='file',unknown=!item.kind;
  return `<div class="storage-row ${resultMode==='files'?'file-result':''}"><span class="tile ${file?'purple':'blue'}">${icon(file?'apps':'storage')}</span><div class="storage-content"><div class="drive-header">${file||unknown?`<b>${escapeHtml(item.name)}</b>`:`<button class="folder-name" data-scan-path="${escapeHtml(item.path)}" ${running?'disabled':''}>${escapeHtml(item.name)} <span>›</span></button>`}<strong>${bytes(item.size)}</strong></div><div class="storage-path">${escapeHtml(resultMode==='files'?item.path.slice((s.path||'').length).replace(/^[\\/]+/,''):item.path)}</div><div class="file-meta">${unknown?'Saved result · rescan to enable drill-down':file?'File':'Folder'}${item.modified?' · Modified '+new Date(item.modified*1000).toLocaleDateString():''}</div><div class="progress"><i style="width:${item.size/max*100}%"></i></div></div><button class="button secondary" data-folder="${escapeHtml(item.path)}">Review ↗</button></div>`;
 }).join('')||(folderLoading?'<div class="storage-empty" role="status">Loading saved results...</div>':`<div class="storage-empty"><span class="tile blue">${icon('storage')}</span><h3>${s.indexMissing?'Saved details need a refresh.':s.updated||s.running?'Nothing matches this view.':'Explore this location.'}</h3><p>${s.indexMissing?'Refresh the original scan once. Files were measured, but this folder was omitted by the previous index limit.':s.updated||s.running?'Try resetting filters, or switch between folders and largest files.':'Run a scan to discover what is taking up space. Switching folders will bring back their saved results.'}</p></div>`);
 $('#storage-load-more').hidden=resultMode!=='folders'||s.nextOffset==null;$('#storage-load-more').disabled=folderLoading||loadingMoreFolders;
 $('#storage-list').setAttribute('aria-busy',String(folderLoading));
 if(restoredStorageListScroll&&s.updated&&!folderLoading&&scanKey(s.path)===scanKey(restoredStorageListScroll.path)&&resultMode===restoredStorageListScroll.mode){$('#storage-list').scrollTop=restoredStorageListScroll.top;restoredStorageListScroll=null;}
 set('#storage-result-count',`${rows.length} results${resultMode==='files'?' · Top 50 largest files found in this scan':s.filteredCount!==undefined?` · ${rows.length} of ${s.filteredCount} matching contents`:s.totalItems>500?' · Showing the 500 largest immediate children':''}. ${s.treeLimited?'Older snapshot has incomplete browsing details. Refresh its original scan once. ':!s.browsable&&s.updated?'Older snapshot: scan again once to enable browsing without rescanning. ':''}Logical file sizes; cloud placeholders and compressed files may occupy less disk space. Links and reparse points are skipped.`);
}
function renderWsl(){
 if(!storageDetails)return;const w=storageDetails.wsl;
 const openDisks=new Set(Array.from($('#wsl-distros').querySelectorAll('details[open]')).map(el=>el.dataset.virtualDisk));
 set('#wsl-count',w.distros.length?String(w.distros.length):'');
 set('#wsl-status',w.error?`WSL could not be fully inspected: ${w.error}`:w.running?'Reading WSL storage...':w.updated?`Updated ${new Date(w.updated*1000).toLocaleTimeString()} · refreshes at most once a minute`:'Checking registered distributions...');
 $('#wsl-refresh').disabled=w.running;
 $('#wsl-distros').innerHTML=[...w.distros].sort((a,b)=>Number(b.running)-Number(a.running)).map(d=>{
  const root=d.mounts?.find(m=>m.path==='/'),mounts=d.mounts?.filter(m=>m.path!=='/')||[],disk=d.disk;
  const hostDrive=disk?.path.match(/[A-Za-z]:\\/),hostDisk=hostDrive?data?.disks.find(volume=>volume.path.slice(0,2).toUpperCase()===hostDrive[0].slice(0,2).toUpperCase()):null;
  return `<article class="card distro-card"><div class="distro-heading"><span class="tile purple">${icon('laptop')}</span><div><h3>${escapeHtml(d.name)}</h3><small>WSL ${d.version} · ${d.running?'Running':'Stopped'}</small></div>${d.running?`<button class="link" data-wsl-open="${escapeHtml(d.name)}" data-linux-path="/">Open Linux files ↗</button>`:'<span class="pill">Not started by Pulse</span>'}</div><div class="distro-stats"><div><small>Used inside Linux</small><strong>${root?bytes(root.used):'—'}</strong><span>${root?`${root.percent.toFixed(0)}% of Linux filesystem`:d.running?'Reading unavailable':'Start distro to read usage'}</span></div><div><small>Windows disk footprint</small><strong>${disk?bytes(disk.allocatedBytes??disk.fileBytes):'—'}</strong><span>${disk?(disk.allocatedBytes!==null?'Allocated on host drive':'Virtual disk file length'):'Virtual disk not found / inaccessible'}</span></div><div><small>Linux virtual capacity</small><strong>${root?bytes(root.total):'—'}</strong><span>Maximum filesystem size, not extra disk</span></div></div>${root?`<div class="progress"><i style="width:${root.percent}%;background:#b6a1dc"></i></div><p class="wsl-root-note">/ · ${bytes(root.free)} available inside Linux.${hostDisk?` Host ${escapeHtml(hostDisk.path)} has ${bytes(hostDisk.free)} free.`:''} Growth is limited by available space on the Windows host.</p>`:''}${d.error?`<p class="storage-warning">${escapeHtml(d.error)}</p>`:''}${disk?`<details class="virtual-disk-detail" data-virtual-disk="${escapeHtml(d.name)}" ${openDisks.has(d.name)?'open':''}><summary>Virtual disk details</summary><p>${escapeHtml(disk.path)}</p><p>File length ${bytes(disk.fileBytes)}${disk.allocatedBytes!==null?' · Allocated '+bytes(disk.allocatedBytes):''}. Already included in Windows drive usage.</p></details>`:''}<div class="mount-list"><h4>Mounted filesystems${mounts.length?' · '+mounts.length:''}</h4>${mounts.length?mounts.map(m=>`<div class="mount-row"><div><strong>${escapeHtml(m.path)}</strong><small>${escapeHtml(m.source)} · ${escapeHtml(m.type)}</small></div><div><span>${bytes(m.used)} used / ${bytes(m.total)}</span><small class="${m.windows?'mount-alias':''}">${m.windows?'Windows drive · already counted':m.shared?'Shares Linux root filesystem':'Additional mounted filesystem'}</small></div></div>`).join(''):`<p>${d.running?'No additional disk mounts reported.':'Mounts are inspected only while this distribution is running.'}</p>`}</div></article>`;
 }).join('')||`<article class="card"><p>${w.error?'WSL details are unavailable. Windows monitoring continues.':w.running?'Looking for your Linux environments...':'No WSL distributions registered for the account running Pulse.'}</p></article>`;
 if(w.extraDisks?.length)$('#wsl-distros').insertAdjacentHTML('beforeend',w.extraDisks.map(d=>`<article class="card extra-disk"><span class="tile blue">${icon('storage')}</span><div><h3>${escapeHtml(d.name)}</h3><p>${bytes(d.allocatedBytes??d.fileBytes)} ${d.allocatedBytes!==null?'allocated on Windows':'file length'} · already included in drive usage</p><small>${escapeHtml(d.path)}</small></div></article>`).join(''));
 const options=w.distros.filter(d=>d.running).map(d=>`<option value="${escapeHtml(d.name)}">${escapeHtml(d.name)}</option>`).join('');
 if($('#wsl-scan-distro').innerHTML!==options){const selected=$('#wsl-scan-distro').value;$('#wsl-scan-distro').innerHTML=options;if(w.distros.some(d=>d.running&&d.name===selected))$('#wsl-scan-distro').value=selected;}
 const scan=w.scan;$('#wsl-scan').disabled=scan.running||!options;$('#wsl-scan-distro').disabled=scan.running;$('#wsl-scan-scope').disabled=scan.running;
 set('#wsl-scan',scan.running?'Analyzing...':'Analyze Linux folder');
 set('#wsl-scan-status',scan.running?`Reading ${scan.distro}: ${scan.path}... no files are changed.`:scan.error?scan.error:scan.updated?`${scan.distro} · ${scan.path} · ${new Date(scan.updated*1000).toLocaleTimeString()} · Allocated sizes, excluding other filesystems.`:options?'Choose a folder to analyze. Reads only; large scans can take up to 90 seconds.':'Start a Linux distribution yourself to enable folder analysis.');
 $('#wsl-scan-results').innerHTML=scan.items.map(item=>`<div class="linux-folder-row"><div><strong>${escapeHtml(item.path)}</strong>${item.path===scan.path?'<small>Selected folder total · includes children below</small>':''}</div><span>${bytes(item.size)}</span><button class="link" data-wsl-open="${escapeHtml(scan.distro)}" data-linux-path="${escapeHtml(item.path)}">Review ↗</button></div>`).join('');
}
async function pollStorage(force=false){
 if(storageLoading)return;storageLoading=true;
 try{
  const requests=[fetch('/api/storage').then(async r=>{
   if(!r.ok)throw Error('Folder scan is unavailable.');activeFolderScan=await r.json();const current=activeFolderScan;
   if(!savedScansLoaded||(!current.running&&current.updated&&current.updated!==savedScanStamp)){
    await loadSavedScans();
    // A scan is published before its background save finishes. Retry until it is durable.
    if(!current.updated||current.cancelled||current.failure||folderScanCache.get(scanKey(current.path))?.updated===current.updated)savedScanStamp=current.updated;
   }
   if(!selectedStoragePath)selectedStoragePath=current.path;
   if(current.running){
    if(folderLoading||scanKey(selectedStoragePath)!==scanKey(current.path))++folderBrowseRequest;
    folderLoading=false;folderResultKey=null;selectedStoragePath=current.path;showPartialScan=true;storage=current;
    renderFolderResults();saveStorageView();return;
   }
   if(folderLoading)return;
   const same=scanKey(selectedStoragePath)===scanKey(current.path);
   if(same&&showPartialScan&&(current.cancelled||current.failure)){storage=current;renderFolderResults();return;}
   const source=storage?.source||restoredStorageSource;
   const root=folderScanCache.get(scanKey(source||selectedStoragePath));
   if(storage&&!storage.running&&!storage.saving&&scanKey(storage.path)===scanKey(selectedStoragePath)&&storage.updated&&root?.updated===storage.updated)return;
   restoredStorageSource=null;
   await showFolderScan(selectedStoragePath,source&&root?source:null);

  })];
  if(force||Date.now()-lastStorageDetail>=5000){lastStorageDetail=Date.now();requests.push(fetch('/api/storage/details').then(async r=>{
   if(!r.ok)throw Error('Storage details are unavailable.');storageDetails=await r.json();
   if(!$('#scan-scope').dataset.loaded){$('#scan-scope').innerHTML=storageDetails.scopes.map(s=>`<option value="${escapeHtml(s.path)}">${escapeHtml(s.name)}</option>`).join('');$('#scan-scope').dataset.loaded='true';followScanLocation(selectedStoragePath||storage?.path);}
   renderWsl();
  }));}
  const results=await Promise.allSettled(requests);for(const result of results)if(result.status==='rejected')toast(result.reason.message);
 }finally{storageLoading=false;}
}
document.querySelectorAll('[data-storage-tab]').forEach(button=>button.onclick=()=>{
 storageTab=button.dataset.storageTab;document.querySelectorAll('[data-storage-tab]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});$('#windows-storage-pane').hidden=storageTab!=='windows';$('#wsl-storage-pane').hidden=storageTab!=='wsl';saveStorageView();pollStorage(true);
});
document.querySelectorAll('[data-result-mode]').forEach(button=>button.onclick=()=>{
 resultMode=button.dataset.resultMode;$('#storage-list').scrollTop=0;document.querySelectorAll('[data-result-mode]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});updateStorageFilter();
});
$('#scan-scope').onchange=()=>showFolderScan($('#scan-scope').value);
$('#saved-scan-locations').onchange=()=>{const path=$('#saved-scan-locations').value;if(path)showFolderScan(path);};
$('#reset-storage-filters').onclick=()=>{$('#storage-search').value='';$('#storage-minimum').value='0';$('#storage-sort').value='size';updateStorageFilter();};
$('#export-storage').onclick=()=>{
 if(!storage?.updated||storage.running)return;
 const quote=value=>'"'+String(value??'').replace(/"/g,'""')+'"';
 const rows=[['Scan folder','Scanned at','View','Path','Kind','Bytes','Modified'],...['items','files'].flatMap(key=>(storage[key]||[]).map(item=>[storage.path,new Date(storage.updated*1000).toISOString(),key==='items'?'Immediate children':'Largest files',item.path,item.kind,item.size,item.modified?new Date(item.modified*1000).toISOString():'']))];
 const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(row=>row.map(value=>quote(/^[=+@\-]/.test(String(value))?"'"+value:value)).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download='pulse-storage-scan.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
$('#scan').onclick=()=>startFolderScan($('#scan-scope').value);
$('#scan-custom').onclick=()=>{const path=$('#custom-scan-path').value.trim();if(path)startFolderScan(path);else toast('Paste a local folder path first.');};
$('#cancel-scan').onclick=async()=>{try{await post('/api/storage/cancel');toast('Stopping the scan...');pollStorage();}catch(e){toast(e.message);}};
$('#folder-up').onclick=()=>{const path=storage?.path?.replace(/[\\/]+$/,'');if(path){const parent=path.slice(0,path.lastIndexOf('\\'))+'\\';exploreFolder(parent);}};
$('#open-scan-folder').onclick=()=>{if(storage?.path)action({action:'folder',path:storage.path});};
let storageSearchTimer;
$('#storage-search').oninput=()=>{clearTimeout(storageSearchTimer);storageSearchTimer=setTimeout(updateStorageFilter,200);};$('#storage-sort').onchange=updateStorageFilter;$('#storage-minimum').onchange=updateStorageFilter;
$('#storage-load-more').onclick=loadMoreFolders;
$('#refresh-storage-index').onclick=()=>startFolderScan(storage.missingSource||storage.source||storage.path);
$('#wsl-refresh').onclick=async()=>{try{await post('/api/storage/wsl-refresh');await pollStorage(true);}catch(e){toast(e.message);}};
$('#wsl-scan').onclick=async()=>{try{await post('/api/storage/wsl-scan',{distro:$('#wsl-scan-distro').value,path:$('#wsl-scan-scope').value});await pollStorage(true);}catch(e){toast(e.message);}};
document.addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;if(button.dataset.scanPath)exploreFolder(button.dataset.scanPath);if(button.dataset.wslOpen)action({action:'wsl-folder',distro:button.dataset.wslOpen,path:button.dataset.linuxPath});});
renderStorageDrives();

$('#clear-storage-history').onclick=()=>$('#clear-storage-dialog').showModal();
$('#keep-storage-history').onclick=()=>$('#clear-storage-dialog').close();
$('#confirm-clear-storage').onclick=async()=>{
 const button=$('#confirm-clear-storage');button.disabled=true;
 try{
  await post('/api/storage/clear-history');
  ++folderBrowseRequest;folderLoading=false;folderResultKey=null;folderScanCache.clear();savedScanStamp=null;savedScansLoaded=false;showPartialScan=false;
  activeFolderScan=null;storage=emptyFolderScan(selectedStoragePath);
  $('#clear-storage-dialog').close();renderFolderResults();
  await pollStorage(true);if(view==='settings')await loadSettings();toast('All saved folder scan history deleted. Your files are unchanged.');
 }catch(e){toast(e.message);}finally{button.disabled=false;}
};

restoreStorageView();

$('#storage-list').addEventListener('scroll',saveStorageView,{passive:true});
