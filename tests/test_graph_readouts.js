const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements=new Map();
function element(id=''){return {id,hidden:true,innerHTML:'',style:{},attrs:{},events:{},classList:{add(){}},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]},getBoundingClientRect(){return {left:50,top:150,bottom:290,width:500,height:80}},querySelector(){return null},append(){},contains(){return false},addEventListener(k,v){this.events[k]=v}}}
for(const id of ['chart','cpu-spark','mem-spark','history-plot','insights-chart'])elements.set('#'+id,element(id));
elements.set('#history-metric',{value:'resources'});
let tooltip;
const context=vm.createContext({data:{history:[{time:100,cpu:10,memory:40},{time:102,cpu:30,memory:50}]},savedHistory:{start:0,end:600,resolution:60,points:[{time:0,cpu:10,memory:20},{time:540,cpu:70,memory:80}]},insightsData:null,$:s=>elements.get(s),bytes:n=>n+' B',escapeHtml:String,document:{body:{append(){}},createElement(){const node=element();if(!tooltip)tooltip=node;return node},addEventListener(){}},window:{innerWidth:700,innerHeight:500,addEventListener(){}},Date,Math,Number});
vm.runInContext(fs.readFileSync('static/chart-readouts.js','utf8'),context);
let model=vm.runInContext('graphReadoutModel("history-plot")',context);context.model=model;
assert.equal(vm.runInContext('closestGraphPoint(model,.5)',context),null,'No values across an unrecorded gap');
assert.equal(vm.runInContext('closestGraphPoint(model,.95).point.cpu',context),70);
assert.equal(vm.runInContext('closestGraphPoint(graphReadoutModel("chart"),0)',context),null,'Initial empty live-chart area must not invent a reading');
const chart=elements.get('#chart');chart.events.focus();assert.equal(tooltip.hidden,false);assert.match(tooltip.innerHTML,/30.0%/);assert.match(tooltip.innerHTML,/50.0%/);assert.match(tooltip.innerHTML,/Observed live sample/);
chart.events.keydown({key:'ArrowLeft',preventDefault(){}});assert.match(tooltip.innerHTML,/10.0%/);
chart.events.keydown({key:'Escape'});assert.equal(tooltip.hidden,true);
elements.get('#history-plot').events.pointermove({clientX:300});assert.match(tooltip.innerHTML,/No recorded sample here/);
elements.get('#history-metric').value='network';context.savedHistory.points=[{time:0,download:20,upload:10}];
elements.get('#history-plot').events.focus();assert.match(tooltip.innerHTML,/20 B\/s/);assert.match(tooltip.innerHTML,/minute bucket average/);
console.log('Graph readout checks passed: exact samples, paired values, gaps, empty space, units, keyboard navigation and dismissal.');
