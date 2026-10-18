/* No external libraries, trackers, cookies, or network services. */
(()=>{
  'use strict';
  const previews={
    overview:{label:'LIVE OVERVIEW',title:'One glance.\nThe whole picture.',description:'Processor, memory, disk space, battery, and network activity. The essentials, together in one calm view.',detail:'Live readings update every two seconds.',alt:'Pulse overview screen with illustrative performance readings.'},
    apps:{label:'APPS & PROCESSES',title:'Meet the apps\nbehind the activity.',description:'See which apps use the most resources. Inspect process details, identify scripts, and review before taking action.',detail:'Guarded actions keep protected processes off-limits.',alt:'Pulse apps and processes screen with illustrative grouped app activity.'},
    storage:{label:'STORAGE EXPLORER',title:'Find the space\nbehind the numbers.',description:'Explore folder sizes, find large files, and return to saved scans. Browse deeper without rescanning every folder.',detail:'Includes Windows disks and WSL storage views.',alt:'Pulse storage screen with illustrative folder sizes and largest files.'},
    history:{label:'PERFORMANCE HISTORY',title:'Today’s activity.\nTomorrow’s perspective.',description:'Review saved resource trends and busy periods. Understand recurring activity instead of guessing from a single reading.',detail:'Minute detail for 7 days. Hourly trends for 1 year.',alt:'Pulse performance history screen with illustrative CPU and memory trend charts.'}
  };
  const tabs=[...document.querySelectorAll('[data-preview]')];
  const panel=document.querySelector('#product-panel');
  const image=document.querySelector('#product-preview');
  function selectTab(tab,focus=false){
    const key=tab.dataset.preview, item=previews[key];
    tabs.forEach(button=>{const selected=button===tab;button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1});
    document.querySelector('#preview-label').textContent=item.label;
    // Initial markup contains a <br>; subsequent titles are plain text with CSS line breaks.
    document.querySelector('#preview-title').textContent=item.title;
    document.querySelector('#preview-description').textContent=item.description;
    document.querySelector('#preview-detail').textContent=item.detail;
    const index=tabs.indexOf(tab);
    document.querySelector('#preview-number').textContent=String(index+1).padStart(2,'0');
    document.querySelector('.counter-track i').style.width=((index+1)*25)+'%';
    panel.setAttribute('aria-labelledby',tab.id);
    image.src='assets/'+(key==='overview'?'overview-dark':key)+'.svg';image.alt=item.alt;
    if(focus)tab.focus();
  }
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',()=>selectTab(tab));
    tab.addEventListener('keydown',event=>{
      let next;
      if(event.key==='ArrowRight')next=(index+1)%tabs.length;
      else if(event.key==='ArrowLeft')next=(index-1+tabs.length)%tabs.length;
      else if(event.key==='Home')next=0;
      else if(event.key==='End')next=tabs.length-1;
      else return;
      event.preventDefault();selectTab(tabs[next],true);
    });
  });
  // Preload compact vector previews after the first screen is ready.
  window.addEventListener('load',()=>Object.keys(previews).forEach(key=>{const preload=new Image();preload.src='assets/'+(key==='overview'?'overview-dark':key)+'.svg'}),{once:true});
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  if(!motion.matches&&'IntersectionObserver' in window){
    const sections=document.querySelectorAll('.intro-heading,.feature-card,.privacy-copy,.steps article,.download-copy,.faq-heading');
    sections.forEach(element=>element.classList.add('reveal'));
    const observer=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');observer.unobserve(entry.target)}}),{threshold:0.1});
    document.documentElement.classList.add('motion-ready');
    sections.forEach(element=>observer.observe(element));
  }
  const progress=document.querySelector('.scroll-progress');
  let ticking=false;
  function updateScroll(){const distance=document.documentElement.scrollHeight-window.innerHeight;progress.style.width=(distance>0?Math.min(100,Math.max(0,window.scrollY/distance*100)):0)+'%';ticking=false}
  window.addEventListener('scroll',()=>{if(!ticking){window.requestAnimationFrame(updateScroll);ticking=true}},{passive:true});
  window.addEventListener('resize',updateScroll);updateScroll();
  const toast=document.querySelector('#download-toast');
  let toastTimer;
  document.querySelectorAll('[data-download]').forEach(link=>link.addEventListener('click',()=>{
    toast.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.hidden=true,9000);
  }));
  toast.querySelector('button').addEventListener('click',()=>{toast.hidden=true;clearTimeout(toastTimer)});
  document.addEventListener('keydown',event=>{if(event.key==='Escape')toast.hidden=true});
  if(!/Windows/i.test(navigator.userAgent)){
    const hint=document.querySelector('#platform-hint');hint.hidden=false;hint.textContent='On another device? You can download now and transfer Pulse to your Windows x64 laptop.';
  }
})();
