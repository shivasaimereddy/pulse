const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const header={value:'',events:{},addEventListener(k,v){this.events[k]=v}},settings={value:'',events:{},addEventListener(k,v){this.events[k]=v}},saved=new Map(),system={matches:true,addEventListener(k,v){this.change=v}},root={dataset:{},style:{}};
const context=vm.createContext({document:{documentElement:root,readyState:'complete',querySelector:s=>s==='#theme-select'?header:settings,querySelectorAll:()=>[header,settings]},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},window:{matchMedia:()=>system,addEventListener(){}}});
vm.runInContext(fs.readFileSync('static/theme.js','utf8'),context);
assert.equal(root.dataset.theme,'dark');settings.value='light';settings.events.change();assert.equal(header.value,'light');assert.equal(root.dataset.theme,'light');assert.equal(saved.get('pulse.appearance'),'light');
header.value='dark';header.events.change();assert.equal(settings.value,'dark');assert.equal(root.dataset.theme,'dark');
settings.value='system';settings.events.change();system.matches=false;system.change();assert.equal(root.dataset.theme,'light');assert.equal(header.value,'system');
console.log('Shared appearance controls stay synchronized with each other and the system theme.');
