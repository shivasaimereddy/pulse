let aboutInfo=null;
// Installation information is read on demand; no extra polling or telemetry.
async function loadAbout(){
 const button=$('#about-refresh');button.disabled=true;
 set('#about-copy-status','');
 set('#about-status','Loading installation details…');
 try{
  const response=await fetch('/api/about');
  if(!response.ok)throw Error('Installation details are unavailable. Restart Pulse if it was just updated.');
  const info=await response.json();aboutInfo=info;
  set('#about-version','Version '+info.version);
  set('#about-system',info.system);
  set('#about-runtime','Python '+info.python+' · '+info.architecture);
  set('#about-database',info.database);
  set('#about-recording',info.recording?'Performance recording is active':info.recordingError?'Needs attention: '+info.recordingError:info.recordingEnabled===false?'Saving is paused in Settings':'Not recording');
  set('#about-status',info.recordingError?'Recording needs attention: '+info.recordingError:'Connected to your local Pulse service.');
  $('#about-local-status').dataset.state=info.recording?'active':info.recordingError?'error':'idle';
  $('#about-copy').disabled=false;
 }catch(error){
  aboutInfo=null;$('#about-copy').disabled=true;$('#about-local-status').dataset.state='idle';
  set('#about-status',error.message);
  ['#about-version','#about-system','#about-runtime','#about-database','#about-recording'].forEach(id=>set(id,'Unavailable'));
 }finally{button.disabled=false;}
}
$('#about-refresh').onclick=loadAbout;

$('#about-copy').disabled=true;
$('#about-copy').onclick=async()=>{
 if(!aboutInfo)return;
 const i=aboutInfo;
 const details=['Pulse '+i.version,'System: '+i.system,'Runtime: Python '+i.python+' / '+i.architecture,'Recording: '+(i.recording?'Active':i.recordingError||'Inactive'),'Database: '+i.database].join('\n');
 try{if(!navigator.clipboard?.writeText)throw Error();await navigator.clipboard.writeText(details);set('#about-copy-status','Diagnostic details copied. Review before sharing.');}
 catch{set('#about-copy-status','Clipboard access is unavailable. Select and copy the details above.');}
};
