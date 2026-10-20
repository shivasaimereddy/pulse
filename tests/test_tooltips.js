const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const listeners={},windowEvents={};let tooltip,timer;
const makeElement=()=>({dataset:{},style:{},hidden:true,isConnected:true,attrs:{},classList:{contains:n=>n==='help-trigger'},setAttribute(k,v){this.attrs[k]=v},getAttribute(k){return this.attrs[k]||null},removeAttribute(k){delete this.attrs[k]},contains(other){return other===this},getBoundingClientRect(){return {left:280,top:170,bottom:190,width:20,height:60}},addEventListener(){},closest(selector){return selector==='dialog'?null:this}});
const document={createElement(){tooltip=makeElement();return tooltip},body:{append(){}},addEventListener(type,fn){listeners[type]=fn}};
vm.runInNewContext(fs.readFileSync('static/tooltips.js','utf8'),{document,window:{innerWidth:360,innerHeight:240,addEventListener(type,fn){windowEvents[type]=fn}},setTimeout:fn=>(timer=fn,1),clearTimeout:()=>timer=null});
const target=makeElement();target.dataset.help='Working-set memory can include shared pages.';target.attrs['aria-describedby']='existing';
listeners.focusin({target});assert.equal(tooltip.hidden,false);assert.equal(tooltip.textContent,target.dataset.help);assert.equal(target.attrs['aria-describedby'],'existing pulse-tooltip');
assert.ok(parseFloat(tooltip.style.left)<=328);assert.ok(parseFloat(tooltip.style.top)<=168,'Tooltip should fit above a low trigger');
listeners.keydown({key:'Escape'});assert.equal(tooltip.hidden,true);assert.equal(target.attrs['aria-describedby'],'existing','Preserve other descriptions');
listeners.pointerover({target,pointerType:'mouse',relatedTarget:null});assert.equal(tooltip.hidden,true);timer();assert.equal(tooltip.hidden,false);
listeners.pointerout({target,relatedTarget:tooltip});assert.equal(tooltip.hidden,false,'Hoverable help must remain open when the pointer enters it');
windowEvents.scroll();assert.equal(tooltip.hidden,true);
listeners.click({target,preventDefault(){}});assert.equal(tooltip.hidden,false,'Help button supports tap/click');
listeners.focusout({relatedTarget:null});assert.equal(tooltip.hidden,true);
listeners.pointerover({target,pointerType:'touch'});assert.equal(tooltip.hidden,true,'Touch uses explicit tap rather than emulated hover');
for(const text of ['', '   ']){
 target.dataset.help=text;
 listeners.pointerover({target,pointerType:'mouse',relatedTarget:null});
 assert.equal(timer,null,'Empty help must not schedule a tooltip');
 listeners.focusin({target});assert.equal(tooltip.hidden,true,'Empty keyboard help stays hidden');
 listeners.click({target,preventDefault(){}});assert.equal(tooltip.hidden,true,'Empty click help stays hidden');
 assert.equal(target.attrs['aria-describedby'],'existing');
}
target.dataset.help='Storage';listeners.pointerover({target,pointerType:'mouse',relatedTarget:null});
target.dataset.help='';timer();assert.equal(tooltip.hidden,true,'Help cleared during the hover delay must not create an empty box');
console.log('Tooltip keyboard, hover, touch, viewport and accessible-description checks passed.');
