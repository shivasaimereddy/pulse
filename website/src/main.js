(()=>{
 'use strict';
 document.querySelectorAll('[data-tour-screen]').forEach(link=>link.addEventListener('click',()=>{
  document.querySelector(`[data-pulse-demo="tour"] nav [data-demo-screen="${link.dataset.tourScreen}"]`)?.click();
 }));
 // Native details supports keyboard use; expose its current state explicitly.
 document.querySelectorAll('.faq-list details').forEach(details=>{const summary=details.querySelector('summary');summary.setAttribute('aria-expanded',String(details.open));details.addEventListener('toggle',()=>summary.setAttribute('aria-expanded',String(details.open)))});
 const toast=document.querySelector('#download-toast');let timer;
 document.querySelectorAll('[data-download]').forEach(link=>link.addEventListener('click',()=>{toast.hidden=false;clearTimeout(timer);timer=setTimeout(()=>toast.hidden=true,8000)}));
 toast.querySelector('button').addEventListener('click',()=>toast.hidden=true);
 const warning=document.querySelector('#warning-faq');
 document.querySelectorAll('a[href="#warning-faq"]').forEach(link=>link.addEventListener('click',()=>warning.open=true));
})();
