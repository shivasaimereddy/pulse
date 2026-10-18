// Apply the saved preference before styles paint. First visits always start dark.
(()=>{
  'use strict';
  const key='pulse.website.theme';
  const root=document.documentElement;
  function apply(theme){
    const selected=theme==='light'?'light':'dark';
    root.dataset.theme=selected;
    const meta=document.querySelector('meta[name="theme-color"]');
    if(meta)meta.content=selected==='light'?'#f5f7fb':'#080b10';
    const button=document.querySelector('#theme-toggle');
    if(button){
      const label=selected==='dark'?'Switch to light theme':'Switch to dark theme';
      button.setAttribute('aria-label',label);button.title=label;
    }
  }
  let initial='dark';
  try{initial=localStorage.getItem(key)||'dark'}catch{}
  apply(initial);
  document.addEventListener('DOMContentLoaded',()=>{
    apply(root.dataset.theme);
    document.querySelector('#theme-toggle').addEventListener('click',()=>{
      const selected=root.dataset.theme==='dark'?'light':'dark';
      apply(selected);
      try{localStorage.setItem(key,selected)}catch{}
    });
  },{once:true});
  window.addEventListener('storage',event=>{if(event.key===key||event.key===null)apply(event.newValue)});
})();
