const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map(),events={};
const get=id=>{if(!nodes.has(id))nodes.set(id,{dataset:{},value:'',textContent:'',events:{},addEventListener(k,fn){this.events[k]=fn},showModal(){this.open=true},close(){this.open=false;this.events.close?.()}});return nodes.get(id)};
const release=JSON.parse(fs.readFileSync('website/dist/release.json','utf8'));
get('#verify-download').dataset={exeHash:release.sha256,filename:release.filename};
let copied='';const context={document:{querySelector:get,addEventListener:(key,fn)=>events[key]=fn},navigator:{clipboard:{writeText:async text=>copied=text}}};
vm.runInNewContext(fs.readFileSync('website/src/checksum.js','utf8'),context);
(async()=>{
 get('#open-checksum').events.click({preventDefault(){}});assert.equal(get('#verify-download').open,true);
 let command=get('#checksum-command').textContent;
 assert.ok(command.includes(release.sha256));assert.ok(command.includes(release.filename));assert.ok(command.includes('DOES NOT MATCH'));
 // Older-version commands must not retain the latest file name or hash.
 get('#verify-download').dataset={exeHash:'a'.repeat(64),filename:'Pulse-0.9.0-Windows-x64.exe'};
 events['pulse-release-change']();command=get('#checksum-command').textContent;
 assert.ok(command.includes('a'.repeat(64)));assert.ok(command.includes('Pulse-0.9.0-Windows-x64.exe'));assert.ok(!command.includes(release.sha256));
 await get('#copy-checksum-command').events.click();assert.equal(copied,command);
 context.navigator.clipboard=null;await get('#copy-checksum-command').events.click();assert.ok(get('#checksum-status').textContent.includes('Clipboard access is unavailable'));
 get('#checksum-close').events.click();assert.equal(get('#verify-download').open,false);
 console.log('Version-specific EXE verification, hash changes, copy fallback and modal checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
