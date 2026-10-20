// Exercise script load order against the actual HTML IDs, without a browser dependency.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html=fs.readFileSync('static/index.html','utf8');
const elements=new Map();
function element() {
  return {dataset:{},style:{setProperty(){}},classList:{toggle(){},add(){},remove(){}},value:'',textContent:'',innerHTML:'',
    addEventListener(){},setAttribute(){},querySelectorAll(){return []},options:[],
    getBoundingClientRect(){return {width:800,height:360}},contains(){return false},querySelector(){return null},scrollIntoView(){},replaceChildren(){},append(){},add(){},click(){}};
}
for(const match of html.matchAll(/\bid="([^"]+)"/g))elements.set('#'+match[1],element());
const requests=[];
const sandbox={document:{body:element(),documentElement:element(),querySelector:selector=>elements.get(selector)||null,
  querySelectorAll:()=>[],createElement:element,addEventListener(){}},
  setInterval(){},setTimeout(){},clearTimeout(){},console,AbortController,Option:function(text,value){return {text,value,dataset:{}}},
  fetch:async url=>{requests.push(url);return {ok:true,json:async()=>({})}},
  window:{scrollY:0,requestAnimationFrame(callback){callback();},scrollTo(){},addEventListener(){},matchMedia(){return {matches:false,addEventListener(){}}}},navigator:{},URL,URLSearchParams,Blob};
const context=vm.createContext(sandbox);
for(const script of ['startup.js','theme.js','app.js','storage-ui.js','process-ui.js','changes-ui.js','insights-ui.js','about-ui.js','workspace-ui.js','storage-map.js','storage-explorer.js','activity-ui.js','settings-ui.js','navigation.js']){
  vm.runInContext(fs.readFileSync('static/'+script,'utf8'),context,{filename:script});
}
assert.ok(requests.includes('/api/metrics'),'Shared monitoring must start before optional views load');
assert.equal(typeof elements.get('#search').oninput,'function');
assert.equal(typeof elements.get('#open-task-manager').onclick,'function');
assert.equal(typeof elements.get('#scan').onclick,'function');
console.log('UI initialization check passed.');
vm.runInContext(`
 insightsData={start:100,end:200,since:null,lastSaved:null,events:[],points:[],repeated:[],summary:{events:0,cpuSeconds:0,memorySeconds:0}};
 renderInsights();
 if($('#insights-count').textContent!=='0')throw Error('Insights should show an honest empty state');
 insightsData={...insightsData,since:100,lastSaved:200,events:[{id:'test',kind:'cpu',start:100,end:162,average:90,peak:95,status:'ended',apps:[{id:'app',name:'app.exe',label:'App',cpu:50,memory:1024,peakMemory:2048,presence:1}]}],summary:{events:1,cpuSeconds:62,memorySeconds:0}};
 $('#insights-kind').value='all';renderInsights();
 if(!$('#insights-events').innerHTML.includes('data-insight-app'))throw Error('An insight should include a review action');
 $('#insights-kind').value='memory';renderInsights();
 if(!$('#insights-events').innerHTML.includes('No periods match'))throw Error('Insight resource filter is incorrect');
 $('#insights-kind').value='all';insightsData=null;
`,context);
console.log('Performance insight empty states, event review actions, and resource filters passed.');

vm.runInContext(`
 storage={path:'C:/Restored',updated:1,items:[{name:'a',path:'C:/Restored/a',kind:'file',size:1}],files:[],errors:0};
 resultMode='folders';restoredStorageListScroll={path:storage.path,mode:'folders',top:125};
 folderLoading=true;renderFolderResults();
 if(!restoredStorageListScroll)throw Error('List scroll was restored before saved contents finished loading');
 folderLoading=false;renderFolderResults();
 if($('#storage-list').scrollTop!==125||restoredStorageListScroll!==null)throw Error('List scroll did not restore after saved contents loaded');
 restoredStorageListScroll={path:'C:/Another',mode:'folders',top:300};$('#storage-list').scrollTop=10;renderFolderResults();
 if($('#storage-list').scrollTop!==10)throw Error('An unrelated saved location changed the list scroll position');
 storage=null;restoredStorageListScroll=null;$('#storage-list').scrollTop=0;
`,context);
console.log('Saved storage list scroll waits for matching loaded contents.');

