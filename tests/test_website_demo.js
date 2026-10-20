/* Mathematical contracts for the product demo's size-proportional storage map. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
let source=fs.readFileSync('website/src/demo.js','utf8');
source=source.replace(' const instances=[];',' globalThis.demoMath={rectangles,series,line}; const instances=[];');
const context={document:{querySelectorAll:()=>[]},window:{matchMedia:()=>({matches:false}),setInterval:()=>{}}};
vm.createContext(context);vm.runInContext(source,context);
const {rectangles,series,line}=context.demoMath;
for(const sizes of [[86,54,31,23,12],[42,26,14,4],[99,1],[1],[1,1,1,1,1,1,1]]){
 const boxes=rectangles(sizes.map((size,i)=>['Folder '+i,size]));
 const total=sizes.reduce((a,b)=>a+b,0);
 assert.equal(boxes.length,sizes.length);
 boxes.forEach((box,i)=>{
  assert.ok(box.x>=0&&box.y>=0&&box.x+box.width<=100.000001&&box.y+box.height<=100.000001,'tile stays inside map');
  assert.ok(Math.abs(box.width*box.height/10000-sizes[i]/total)<1e-8,'tile area matches folder share');
  boxes.slice(i+1).forEach(other=>{const overlapX=Math.min(box.x+box.width,other.x+other.width)-Math.max(box.x,other.x);const overlapY=Math.min(box.y+box.height,other.y+other.height)-Math.max(box.y,other.y);assert.ok(overlapX<1e-8||overlapY<1e-8,'tiles do not overlap')});
 });
}
for(const historical of [false,true]){
 const points=series(historical);assert.equal(points.length,48);
 points.forEach(point=>assert.ok(point.cpu>=0&&point.cpu<=100&&point.memory>=0&&point.memory<=100));
 assert.ok(!line(points,'cpu').includes('NaN'));
}
console.log('Sample storage tiles preserve sizes, bounds and non-overlap; graph data stays valid.');
