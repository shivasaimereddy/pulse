const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync('static/app.js','utf8');
const context=vm.createContext({data:null,bytes:n=>n+' B'});
vm.runInContext(source.slice(source.indexOf('function observationWindow'),source.indexOf('function quickCard')),context);
function snapshot(count=46,cpu=80,memory=85){return {timestamp:1000,history:Array.from({length:count},(_,i)=>({time:1000-(count-1-i)*2,cpu,memory})),disks:[],battery:null};}
function observations(value){context.data=value;return vm.runInContext('recommendations()',context);}
assert.equal(observations(snapshot(10)).length,0,'Brief spikes must not trigger sustained observations');
assert.equal(observations(snapshot()).length,2,'Continuous high CPU and RAM should be observed');
let value=snapshot();value.history[20].cpu=20;
assert.equal(observations(value).filter(x=>x.icon==='cpu').length,0,'An average cannot hide a below-threshold reading');
value=snapshot();value.history[value.history.length-5].time-=30;
assert.equal(observations(value).length,0,'Recording gaps must interrupt continuous evidence');
value=snapshot();value.timestamp+=120;
assert.equal(observations(value).length,0,'Old sample windows must not produce current activity claims');
value=snapshot(2,10,10);value.disks=[{path:'C:',free:100,percent:90}];
assert.equal(observations(value)[0].view,'storage','Low disk capacity does not require a minute of CPU history');
value=snapshot(46,10,10);value.battery={percent:25,plugged:false};
assert.equal(observations(value)[0].setting,'power');
value.battery.plugged=true;assert.equal(observations(value).length,0);
console.log('Overview observation scenarios passed: spikes, sustained use, threshold dips, gaps, stale samples, disk capacity, battery.');
