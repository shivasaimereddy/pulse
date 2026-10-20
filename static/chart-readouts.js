// Match the rendered positions; never interpolate across missing observations.
function graphReadoutModel(id){
 const resources=[['cpu','Processor','#79b8ff'],['memory','Memory','#bc9fe8']];
 if(['chart','cpu-spark','mem-spark'].includes(id)){
  const points=data?.history||[],small=id!=='chart';
  return {points,series:id==='cpu-spark'?resources.slice(0,1):id==='mem-spark'?resources.slice(1):resources,kind:'live',
   position:(_,i)=>small?i/Math.max(points.length-1,1):1-(points.length-1-i)/89};
 }
 if(id==='history-plot'){
  if(!savedHistory)return null;
  const h=savedHistory,mode=$('#history-metric').value;
  return {points:h.points,kind:mode,resolution:h.resolution,start:h.start,end:h.end,
   series:mode==='resources'?resources:mode==='network'?[['download','Download','#79b8ff'],['upload','Upload','#bc9fe8']]:mode==='battery'?[['battery','Battery','#63bf91']]:[['diskFree','Free space','#e4a146']],
   position:p=>(p.time+Math.min(h.resolution/2,Math.max(0,h.end-p.time))-h.start)/Math.max(h.end-h.start,1)};
 }
 if(!insightsData)return null;
 const h=insightsData,points=h.points,start=points.length?Math.max(h.start,Math.min(points[0].time,h.end-300)):h.start,span=Math.max(60,h.end-start),resolution=h.resolution||60;
 return {points,series:resources,kind:'insights',resolution,start,end:start+span,
  position:p=>(p.time+Math.min(resolution/2,Math.max(0,h.end-p.time)/2)-start)/span};
}
function closestGraphPoint(model,fraction){
 if(!model?.points.length)return null;
 let best=null;
 model.points.forEach((point,index)=>{const x=model.position(point,index),distance=Math.abs(x-fraction);if(!best||distance<best.distance)best={point,index,x,distance};});
 if(model.kind==='live')return best.distance<=.065?best:null;
 const timestamp=model.start+fraction*(model.end-model.start);
 return timestamp>=best.point.time&&timestamp<=Math.min(model.end,best.point.time+model.resolution)?best:null;
}
let refreshGraphReadout=()=>{};
(() => {
 const tooltip=document.createElement('div');tooltip.id='graph-readout';tooltip.className='graph-readout';tooltip.setAttribute('role','tooltip');tooltip.hidden=true;document.body.append(tooltip);
 let active=null,anchor=null,selected=null;
 function hide(){tooltip.hidden=true;if(active){active.querySelector('.graph-crosshair')?.remove();active.removeAttribute('aria-describedby');}active=null;anchor=null;selected=null;}
 function show(element,fraction,index=null){
  if(active&&active!==element)hide();active=element;anchor=fraction;selected=index;
  const model=graphReadoutModel(element.id),match=index===null?closestGraphPoint(model,fraction):model?.points[index]?{point:model.points[index],index,x:model.position(model.points[index],index)}:null;
  const rect=element.getBoundingClientRect();
  const position=match?Math.max(0,Math.min(1,match.x)):fraction;
  let guide=element.querySelector('.graph-crosshair');if(!guide){guide=document.createElement('div');guide.className='graph-crosshair';guide.setAttribute('aria-hidden','true');element.append(guide);}guide.style.left=position*100+'%';
  if(!match)tooltip.innerHTML='<strong>No recorded sample here</strong><small>Move to a recorded point. Gaps are not estimated.</small>';
  else{
   const p=match.point,time=new Date(p.time*1000).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',...(model.kind==='live'?{second:'2-digit'}:{})});
   const format=value=>!Number.isFinite(value)?'Unavailable':model.kind==='network'?bytes(value)+'/s':['disk'].includes(model.kind)?bytes(value):value.toFixed(1)+'%';
   tooltip.innerHTML=`<strong class="graph-readout-time">${escapeHtml(time)}</strong>${model.series.map(([key,label,color])=>`<div><span><i style="background:${color}"></i>${label}</span><b>${format(p[key])}</b></div>`).join('')}<small>${model.kind==='live'?'Observed live sample':model.resolution>=86400?'Daily bucket average':model.resolution>=3600?'Hourly bucket average':`${Math.round(model.resolution/60)}-minute bucket average`}${Number.isFinite(p.coverage)?' · '+Math.round(p.coverage)+'s sampled':''}</small>`;
  }
  tooltip.hidden=false;element.setAttribute('aria-describedby',tooltip.id);
  const box=tooltip.getBoundingClientRect(),pad=12;
  tooltip.style.left=Math.max(pad,Math.min(rect.left+rect.width*position-box.width/2,window.innerWidth-box.width-pad))+'px';
  tooltip.style.top=Math.max(pad,Math.min(rect.top-box.height-12>=pad?rect.top-box.height-12:rect.bottom+12,window.innerHeight-box.height-pad))+'px';
 }
 for(const id of ['chart','cpu-spark','mem-spark','history-plot','insights-chart']){
  const element=$('#'+id);if(!element)continue;
  element.classList.add('interactive-graph');element.tabIndex=0;element.setAttribute('role','group');element.setAttribute('aria-label',(id==='cpu-spark'?'Processor':id==='mem-spark'?'Memory':id==='history-plot'?'Performance history':id==='insights-chart'?'Recorded activity':'Live processor and memory')+' graph. Hover or tap for readings. Use Left and Right arrow keys to explore samples.');
  const pointer=event=>{const rect=element.getBoundingClientRect();show(element,Math.max(0,Math.min(1,(event.clientX-rect.left)/Math.max(1,rect.width))));};
  element.addEventListener('pointermove',pointer);element.addEventListener('pointerdown',pointer);
  element.addEventListener('pointerleave',event=>{if(!tooltip.contains(event.relatedTarget))hide();});element.addEventListener('blur',hide);
  element.addEventListener('focus',()=>{const model=graphReadoutModel(id);if(model?.points.length)show(element,1,model.points.length-1);});
  element.addEventListener('keydown',event=>{
   if(event.key==='Escape'){hide();return;}
   if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
   const model=graphReadoutModel(id);if(!model?.points.length)return;event.preventDefault();
   const current=selected??closestGraphPoint(model,anchor??1)?.index??model.points.length-1;
   const index=event.key==='Home'?0:event.key==='End'?model.points.length-1:Math.max(0,Math.min(model.points.length-1,current+(event.key==='ArrowLeft'?-1:1)));
   show(element,model.position(model.points[index],index),index);
  });
 }
 refreshGraphReadout=()=>{if(active)show(active,anchor,selected);};
 tooltip.addEventListener('pointerleave',hide);
 window.addEventListener('scroll',hide,true);window.addEventListener('resize',hide);
 document.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});
 document.addEventListener('click',event=>{if(active&&!active.contains(event.target))hide();});
})();
