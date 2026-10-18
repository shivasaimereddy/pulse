"""Build a self-contained product website with verified release downloads."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile
from urllib.parse import urljoin, urlsplit
from html import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from pulse import __version__
from generate_product_previews import main as generate_previews


def main():
    website = ROOT / 'website'
    source, output = website / 'src', website / 'dist'
    executable = ROOT / 'dist' / 'Pulse.exe'
    archive = ROOT / 'dist' / ('Pulse-'+__version__+'-Windows-x64.zip')
    if not executable.is_file() or not archive.is_file():
        raise SystemExit('Build the matching desktop release first using scripts/Build Release.cmd.')
    config = json.loads((website / 'site.config.json').read_text(encoding='utf-8'))
    site_url=config['siteUrl'].rstrip('/')+'/'
    parsed=urlsplit(site_url)
    if parsed.scheme!='https' or not parsed.netloc or parsed.query or parsed.fragment:
        raise SystemExit('Set siteUrl to the public HTTPS page URL without query parameters or fragments.')
    # The static hosting bundle includes downloads; no dependency on GitHub Releases.
    if config['downloadUrl'] != 'downloads/Pulse.exe' or config['archiveUrl'] != 'downloads/Pulse-Windows-x64.zip':
        raise SystemExit('This builder expects local downloads/Pulse.exe and downloads/Pulse-Windows-x64.zip paths.')
    generate_previews()
    output.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,output,dirs_exist_ok=True)
    social_file=output/'assets/social.png'
    social_digest=hashlib.sha256(social_file.read_bytes()).hexdigest()[:12]
    social_name='pulse-share-'+social_digest+'.png'
    shutil.copy2(social_file,output/'assets'/social_name)
    for old_image in (output/'assets').glob('pulse-share-*.png'):
        if old_image.name!=social_name:old_image.unlink()
    downloads=output/'downloads'
    downloads.mkdir(exist_ok=True)
    shutil.copy2(executable,downloads/'Pulse.exe')
    shutil.copy2(archive,downloads/'Pulse-Windows-x64.zip')
    digest=hashlib.sha256(executable.read_bytes()).hexdigest()
    # Reject mismatched stale executable/archive pairs.
    with zipfile.ZipFile(archive) as release:
        if hashlib.sha256(release.read('Pulse.exe')).hexdigest()!=digest:
            raise SystemExit('Executable and versioned archive do not match. Rebuild the desktop release.')
    (downloads/'SHA256SUMS.txt').write_text(digest+'  Pulse.exe\n'+hashlib.sha256(archive.read_bytes()).hexdigest()+'  Pulse-Windows-x64.zip\n',encoding='utf-8')
    notices=[]
    for notice in sorted((ROOT/'dist/licenses').glob('*')):
        if notice.is_file():
            notices.append('\n'+'='*70+'\n'+notice.name+'\n'+'='*70+'\n'+notice.read_text(encoding='utf-8',errors='replace'))
    (downloads/'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices),encoding='utf-8')
    replacements={
        'VERSION':__version__, 'SIZE':f'{executable.stat().st_size/1024/1024:.1f} MB', 'SHA256':digest,
        'DOWNLOAD_URL':config['downloadUrl'], 'ARCHIVE_URL':config['archiveUrl'],
        'ARCHIVE_SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'SITE_URL':site_url, 'SOCIAL_IMAGE_URL':urljoin(site_url,'assets/'+social_name)}
    html=(output/'index.html').read_text(encoding='utf-8')
    structured={
        '@context':'https://schema.org','@graph':[
            {'@type':'WebSite','name':'Pulse','url':site_url},
            {'@type':'SoftwareApplication','name':'Pulse','url':site_url,
             'description':'A Windows laptop dashboard for live performance monitoring, storage exploration, and local performance history.',
             'applicationCategory':'UtilitiesApplication','operatingSystem':'Windows x64',
             'softwareVersion':__version__,'downloadUrl':urljoin(site_url,config['downloadUrl']),
             'image':urljoin(site_url,'assets/'+social_name)}]}
    html=html.replace('{{STRUCTURED_DATA}}',json.dumps(structured,ensure_ascii=True).replace('<','\\u003c'))
    for key,value in replacements.items():html=html.replace('{{'+key+'}}',escape(value,quote=True))
    if '{{' in html:raise SystemExit('An unresolved website template value remains.')
    (output/'index.html').write_text(html,encoding='utf-8')
    (output/'release.json').write_text(json.dumps(dict(version=__version__,bytes=executable.stat().st_size,sha256=digest,download=config['downloadUrl']),indent=2),encoding='utf-8')
    (output/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+urljoin(site_url,'sitemap.xml')+'\n',encoding='utf-8')
    (output/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+escape(site_url)+'</loc></url></urlset>\n',encoding='utf-8')
    bundle=ROOT/'dist/Pulse-website.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as package:
        for file in sorted(output.rglob('*')):
            if file.is_file():package.write(file,file.relative_to(output))
    print('Website ready:',output)
    print('Upload archive:',bundle)


if __name__=='__main__':
    main()
