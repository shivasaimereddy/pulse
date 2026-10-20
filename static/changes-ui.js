let storageChanges=[],changesMode='items',changesRequest=0,changesTimelineContext=null;
function currentChanges(){return storageChanges.find(location=>location.path===$('#changes-location').value);}
const signedBytes=value=>(value>0?'+':value<0?'−':'')+bytes(Math.abs(value));
async function loadChanges(){
 const request=++changesRequest;$('#refresh-changes').disabled=true;set('#changes-status','Reading saved comparisons...');
 try{
  const response=await fetch('/api/storage/changes');const result=await response.json();
  if(!response.ok)throw Error(result.error||'Changes could not be loaded.');
  if(request!==changesRequest)return;
  const selected=$('#changes-location').value;storageChanges=result.locations;changesTimelineContext=null;
  $('#changes-location').innerHTML=storageChanges.length?storageChanges.map(location=>`<option value="${escapeHtml(location.path)}">${escapeHtml(location.path)}</option>`).join(''):'<option value="">No saved scans yet</option>';
  if(storageChanges.some(location=>location.path===selected))$('#changes-location').value=selected;
  else if(storageChanges.length)$('#changes-location').value=(storageChanges.find(location=>location.comparison?.available)||storageChanges[0]).path;
  renderChanges();
 }catch(e){if(request===changesRequest){set('#changes-status',e.message);$('#changes-content').hidden=true;$('#changes-empty').hidden=true;}}
 finally{if(request===changesRequest)$('#refresh-changes').disabled=false;}
}
function renderChanges(){
 const location=currentChanges(),comparison=location?.comparison;
 const ready=!!comparison?.available;
 $('#changes-content').hidden=!ready;$('#changes-empty').hidden=ready;
 $('#changes-location').disabled=!storageChanges.length;
 if(!ready){
  set('#changes-status',location?'A comparison needs two complete scans of the same location.':'Your first comparison starts with a folder scan.');
  set('#changes-empty-detail',comparison?.reason||'Scan a folder, then scan it again later. Pulse will show which contents grew, shrank, appeared, or are no longer listed.');
  set('#changes-scan',location?'Open in Storage':'Go to Storage');return;
 }
 const c=comparison;
 set('#changes-status',(changesTimelineContext?'Timeline comparison · Refresh returns to the latest scans · ':'Saved comparison · updated ')+new Date(c.currentAt*1000).toLocaleString());
 set('#changes-net',signedBytes(c.net));$('#changes-net').dataset.direction=c.net>0?'up':c.net<0?'down':'flat';
 set('#changes-added',signedBytes(c.added));set('#changes-reduced',signedBytes(-c.reduced));
 set('#changes-net-detail',c.net>0?'More space used in this location':c.net<0?'Less space used in this location':'No net size change');
 const largest=c.items[0];
 set('#changes-headline',largest?`${largest.name} ${largest.status==='new'?'appeared':largest.status==='missing'?'is no longer listed':largest.status==='replaced'?'changed type':largest.delta>0?'grew':'shrunk'}`:c.fileCount?'Changes inside your folders':'Sizes are holding steady.');
 set('#changes-interval',new Date(c.previousAt*1000).toLocaleString()+' → '+new Date(c.currentAt*1000).toLocaleString());
 set('#changes-view-help',changesMode==='files'?'Individual file changes found in comparable saved folder listings.':'Immediate contents of this location. Folder changes include everything inside them.');
 const all=c[changesMode]||[],filter=$('#changes-filter').value;
 const rows=all.filter(item=>filter==='all'||filter==='increased'&&(item.delta>0||item.status==='new')||filter==='reduced'&&(item.delta<0||item.status==='missing'));
 const labels={new:'Newly listed',missing:'No longer listed',grown:'Grown',shrunk:'Reduced',replaced:'Type changed'};
 const max=Math.max(1,...rows.map(item=>Math.abs(item.delta)));
 $('#changes-list').innerHTML=rows.map(item=>`<div class="change-row"><span class="tile ${item.kind==='folder'?'blue':'purple'}">${icon(item.kind==='folder'?'storage':'apps')}</span><div class="change-identity"><strong>${escapeHtml(item.name)}</strong>${item.path.slice(location.path.length).replace(/^[\\/]+/,'')!==item.name?`<small title="${escapeHtml(item.path)}">${escapeHtml(item.path.slice(location.path.length).replace(/^[\\/]+/,''))}</small>`:''}<div class="change-meta"><span>${labels[item.status]||'Changed'}</span><span>${bytes(item.before)} → ${bytes(item.after)}</span></div><div class="change-track"><i style="width:${Math.abs(item.delta)/max*100}%" class="${item.delta<0?'reduction':'growth'}"></i></div></div><div class="change-action"><strong class="${item.delta<0?'reduction':'growth'}">${signedBytes(item.delta)}</strong><button class="link" data-folder="${escapeHtml(item.status==='missing'?location.path:item.path)}">${item.status==='missing'?'Open location':'Review'} ↗</button></div></div>`).join('')||`<div class="changes-no-results"><h3>${c.count||c.fileCount?'No changes match this view.':'No size changes found.'}</h3><p>${c.count||c.fileCount?'Choose another view or filter.':'The comparable entries have the same sizes in both snapshots.'}</p></div>`;
 const count=changesMode==='files'?c.fileCount:c.count;
 set('#changes-coverage',`${rows.length} shown${count>200?` · Largest 200 of ${count} changes retained`:''}.${changesMode==='files'&&!c.detailed?' Nested file comparison begins after two scans with the new folder index.':''}${c.limited?' Some folders were outside the saved index limit. File details cover comparable listings only.':''} Same-size edits are not detected; this view compares size and presence, not file contents.`);
}
$('#refresh-changes').onclick=loadChanges;
$('#changes-location').onchange=renderChanges;
$('#changes-filter').onchange=renderChanges;
$('#changes-open-folder').onclick=()=>{const location=currentChanges();if(location)action({action:'folder',path:location.path});};
$('#changes-scan').onclick=async()=>{const location=currentChanges();changeView('storage');if(location)await showFolderScan(location.path);};
document.querySelectorAll('[data-changes-mode]').forEach(button=>button.onclick=()=>{
 changesMode=button.dataset.changesMode;document.querySelectorAll('[data-changes-mode]').forEach(other=>{other.classList.toggle('selected',other===button);other.setAttribute('aria-pressed',String(other===button));});renderChanges();
});
