// Binary treemap: tile area is proportional to displayed logical bytes.
function storageMapItems(rows){
 const positive=rows.filter(item=>Number.isFinite(item.size)&&item.size>0).slice().sort((a,b)=>b.size-a.size);
 const total=positive.reduce((sum,item)=>sum+item.size,0),visible=[],other=[];
 positive.forEach((item,index)=>{(index<18&&item.size/total>=.008?visible:other).push(item);});
 if(other.length)visible.push({name:'Other displayed items',size:other.reduce((sum,item)=>sum+item.size,0),aggregate:other.length});
 return {items:visible,total,count:positive.length};
}
function layoutStorageMap(items,width,height,x=0,y=0){
 if(!items.length||width<=0||height<=0)return [];
 if(items.length===1)return [{item:items[0],x,y,width,height}];
 const total=items.reduce((sum,item)=>sum+item.size,0);
 let index=1,sum=items[0].size;
 while(index<items.length-1&&Math.abs(sum+items[index].size-total/2)<Math.abs(sum-total/2)){sum+=items[index].size;index++;}
 const ratio=sum/total,first=items.slice(0,index),second=items.slice(index);
 return width>=height?[...layoutStorageMap(first,width*ratio,height,x,y),...layoutStorageMap(second,width*(1-ratio),height,x+width*ratio,y)]:[...layoutStorageMap(first,width,height*ratio,x,y),...layoutStorageMap(second,width,height*(1-ratio),x,y+height*ratio)];
}
let storageMapRows=[],storageMapScan=null,storageMapRenderKey=null;
function renderStorageMap(rows,scan){
 storageMapRows=rows;storageMapScan=scan;
 const section=$('#storage-map-section');section.hidden=resultMode!=='folders'||!scan.updated||scan.running||folderLoading;
 if(section.hidden)return;
 const model=storageMapItems(rows),map=$('#storage-map');
 set('#storage-map-total',bytes(model.total)+' in displayed contents');
 set('#storage-map-caption',`${model.count} non-empty items · Areas show logical size, not reclaimable space.${scan.errors||scan.cancelled||scan.failure||scan.treeLimited?' This scan has limited coverage.':''}${scan.nextOffset!=null?' More saved results are available below; load them to extend this map.':''}`);
 const width=map.getBoundingClientRect().width;
 if(!width||!section.open)return;
 if(!model.items.length){map.innerHTML='<div class="map-empty">No non-empty items in this view. Try resetting your filters.</div>';return;}
 const height=map.getBoundingClientRect().height||340;
 const hues=[218,175,263,34,329,198,151,285];
 const tiles=layoutStorageMap(model.items,width,height).map(({item,x,y,width:w,height:h},index)=>{
  const percent=item.size/model.total*100,compact=w<125||h<80,tiny=w<65||h<40;
  const action=item.aggregate?'data-map-other':item.kind==='folder'?'data-scan-path':item.kind==='file'?'data-folder':null;
  const help=`${item.name} · ${bytes(item.size)} · ${percent.toFixed(1)}% of displayed contents. ${item.aggregate?item.aggregate+' smaller items combined. Review them in the list below.':item.kind==='folder'?'Open this folder’s saved results.':item.kind==='file'?'Open its containing folder in Explorer.':'Older snapshot: rescan to enable browsing.'}${item.path?' '+item.path:''}`;
  return `<button type="button" class="map-tile${compact?' compact':''}${h<64?' short':''}${tiny?' tiny':''}" style="left:${x/width*100}%;top:${y/height*100}%;width:${w/width*100}%;height:${h/height*100}%;--map-hue:${item.aggregate?220:hues[index%hues.length]}" ${action?`${action}="${escapeHtml(item.path||'')}"`:''} data-help="${escapeHtml(help)}" aria-label="${escapeHtml(help)}"><span class="map-tile-surface"><span class="map-tile-heading"><span>${escapeHtml(item.name)}</span>${!compact?`<i aria-hidden="true">${item.aggregate?'⋯':item.kind==='folder'?'↗':'·'}</i>`:''}</span><span class="map-tile-size">${bytes(item.size)}${!compact?`<small>${percent.toFixed(1)}% of view</small>`:''}</span></span></button>`;
 }).join('');
 const key=JSON.stringify([scan.path,scan.updated,width,height]);
 if(map.innerHTML!==tiles&&(!map.contains(document.activeElement)||key!==storageMapRenderKey))map.innerHTML=tiles;
 storageMapRenderKey=key;
}
const storageMapSection=$('#storage-map-section');
try{storageMapSection.open=sessionStorage.getItem('pulse.storageMapOpen')!=='false';}catch{}
storageMapSection.addEventListener('toggle',()=>{try{sessionStorage.setItem('pulse.storageMapOpen',String(storageMapSection.open));}catch{}if(storageMapScan)renderStorageMap(storageMapRows,storageMapScan);});
let mapResizeTimer;
function resizeStorageMap(){clearTimeout(mapResizeTimer);mapResizeTimer=setTimeout(()=>{if(storageMapScan)renderStorageMap(storageMapRows,storageMapScan);},80);}
if(typeof ResizeObserver!=='undefined')new ResizeObserver(resizeStorageMap).observe($('#storage-map'));
else window.addEventListener('resize',resizeStorageMap);
document.addEventListener('click',event=>{if(event.target.closest('[data-map-other]'))$('#storage-list').scrollIntoView({block:'start',behavior:'instant'});});
