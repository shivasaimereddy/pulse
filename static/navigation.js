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
 try{saved=sessionStorage.getItem('pulse.activeView')||'overview';const positions=JSON.parse(sessionStorage.getItem('pulse.scrollPositions')||'{}');scroll=Number.isFinite(positions[saved])?Math.max(0,positions[saved]):0;}catch{}
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
