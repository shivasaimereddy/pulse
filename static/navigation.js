// Restore the saved screen, data, and scroll position as one startup operation.
let restoringDashboard=true;
function rememberDashboardScroll(){
 if(restoringDashboard)return;
 try{const positions=JSON.parse(sessionStorage.getItem('pulse.scrollPositions')||'{}');positions[view]=window.scrollY||0;sessionStorage.setItem('pulse.scrollPositions',JSON.stringify(positions));}catch{}
}
window.addEventListener('scroll',rememberDashboardScroll,{passive:true});
window.addEventListener('pagehide',()=>{rememberDashboardScroll();if(typeof saveStorageView==='function')saveStorageView();});
async function restoreDashboardView(){
 restoringDashboard=true;
 let saved='overview',scroll=0;
 try{saved=sessionStorage.getItem('pulse.activeView')||localStorage.getItem('pulse.startView')||'overview';const positions=JSON.parse(sessionStorage.getItem('pulse.scrollPositions')||'{}');scroll=Number.isFinite(positions[saved])?Math.max(0,positions[saved]):0;}catch{}
 try{
  await Promise.all([initialMetricsReady,changeView(dashboardViews.includes(saved)?saved:'overview',{restore:true})]);
  // A frame lets the restored list contribute its height before scrolling.
  await new Promise(resolve=>window.requestAnimationFrame(resolve));
  window.scrollTo({top:scroll,behavior:'instant'});
 }finally{
  clearTimeout(window.pulseBootTimer);
  document.documentElement.classList.remove('booting');
  document.body.setAttribute('aria-busy','false');
  const loader=document.querySelector('#app-loader');if(loader)loader.setAttribute('aria-hidden','true');
  restoringDashboard=false;
 }
}
restoreDashboardView();

// Compact-screen navigation: keep content reachable without a horizontal menu strip.
function closeAppNavigation(){
 if(!document.body.classList.contains('nav-open'))return;
 document.body.classList.remove('nav-open');document.querySelector('main').inert=false;
 document.querySelector('#toggle-nav').setAttribute('aria-expanded','false');
 document.querySelector('#toggle-nav').focus();
}
document.querySelector('#toggle-nav').onclick=()=>{
 document.body.classList.add('nav-open');document.querySelector('main').inert=true;
 document.querySelector('#toggle-nav').setAttribute('aria-expanded','true');
 document.querySelector('#close-nav').focus();
};
document.querySelector('#close-nav').onclick=closeAppNavigation;
document.querySelector('#nav-scrim').onclick=closeAppNavigation;
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeAppNavigation();});
document.addEventListener('click',event=>{if(event.target.closest('button.nav[data-view]'))closeAppNavigation();});
window.matchMedia('(min-width: 861px)').addEventListener('change',event=>{if(event.matches)closeAppNavigation();});

// A compact rail gives charts and investigation tables more room on laptops.
function applySidebarCompact(compact){
 document.body.classList.toggle('sidebar-compact',compact);
 const control=document.querySelector('#compact-nav');
 control.setAttribute('aria-expanded',String(!compact));
 control.setAttribute('aria-label',compact?'Expand sidebar':'Collapse sidebar');
 control.setAttribute('data-help',compact?'Expand the sidebar to show menu names.':'Collapse the sidebar for more workspace.');
 document.querySelectorAll('.app-navigation .nav').forEach(button=>{
  if(compact){button.setAttribute('data-help',button.textContent.trim());button.setAttribute('data-help-placement','right');button.setAttribute('data-help-kind','menu');}
  else ['data-help','data-help-placement','data-help-kind'].forEach(name=>button.removeAttribute(name));
 });
}
try{applySidebarCompact(localStorage.getItem('pulse.sidebarCompact')==='true');}catch{}
document.querySelector('#compact-nav').onclick=()=>{
 const compact=!document.body.classList.contains('sidebar-compact');applySidebarCompact(compact);
 try{localStorage.setItem('pulse.sidebarCompact',String(compact));}catch{}
};
