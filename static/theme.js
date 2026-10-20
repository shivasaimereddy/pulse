(function () {
  const key='pulse.appearance';
  const valid=value=>['system','light','dark'].includes(value)?value:'system';
  const system=window.matchMedia('(prefers-color-scheme: dark)');
  let preference='system';
  try { preference=valid(localStorage.getItem(key)); } catch {}

  function apply() {
    const resolved=preference==='system'?(system.matches?'dark':'light'):preference;
    document.documentElement.dataset.theme=resolved;
    document.documentElement.style.colorScheme=resolved;
    const control=document.querySelector('#theme-select');
    if(control)control.value=preference;
    const settings=document.querySelector('#settings-theme');if(settings)settings.value=preference;
  }
  function bind() {
    document.querySelectorAll('#theme-select,#settings-theme').forEach(control=>{
    control.value=preference;
    control.addEventListener('change',()=>{
      preference=valid(control.value);
      try { localStorage.setItem(key,preference); } catch {}
      apply();
    });
    });
  }
  apply();
  system.addEventListener('change',()=>{if(preference==='system')apply();});
  window.addEventListener('storage',event=>{
    if(event.key===key||event.key===null){preference=valid(event.newValue);apply();}
  });
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);
  else bind();
})();
