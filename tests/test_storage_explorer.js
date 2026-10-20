const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),requests=[],posts=[];
function node(){return {open:false,hidden:false,innerHTML:'',textContent:'',value:'',style:{},events:{},classList:{add(){},remove(){}},addEventListener(k,v){this.events[k]=v},showModal(){this.open=true},close(){this.open=false;this.events.close?.()},focus(){},setAttribute(){},querySelectorAll(){return []},getBoundingClientRect(){return {width:800,height:400}}}}
const $=selector=>{if(!nodes.has(selector))nodes.set(selector,node());return nodes.get(selector)};
const root='C:\\',source='C:\\Users\\demo\\Documents';
const cache=new Map([[source.replaceAll('\\','/').toLowerCase(),{path:source,updated:100}]]);
let scanState={running:false};
const context=vm.createContext({$,data:{disks:[{path:root,type:'NTFS',used:400,free:600,total:1000,percent:40}]},storage:null,view:'storage',folderScanCache:cache,scanKey:p=>(p||'').replaceAll('\\','/').replace(/\/+$/,'').toLowerCase(),bytes:n=>n+' B',escapeHtml:s=>String(s).replaceAll('<','&lt;').replaceAll('"','&quot;'),icon:()=>'',set:(id,v)=>$(id).textContent=v,activeFolderScan:null,document:{body:node()},window:{addEventListener(){}},setTimeout(){},clearTimeout(){},setInterval(){},URLSearchParams,Date,Math,Number,loadSavedScans:async()=>{},pollStorage(){},toast(){},action(){},post:async(path,body)=>{posts.push({path,body});scanState={running:true,path:body.path,visited:5};},fetch:async url=>{requests.push(url);if(url==='/api/storage')return {ok:true,json:async()=>scanState};return {ok:true,json:async()=>({path:source,source,updated:100,size:100,items:[{path:source+'\\Folder',name:'Folder',size:100,kind:'folder'}],nextOffset:null})}}});
const map=fs.readFileSync('static/storage-map.js','utf8');vm.runInContext(map.slice(0,map.indexOf('let storageMapRows')),context);
vm.runInContext(fs.readFileSync('static/storage-explorer.js','utf8'),context);
(async()=>{
 await vm.runInContext('openStorageExplorer()',context);
 assert.equal($('#storage-explorer').open,true);assert.match($('#explorer-map').innerHTML,/Map it to see the detail/);assert.match($('#explorer-locations').innerHTML,/Documents/);
 assert.equal($('#explorer-drive-used').textContent,'400 B');assert.equal(posts.length,0,'Opening explorer must never start a scan');
 context.source=source;await vm.runInContext('browseExplorer(source,source)',context);
 assert.match($('#explorer-map').innerHTML,/data-explorer-item/);assert.match($('#explorer-coverage').textContent,/Folder snapshot/);assert.equal($('#explorer-locations').hidden,true);
 $('#storage-explorer').events.click({target:{closest(){return {dataset:{explorerItem:'0'}}}}});assert.match($('#explorer-inspector-content').innerHTML,/Open saved folder/);
 assert.equal(posts.length,0,'Selection and saved browsing must not scan');
 // Simulate a page-wide refresh publishing a fresh scan before the explorer sees it.
 cache.set('c:',{path:root,updated:200});scanState={path:root,updated:200,running:false};
 await vm.runInContext('selectExplorerDrive("C:\\\\")',context);
 const before=requests.filter(url=>url.startsWith('/api/storage/browse')).length;await vm.runInContext('pollExplorerScan()',context);assert.ok(requests.filter(url=>url.startsWith('/api/storage/browse')).length>before,'A newly saved scan must refresh even if another view already updated the scan cache');
 await Promise.all([vm.runInContext('startExplorerScan()',context),vm.runInContext('startExplorerScan()',context)]);
 assert.equal(posts.length,1,'Concurrent clicks must not start duplicate scans');assert.equal(posts[0].body.path,root);
 $('#storage-explorer').close();assert.equal(posts.length,1,'Closing explorer must not cancel the scan');
 console.log('Explorer checks passed: capacity vs snapshot separation, explicit scanning, saved browsing, selection, refresh and lifecycle.');
})().catch(error=>{console.error(error);process.exitCode=1});
