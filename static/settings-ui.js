let settingsInfo=null,settingsRequest=0,settingsMutation=false;
const settingsSections=['workspace','recording','data'];
function selectSettingsSection(section,focus=false){
 if(!settingsSections.includes(section))section='workspace';
 settingsSections.forEach(name=>{
  const tab=$('#settings-tab-'+name),selected=name===section;
  tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
  $('#settings-panel-'+name).hidden=!selected;
  if(selected&&focus)tab.focus();
 });
 try{sessionStorage.setItem('pulse.settingsSection',section);}catch{}
}
settingsSections.forEach((name,index)=>{
 const tab=$('#settings-tab-'+name);tab.onclick=()=>selectSettingsSection(name);
 tab.onkeydown=event=>{
  const next=event.key==='ArrowRight'?(index+1)%3:event.key==='ArrowLeft'?(index+2)%3:event.key==='Home'?0:event.key==='End'?2:null;
  if(next!==null){event.preventDefault();selectSettingsSection(settingsSections[next],true);}
 };
});
let savedSettingsSection='workspace';
try{savedSettingsSection=sessionStorage.getItem('pulse.settingsSection')||'workspace';}catch{}
selectSettingsSection(savedSettingsSection);
function saveBrowserPreference(key,value){
 try{localStorage.setItem(key,value);set('#settings-browser-status','Saved for this browser.');return true;}
 catch{set('#settings-browser-status','Applied for this session. Browser storage is unavailable, so this preference may not survive a restart.');return false;}
}
function syncBrowserSettings(){
 $('#settings-refresh').value=String(liveDisplayInterval);
 try{const start=localStorage.getItem('pulse.startView');$('#settings-start').value=['overview','activity','storage'].includes(start)?start:'overview';}catch{$('#settings-start').value='overview';}
 $('#settings-theme').value=$('#theme-select').value||'system';
}
async function loadSettings(){
 const request=++settingsRequest;$('#refresh-settings').disabled=true;
 syncBrowserSettings();
 try{
  const response=await fetch('/api/settings');if(response.status===404)throw Error('Restart Pulse to enable the updated settings.');
  const result=await response.json();if(!response.ok)throw Error(result.error||'Settings could not be loaded.');
  if(request!==settingsRequest)return;
  settingsInfo=result;
  $('#settings-recording').checked=result.recordingEnabled;$('#settings-recording').disabled=settingsMutation;
  set('#settings-recording-state',result.recordingError?'Recording needs attention: '+result.recordingError:!result.recordingEnabled?'Saving is paused. Live monitoring continues.':result.lastSaved?'Recording locally · Last saved '+new Date(result.lastSaved*1000).toLocaleString():'Recording enabled · Waiting for the first saved readings.');
  $('#settings-recording-dot').dataset.state=result.recordingError?'error':result.recordingEnabled?'active':'paused';
  set('#settings-database-size',bytes(result.databaseBytes));set('#settings-database-path',result.database);
  set('#settings-scan-count',result.scanCount+' saved storage '+(result.scanCount===1?'snapshot':'snapshots'));
  $('#settings-clear-storage').disabled=settingsMutation||result.storageScanning||!result.scanCount;
  $('#settings-clear-performance').disabled=settingsMutation;
  $('#settings-open-data').disabled=false;$('#settings-copy-data').disabled=false;
  $('#settings-change-database').disabled=settingsMutation||result.storageScanning;
  set('#settings-status',result.storageScanning?'A storage scan is running. Stop it before clearing storage history.':'Connected to your local Pulse service.');
 }catch(error){if(request===settingsRequest){settingsInfo=null;set('#settings-status',error.message);['#settings-recording','#settings-clear-performance','#settings-clear-storage','#settings-open-data','#settings-copy-data','#settings-change-database'].forEach(id=>$(id).disabled=true);set('#settings-recording-state','Recording status unavailable');}}
 finally{if(request===settingsRequest)$('#refresh-settings').disabled=false;}
}
$('#refresh-settings').onclick=loadSettings;
$('#settings-theme').onchange=()=>saveBrowserPreference('pulse.appearance',$('#settings-theme').value);
$('#settings-start').onchange=()=>{const value=$('#settings-start').value;if(['overview','activity','storage'].includes(value))saveBrowserPreference('pulse.startView',value);};
$('#settings-refresh').onchange=()=>{
 const value=Number($('#settings-refresh').value);if(![2000,5000,10000].includes(value))return;
 liveDisplayInterval=value;lastDisplayPoll=0;saveBrowserPreference('pulse.refreshInterval',String(value));if(!paused)set('#connection',liveConnectionLabel());
};
$('#settings-recording').onchange=async()=>{
 if(!settingsInfo||settingsMutation)return;
 settingsMutation=true;$('#settings-recording').disabled=true;
 try{await post('/api/settings',{recordingEnabled:$('#settings-recording').checked});workspaceRecordAt=0;toast($('#settings-recording').checked?'Performance history recording enabled.':'Saving performance history paused. Live monitoring continues.');}
 catch(error){toast(error.message);}
 finally{settingsMutation=false;await loadSettings();}
};
$('#settings-open-data').onclick=()=>{if(settingsInfo)action({action:'folder',path:settingsInfo.database});};
$('#settings-copy-data').onclick=async()=>{
 if(!settingsInfo)return;
 try{await navigator.clipboard.writeText(settingsInfo.database);set('#settings-copy-status','Database path copied.');}
 catch{set('#settings-copy-status','Clipboard unavailable. Select the database path above to copy it.');}
};
$('#settings-clear-storage').onclick=()=>$('#clear-storage-dialog').showModal();
$('#settings-clear-performance').onclick=()=>$('#clear-performance-dialog').showModal();
$('#keep-performance-history').onclick=()=>$('#clear-performance-dialog').close();
$('#confirm-clear-performance').onclick=async()=>{
 if(settingsMutation)return;
 settingsMutation=true;$('#confirm-clear-performance').disabled=true;
 try{
  await post('/api/history/clear',{confirm:true});
  insightsRequest++;historyRequest++;activityRequest++;
  insightsData=null;savedHistory=null;activityData=null;workspaceRecordAt=0;
  ['#insights-events','#history-plot','#history-app-list','#activity-events'].forEach(id=>$(id).replaceChildren());
  $('#clear-performance-dialog').close();toast('Performance history cleared. Storage snapshots were kept.');
 }catch(error){toast(error.message);}
 finally{settingsMutation=false;$('#confirm-clear-performance').disabled=false;await loadSettings();}
};
setInterval(()=>{if(view==='settings'&&!settingsMutation&&!$('#refresh-settings').disabled)loadSettings();},15000);

