// Run before paint: the saved screen is revealed only after its initial data settles.
document.documentElement.classList.add('booting');
try{window.history.scrollRestoration='manual';}catch{}
window.pulseBootTimer=setTimeout(()=>{
 document.documentElement.classList.remove('booting');
 const loader=document.querySelector('#app-loader');if(loader)loader.setAttribute('aria-hidden','true');
 if(document.body)document.body.setAttribute('aria-busy','false');
 const notice=document.querySelector('#notice');
 if(notice){notice.hidden=false;notice.textContent='Still reconnecting to Pulse. This screen will update when the local service responds.';}
},8000);
