// Commands run only when the visitor pastes them into Windows PowerShell.
(()=>{
  'use strict';
  const dialog=document.querySelector('#verify-download');
  const expected=document.querySelector('#expected-checksum');
  const command=document.querySelector('#checksum-command');
  const status=document.querySelector('#checksum-status');
  function update(){
    const file={name:dialog.dataset.filename,hash:dialog.dataset.exeHash};
    expected.textContent=file.hash;
    command.textContent=[
      "$expected = '"+file.hash+"'",
      'try {',
      "  $actual = (Get-FileHash -LiteralPath '.\\"+file.name+"' -Algorithm SHA256 -ErrorAction Stop).Hash",
      "  if ($actual -eq $expected) { 'MATCH - file verified.' }",
      "  else { 'DOES NOT MATCH - download a fresh copy.' }",
      "} catch { 'Cannot read the file. Check its name and folder.' }"
    ].join('\n');
    status.textContent='';
  }
  async function copy(text,message){
    try{await navigator.clipboard.writeText(text);status.textContent=message}
    catch{status.textContent='Clipboard access is unavailable. Select and copy the command above.'}
  }
  document.querySelector('#open-checksum').addEventListener('click',event=>{event.preventDefault();update();dialog.showModal()});
  document.querySelector('#checksum-close').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{status.textContent=''});
  document.addEventListener('pulse-release-change',update);
  document.querySelector('#copy-checksum-command').addEventListener('click',()=>copy(command.textContent,'Command copied. Paste it into Windows PowerShell.'));
  document.querySelector('#copy-checksum').addEventListener('click',()=>copy(expected.textContent,'Expected checksum copied.'));
  update();
})();
