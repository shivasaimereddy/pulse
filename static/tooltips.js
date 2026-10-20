// Shared contextual help for mouse, keyboard and touch. Tooltip text is plain text.
(() => {
 const tip=document.createElement('div');
 tip.id='pulse-tooltip';tip.className='pulse-tooltip';tip.setAttribute('role','tooltip');tip.hidden=true;
 document.body.append(tip);
 let active=null,timer=null,dismissTimer=null;
 const clear=()=>{clearTimeout(timer);timer=null;clearTimeout(dismissTimer);dismissTimer=null;};
 function hide(){
  clear();tip.hidden=true;
  if(active){const ids=(active.getAttribute('aria-describedby')||'').split(/\s+/).filter(id=>id&&id!==tip.id);if(ids.length)active.setAttribute('aria-describedby',ids.join(' '));else active.removeAttribute('aria-describedby');}
  active=null;
 }
 function place(){
  if(!active||!active.isConnected||!active.dataset.help?.trim()){hide();return;}
  const rect=active.getBoundingClientRect(),box=tip.getBoundingClientRect(),gap=10,pad=12;
  if(active.getAttribute('data-help-placement')==='right'){
   const right=rect.left+rect.width+gap;
   const fits=right+box.width<=window.innerWidth-pad;
   tip.dataset.placement=fits?'right':'left';
   tip.style.left=Math.max(pad,Math.min(fits?right:rect.left-box.width-gap,window.innerWidth-box.width-pad))+'px';
   tip.style.top=Math.max(pad,Math.min(rect.top+rect.height/2-box.height/2,window.innerHeight-box.height-pad))+'px';
   return;
  }
  tip.dataset.placement='vertical';
  tip.style.left=Math.max(pad,Math.min(rect.left+rect.width/2-box.width/2,window.innerWidth-box.width-pad))+'px';
  const below=rect.bottom+gap;
  tip.style.top=Math.max(pad,Math.min(below+box.height<=window.innerHeight-pad?below:rect.top-box.height-gap,window.innerHeight-box.height-pad))+'px';
 }
 function show(target){
  const text=target.dataset.help?.trim();
  if(!text){hide();return;}
  if(active===target&&!tip.hidden)return;
  hide();active=target;(target.closest('dialog')||document.body).append(tip);tip.textContent=text;tip.dataset.kind=target.getAttribute('data-help-kind')||'help';tip.hidden=false;
  const ids=(target.getAttribute('aria-describedby')||'').split(/\s+/).filter(Boolean);
  target.setAttribute('aria-describedby',[...new Set([...ids,tip.id])].join(' '));place();
 }
 const targetFor=event=>{const target=event.target.closest?.('[data-help]');return target?.dataset.help?.trim()?target:null;};
 document.addEventListener('pointerover',event=>{
  if(event.pointerType==='touch')return;
  const target=targetFor(event);if(!target){if(!tip.contains(event.target))hide();return;}if(target.contains(event.relatedTarget))return;
  if(active===target&&!tip.hidden){clear();return;}
  if(active&&active!==target)hide();
  clear();timer=setTimeout(()=>show(target),350);
 });
 document.addEventListener('pointerout',event=>{
  const target=targetFor(event);
  if(target&&!target.contains(event.relatedTarget)&&!tip.contains(event.relatedTarget)){
   clear();if(active===target)dismissTimer=setTimeout(hide,150);
  }
 });
 document.addEventListener('focusin',event=>{const target=targetFor(event);if(target)show(target);else hide();});
 document.addEventListener('focusout',event=>{if(active&&!active.contains(event.relatedTarget))hide();});
 document.addEventListener('click',event=>{
  const target=targetFor(event);
  if(target?.classList.contains('help-trigger')){event.preventDefault();show(target);}
  else hide();
 });
 document.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});
 tip.addEventListener('pointerenter',clear);
 tip.addEventListener('pointerleave',()=>{clear();dismissTimer=setTimeout(hide,150);});
 window.addEventListener('scroll',hide,true);window.addEventListener('resize',hide);
 document.addEventListener('visibilitychange',hide);
})();
