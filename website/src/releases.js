// Embedded release metadata also works when the page is opened as a local file.
(()=>{
 'use strict';
 const catalog=JSON.parse(document.querySelector('#release-catalog').textContent);
 const picker=document.querySelector('#download-version');
 const link=document.querySelector('#version-download');
 const dialog=document.querySelector('#verify-download');
 function update(){
  const release=catalog.releases.find(item=>item.version===picker.value)||catalog.releases[0];
  link.href=release.download;link.download=release.filename;
  document.querySelector('#selected-release-details').textContent=`Version ${release.version} · ${release.version===catalog.latest?'Latest':'Previous release'} · ${release.platform} · ${(release.bytes/1024/1024).toFixed(1)} MB`;
  dialog.dataset.exeHash=release.sha256;dialog.dataset.filename=release.filename;
  document.querySelector('#checksum-release-label').textContent=`Pulse ${release.version} · SHA-256`;
  document.querySelector('#checksum-filename').textContent=release.filename;
  document.querySelector('#checksum-file-link').href=release.download.slice(0,release.download.lastIndexOf('/')+1)+'SHA256SUMS.txt';
  document.dispatchEvent(new Event('pulse-release-change'));
 }
 picker.addEventListener('change',update);update();
 document.querySelectorAll('a[href="#available-releases"]').forEach(link=>link.addEventListener('click',()=>document.querySelector('#available-releases details').open=true));
})();
