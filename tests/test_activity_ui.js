const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map();const $=id=>{if(!nodes.has(id))nodes.set(id,{value:'',innerHTML:'',textContent:'',disabled:false,hidden:false,setAttribute(){},querySelectorAll(){return []}});return nodes.get(id)};
const context=vm.createContext({$,Date,Number,Math,Set,Array,insightDuration:n=>Math.round(n/60)+' min',bytes:n=>n+' B',escapeHtml:s=>String(s).replaceAll('<','&lt;').replaceAll('"','&quot;'),icon:()=>'',set:(id,v)=>$(id).textContent=v,document:{querySelectorAll:()=>[],addEventListener(){}},sessionStorage:{getItem(){return null},setItem(){}},setInterval(){},view:'activity',fetch:async()=>({ok:true,json:async()=>({period:'24h',start:0,events:[],lastSaved:null})})});
vm.runInContext(fs.readFileSync('static/activity-ui.js','utf8'),context);
const performance={id:'performance:x',kind:'performance',start:100,end:300,observation:{id:'x',kind:'cpu',average:80,peak:99,status:'ended',apps:[{name:'<Editor>',cpu:40,memory:500}]}};
const storage={id:'storage:1',kind:'storage',scanId:1,path:'C:/Docs',start:0,end:400,comparison:{net:0,added:10,reduced:10},highlights:[{name:'<file>',delta:10}]};
context.event=performance;assert.match(vm.runInContext('activityEventContent(event,200).detail',context),/began before/);assert.match(vm.runInContext('activityEventContent(event,0).detail',context),/&lt;Editor>/);
context.event=storage;let content=vm.runInContext('activityEventContent(event,0)',context);assert.match(content.title,/no net growth/);assert.match(content.interval,/Between scans/);assert.match(content.detail,/Exact change time is unknown/);
context.event={kind:'gap',start:0,end:300};assert.match(vm.runInContext('activityEventContent(event,0).detail',context),/cause is unknown/);
(async()=>{
 await vm.runInContext('loadActivity()',context);assert.match($('#activity-events').innerHTML,/ready to build/);assert.equal($('#refresh-activity').disabled,false);
 context.fixture={period:'24h',start:0,events:[performance,storage],lastSaved:null};context.fetch=async()=>({ok:true,json:async()=>context.fixture});await vm.runInContext('loadActivity()',context);
 assert.equal($('#activity-performance-count').textContent,'1');assert.equal($('#activity-storage-count').textContent,'1');assert.match($('#activity-events').innerHTML,/Review this comparison/);
 vm.runInContext("activityKind='gap';renderActivity()",context);assert.match($('#activity-events').innerHTML,/No events match/);
 context.fetch=async()=>({ok:false,json:async()=>({error:'Unavailable'})});await vm.runInContext('loadActivity()',context);assert.match($('#activity-status').textContent,/last loaded/);assert.equal($('#activity-storage-count').textContent,'1','Failure should not replace known counts with zero');
 // Older network results must never replace the latest requested period.
 let resolveOld;context.fetch=()=>new Promise(resolve=>resolveOld=resolve);const old=vm.runInContext('loadActivity()',context);
 context.fetch=async()=>({ok:true,json:async()=>({...context.fixture,period:'7d',events:[]})});vm.runInContext("activityPeriod='7d'",context);await vm.runInContext('loadActivity()',context);
 resolveOld({ok:true,json:async()=>context.fixture});await old;assert.equal(vm.runInContext('activityData.period',context),'7d');
 console.log('Activity UI checks passed: evidence, intervals, escaping, filters, empty states, stale data and request races.');
})().catch(error=>{console.error(error);process.exitCode=1});
