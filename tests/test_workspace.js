const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
const $=id=>{if(!elements.has(id))elements.set(id,{innerHTML:'',textContent:'',value:'',hidden:false,style:{}});return elements.get(id);};
const context=vm.createContext({$,data:null,Date,Number,Math,Map,folderScanCache:new Map(),folderLoading:false,bytes:n=>n+' B',icon:()=>'',escapeHtml:s=>String(s).replaceAll('<','&lt;').replaceAll('"','&quot;'),set:(id,v)=>$(id).textContent=v,groupedProcesses:rows=>rows,fetch:async()=>{throw Error('offline')},document:{addEventListener(){},querySelectorAll:()=>[]}});
vm.runInContext(fs.readFileSync('static/workspace-ui.js','utf8'),context);
function model(scan){context.scan=scan;return vm.runInContext('storageFindingModel(scan)',context);}
let result=model({size:100,items:[{name:'small',size:10},{name:'large',size:80}],files:[{name:'a',size:2},{name:'b',size:9}]});
assert.equal(result.largest.name,'large');assert.equal(result.file.name,'b');assert.equal(result.measured,100);
for(const flag of ['errors','cancelled','failure','indexMissing','treeLimited'])assert.ok(model({[flag]:1}).partial,flag+' must disclose limited coverage');
$('#storage-search').value='cache';assert.equal(model({filteredCount:1}).filtered,true);
$('#storage-search').value='';$('#storage-minimum').value='0';assert.equal(model({filteredCount:1}).filtered,false);
context.scan={updated:100,size:100,items:[{name:'largest',size:80,path:'C:/largest',kind:'folder'}],files:[],errors:1};
vm.runInContext('renderStorageFindings(scan)',context);assert.match($('#storage-findings').innerHTML,/Limited coverage/);assert.match($('#storage-findings').innerHTML,/80%/);assert.match($('#storage-findings').innerHTML,/data-scan-path/);
context.scan.running=true;vm.runInContext('renderStorageFindings(scan)',context);assert.equal($('#storage-findings').hidden,true);
function live(timestamp,read,write){context.data={timestamp,processes:[],memory:{available:100},io:{read,write}};vm.runInContext('renderWorkspaceOverview()',context);}
live(100,100,100);assert.equal($('#essential-disk').textContent,'—');
live(102,300,500);assert.equal($('#essential-disk').textContent,'↓ 100 B/s');assert.match($('#essential-disk-detail').textContent,/200 B\/s/);
live(200,900,900);assert.equal($('#essential-disk').textContent,'—','A recording gap must not imply live throughput');
context.folderScanCache.set('a',{path:'C:/<unsafe>',updated:100});vm.runInContext('renderScanLibrary()',context);assert.match($('#scan-library-list').innerHTML,/&lt;unsafe>/);
console.log('Workspace scenarios passed: ranking, scan coverage, filters, safe paths, disk rates and sampling gaps.');
