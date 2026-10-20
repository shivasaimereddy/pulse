const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const nodes=new Map();
function node(){return {hidden:false,open:true,innerHTML:'',textContent:'',getBoundingClientRect(){return {width:800,height:360}},contains(){return false},addEventListener(){}}}
const $=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)};
const context=vm.createContext({$,resultMode:'folders',folderLoading:false,bytes:n=>n+' B',set:(id,v)=>$(id).textContent=v,escapeHtml:v=>String(v).replaceAll('<','&lt;').replaceAll('"','&quot;'),document:{addEventListener(){},activeElement:null},window:{addEventListener(){}},sessionStorage:{getItem(){return null}},setTimeout(){},clearTimeout(){},Math,Number});
vm.runInContext(fs.readFileSync('static/storage-map.js','utf8'),context);
function run(rows){context.rows=rows;return vm.runInContext('storageMapItems(rows)',context)}
function layout(items,width=800,height=360){context.items=items;return vm.runInContext(`layoutStorageMap(items,${width},${height})`,context)}
for(const sizes of [[86,54,41,31,23,12,9],[100],[999999,1,1,1],Array.from({length:80},(_,i)=>i+1)]){
 const model=run(sizes.map((size,i)=>({name:'Item '+i,size}))),tiles=layout(model.items),sum=sizes.reduce((a,b)=>a+b,0);
 assert.equal(model.total,sum);assert.equal(model.items.reduce((a,b)=>a+b.size,0),sum,'Aggregation must preserve bytes');
 assert.ok(Math.abs(tiles.reduce((a,t)=>a+t.width*t.height,0)-800*360)<.001);
 for(const tile of tiles){assert.ok(tile.x>=0&&tile.y>=0&&tile.x+tile.width<=800.001&&tile.y+tile.height<=360.001);assert.ok(Math.abs(tile.width*tile.height/(800*360)-tile.item.size/sum)<.000001);}
 for(let a=0;a<tiles.length;a++)for(let b=a+1;b<tiles.length;b++){const x=tiles[a],y=tiles[b];assert.ok(Math.min(x.x+x.width,y.x+y.width)-Math.max(x.x,y.x)<.0001||Math.min(x.y+x.height,y.y+y.height)-Math.max(x.y,y.y)<.0001,'Tiles must not overlap');}
}
assert.equal(run([{size:0},{size:-1},{size:NaN}]).items.length,0);
const original=[{name:'small',size:1},{name:'large',size:90}];run(original);assert.equal(original[0].name,'small','Do not mutate list order');
context.rows=[{name:'<folder>',path:'C:/<folder>',kind:'folder',size:100}];context.scan={updated:1,errors:1,nextOffset:100};
vm.runInContext('renderStorageMap(rows,scan)',context);
assert.match($('#storage-map').innerHTML,/&lt;folder>/);assert.match($('#storage-map').innerHTML,/data-scan-path/);assert.match($('#storage-map').innerHTML,/100.0%/);
assert.match($('#storage-map-caption').textContent,/limited coverage/);assert.match($('#storage-map-caption').textContent,/More saved results/);
context.resultMode='files';vm.runInContext('renderStorageMap(rows,scan)',context);assert.equal($('#storage-map-section').hidden,true,'Do not combine folder map with overlapping largest-file results');
console.log('Storage map checks passed: area accuracy, grouping, non-overlap, bounds, safe labels, coverage and view switching.');