(async()=>{
 await vm.runInContext(`(async()=>{
  renderFolderResults=()=>{}; followScanLocation=()=>{}; renderWsl=()=>{};
  const desktop={path:'C:/Desktop',updated:1,running:false,items:[{name:'report',size:100}],files:[]};
  const downloads={path:'C:/Downloads',updated:2,running:false,items:[{name:'installer',size:200}],files:[]};
  let current=downloads;
  fetch=async url=>({ok:true,json:async()=>url==='/api/storage'?current:{scans:[downloads,desktop],available:true}});
  lastStorageDetail=Date.now();
  await pollStorage();
  showFolderScan('c:/desktop/');
  if(storage.updated!==1)throw Error('Folder selection did not restore its scan');
  await pollStorage();
  if(storage.updated!==1)throw Error('Background polling replaced selected folder');
  showFolderScan('C:/Unscanned');
  if(storage.updated!==null||storage.items.length)throw Error('Unscanned folder showed unrelated results');
  current={...desktop,running:true,updated:null};
  await pollStorage();
  if(!storage.running)throw Error('Active scan did not show progress');
  current={...desktop,running:false,cancelled:true,updated:3};
  await pollStorage();
  if(!storage.cancelled)throw Error('Cancelled scan was not marked partial');
  showFolderScan('C:/Downloads');showFolderScan('C:/Desktop');
  if(storage.updated!==1)throw Error('Cancelled scan replaced successful saved result');
  await pollStorage();
  if(storage.updated!==1)throw Error('Polling restored partial results after returning to saved scan');
  let scanPosts=0;
  post=async()=>{scanPosts++;};
  const source={...desktop,browsable:true};
  folderScanCache.set(scanKey(source.path),source);
  storage=source;
  fetch=async()=>({ok:true,json:async()=>({...source,path:'C:/Desktop/Sub',source:source.path,items:[]})});
  await exploreFolder('C:/Desktop/Sub');
  if(storage.source!=='C:/Desktop'||storage.path!=='C:/Desktop/Sub')throw Error('Saved subtree did not open');
  if(scanPosts)throw Error('Browsing triggered a filesystem scan');
  await exploreFolder('C:/Unknown');
  if(scanPosts)throw Error('Unknown folder scanned without explicit action');
  storage={path:'C:/Desktop',source:'C:/Desktop',indexVersion:2,items:[{path:'C:/Desktop/a',name:'a',size:2}],nextOffset:200,filteredCount:201};
  fetch=async()=>({ok:true,json:async()=>({...storage,items:[{path:'C:/Desktop/b',name:'b',size:1}],nextOffset:null})});
  await loadMoreFolders();
  if(storage.items.length!==2||storage.nextOffset!==null)throw Error('Saved results paging did not append the next page');
  if(scanPosts)throw Error('Loading more saved results triggered a filesystem scan');
  let browseCalls=0;
  const savedIndexed={...desktop,indexVersion:2,browsable:true};
  folderScanCache.set(scanKey(desktop.path),savedIndexed);
  activeFolderScan={...downloads,running:false};
  storage={...savedIndexed,source:desktop.path,filteredCount:1,nextOffset:null};selectedStoragePath=desktop.path;
  folderResultKey=browseResultKey(desktop.path,desktop.path);
  fetch=async()=>{browseCalls++;return {ok:true,json:async()=>storage};};
  resultMode='files';updateStorageFilter();resultMode='folders';await updateStorageFilter();
  if(browseCalls)throw Error('Switching result tabs should reuse loaded folder contents');
  const stored=storage;
  $('#storage-search').value='report';
  let finishBrowse;
  fetch=()=>{browseCalls++;return new Promise(resolve=>finishBrowse=resolve);};
  const pending=showFolderScan(desktop.path,desktop.path);
  if(storage!==stored||!folderLoading)throw Error('Filtering cleared already loaded results');
  finishBrowse({ok:true,json:async()=>({...stored,items:[{name:'report',path:'C:/Desktop/report',size:1}]})});
  await pending;
  if(folderLoading||storage.items[0].name!=='report')throw Error('Filtered results were not committed');
  const viewState=new Map();sessionStorage={getItem:key=>viewState.get(key),setItem:(key,value)=>viewState.set(key,value)};
  resultMode='files';storageTab='windows';saveStorageView();
  resultMode='folders';selectedStoragePath=null;$('#storage-search').value='';restoreStorageView();
  if(resultMode!=='files'||selectedStoragePath!==desktop.path||$('#storage-search').value!=='report')throw Error('Storage context did not restore after reload');


 })()`,context);
 await vm.runInContext(`(async()=>{
 const savedViewTest=new Map();
 sessionStorage={getItem:key=>savedViewTest.get(key),setItem:(key,value)=>savedViewTest.set(key,value)};
 renderProcesses=()=>{};pollStorage=()=>{};loadHistory=()=>{};loadChanges=()=>{};loadInsights=()=>{};loadAbout=()=>{};loadActivity=()=>{};loadSettings=()=>{};
 for(const name of dashboardViews){
  changeView(name);view='overview';await restoreDashboardView();
  if(view!==name)throw Error('Refresh did not restore '+name);
  const sections={settings:'#settings-section',activity:'#activity-section',overview:'#overview',processes:'#process-section',storage:'#storage-section',changes:'#changes-section',history:'#history-section',optimize:'#optimize-section',about:'#about-section'};
  for(const [screen,id] of Object.entries(sections))if($(id).hidden!==(screen!==name))throw Error('Incorrect screen visibility for '+name);
 }
 sessionStorage.setItem('pulse.activeView','invalid');await restoreDashboardView();
 if(view!=='overview')throw Error('Invalid saved screen should fall back to Overview');
 sessionStorage={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}};
 await restoreDashboardView();if(view!=='overview')throw Error('Blocked storage should not break startup');
 })()`,context);
 await vm.runInContext(`(async()=>{
 let revealCount=0,scrollRestored=null,finishRestore;
 sessionStorage={getItem:key=>key==='pulse.activeView'?'storage':key==='pulse.scrollPositions'?'\{\"storage\":792\}':null,setItem(){}};
 const originalChange=changeView;
 changeView=()=>new Promise(resolve=>finishRestore=resolve);
 document.documentElement.classList.remove=()=>{revealCount++;};
 window.scrollTo=options=>{scrollRestored=options.top;};
 const restoring=restoreDashboardView();
 await Promise.resolve();
 if(revealCount||scrollRestored!==null)throw Error('Reload revealed the screen before its data was ready');
 finishRestore();await restoring;
 if(revealCount!==1||scrollRestored!==792)throw Error('Reload did not reveal the completed screen at its saved scroll position');
 changeView=originalChange;
 })()`,context);
 console.log('Startup waits for screen data and restores the exact scroll position before revealing it.');
 console.log('All screens restore after refresh; invalid or blocked storage falls back safely.');
 console.log('Storage switching, polling, and partial-result checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
vm.runInContext(`
 storageChanges=[{path:'C:/Example',updated:2,comparison:null}];
 $('#changes-location').value='C:/Example';renderChanges();
 if(!$('#changes-content').hidden||$('#changes-empty').hidden)throw Error('First scan should explain missing comparison');
 storageChanges[0].comparison={available:true,previousAt:1,currentAt:2,items:[],files:[],count:0,fileCount:0,net:0,added:0,reduced:0,detailed:true};
 renderChanges();
 if($('#changes-content').hidden||!$('#changes-empty').hidden)throw Error('Ready comparison should be visible');
 if($('#changes-net').textContent!=='0 B')throw Error('Net change should show zero');
 storageChanges[0].comparison={available:false,reason:'Incomplete scan'};renderChanges();
 if($('#changes-empty-detail').textContent!=='Incomplete scan')throw Error('Unavailable comparison should show its reason');
`,context);
console.log('Changes view empty, ready, and incomplete states passed.');