let databaseChanging=false;
$('#settings-change-database').onclick=()=>{
 if(!settingsInfo||settingsMutation)return;
 $('#database-selected-path').value='';$('#database-confirm').disabled=true;
 set('#database-change-status','Choose a location. Existing Pulse history opens in place; a new file starts empty.');
 $('#database-dialog').showModal();
};
$('#database-cancel').onclick=()=>{if(!databaseChanging)$('#database-dialog').close();};
$('#database-dialog').addEventListener('cancel',event=>{if(databaseChanging)event.preventDefault();});
function selectDatabasePath(path){
 $('#database-selected-path').value=path||'';
 $('#database-confirm').disabled=!path||path===settingsInfo?.database;
 set('#database-change-status',path===settingsInfo?.database?'This database is already in use.':path?'Ready to switch. Your previous database will be kept.':'No file selected. Your database has not changed.');
}
$('#database-default').onclick=()=>{if(!databaseChanging)selectDatabasePath(settingsInfo?.defaultDatabase);};
$('#database-browse').onclick=async()=>{
 if(databaseChanging)return;
 databaseChanging=true;$('#database-browse').disabled=true;$('#database-confirm').disabled=true;
 $('#database-default').disabled=true;$('#database-cancel').disabled=true;
 set('#database-change-status','Choose a file in the Windows dialog. Check your taskbar if it is behind this window.');
 try{const response=await post('/api/database/choose');selectDatabasePath((await response.json()).path);}
 catch(error){set('#database-change-status',error.message);}
 finally{databaseChanging=false;$('#database-browse').disabled=false;$('#database-default').disabled=false;$('#database-cancel').disabled=false;}
};
function reloadDatabaseWorkspace(){
 try{sessionStorage.removeItem('pulse.storageView');}catch{}
 window.location.reload();
}
$('#database-confirm').onclick=async()=>{
 const path=$('#database-selected-path').value;if(databaseChanging||!path)return;
 databaseChanging=true;settingsMutation=true;
 ['#database-confirm','#database-cancel','#database-browse','#database-default'].forEach(id=>$(id).disabled=true);
 set('#database-change-status','Saving pending history and opening your selected database…');
 try{
  await post('/api/database/switch',{path,confirm:true});
  try{localStorage.setItem('pulse.databaseChanged',String(Date.now()));}catch{}
  reloadDatabaseWorkspace();
 }catch(error){set('#database-change-status',error.message);}
 finally{
  databaseChanging=false;settingsMutation=false;
  ['#database-confirm','#database-cancel','#database-browse','#database-default'].forEach(id=>$(id).disabled=false);
 }
};
window.addEventListener('storage',event=>{if(event.key==='pulse.databaseChanged')reloadDatabaseWorkspace();});
