"""Build the self-contained product website and retained, versioned EXE downloads."""
import hashlib
import argparse
from html import escape
import json
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import urljoin, urlsplit
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from pulse import __version__
from website_releases import prepare


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace-current',action='store_true',help='Explicitly replace the current build while backing up its previous artifact.')
    arguments=parser.parse_args()
    website=ROOT/'website'
    source,output=website/'src',website/'dist'
    config=json.loads((website/'site.config.json').read_text(encoding='utf-8'))
    site_url=config['siteUrl'].rstrip('/')+'/'
    parsed=urlsplit(site_url)
    if parsed.scheme!='https' or not parsed.netloc or parsed.query or parsed.fragment:
        raise SystemExit('Set siteUrl to the public HTTPS page URL without query parameters or fragments.')
    try:
        artifacts,releases=prepare(ROOT,__version__,os.environ.get('PULSE_RELEASE_DIR'),replace_current=arguments.replace_current)
    except (ValueError,OSError,KeyError) as error:
        raise SystemExit(str(error))
    latest=releases[0]
    # Validate the exact generated directory before replacing build output.
    if output.resolve()!=ROOT.resolve()/'website'/'dist' or output.is_symlink():
        raise SystemExit('Refusing to replace an unexpected website output directory.')
    if output.exists():shutil.rmtree(output)
    shutil.copytree(source,output,ignore=shutil.ignore_patterns('theme.css','clarity.css','polish.css','screens','social.svg','overview.svg','overview-dark.svg','apps.svg','history.svg','storage.svg'))
    social_file=output/'assets/social.png'
    social_name='pulse-share-'+hashlib.sha256(social_file.read_bytes()).hexdigest()[:12]+'.png'
    shutil.copy2(social_file,output/'assets'/social_name)
    for release in releases:
        original=artifacts/release['version']
        target=output/release['download']
        target.parent.mkdir(parents=True)
        shutil.copy2(original/'Pulse.exe',target)
        (target.parent/'SHA256SUMS.txt').write_text(release['sha256']+'  '+release['filename']+'\n',encoding='utf-8')
        notices=[]
        for notice in sorted((original/'licenses').glob('*')):
            if notice.is_file():notices.append('\n'+notice.name+'\n'+'='*60+'\n'+notice.read_text(encoding='utf-8',errors='replace'))
        (target.parent/'THIRD-PARTY-NOTICES.txt').write_text('\n'.join(notices),encoding='utf-8')
    downloads=output/'downloads'
    # Compatibility aliases serve the latest EXE; versioned URLs remain immutable.
    shutil.copy2(output/latest['download'],downloads/'Pulse.exe')
    shutil.copy2((output/latest['download']).parent/'THIRD-PARTY-NOTICES.txt',downloads/'THIRD-PARTY-NOTICES.txt')
    (downloads/'SHA256SUMS.txt').write_text(latest['sha256']+'  Pulse.exe\n',encoding='utf-8')
    options=''.join('<option value="'+r['version']+'">Version '+r['version']+(' · Latest' if i==0 else ' · Previous release')+'</option>' for i,r in enumerate(releases))
    release_rows=''.join('<article class="release-entry"><div><h4>Pulse '+r['version']+'</h4><span>'+('Latest release' if i==0 else 'Previous release')+' · Windows x64 · '+f"{r['bytes']/1024/1024:.1f} MB"+'</span></div><ul>'+''.join('<li>'+escape(note)+'</li>' for note in r['notes'])+'</ul><a href="'+r['download']+'" download="'+r['filename']+'">Download EXE ↗</a></article>' for i,r in enumerate(releases))
    catalog=dict(latest=latest['version'],releases=releases)
    replacements=dict(RELEASE_PICKER_STATE='hidden' if len(releases)==1 else '',VERSION=__version__,SIZE=f"{latest['bytes']/1024/1024:.1f} MB",SHA256=latest['sha256'],DOWNLOAD_URL=latest['download'],FILENAME=latest['filename'],SITE_URL=site_url,SOCIAL_IMAGE_URL=urljoin(site_url,'assets/'+social_name))
    html=(output/'index.html').read_text(encoding='utf-8')
    structured={'@context':'https://schema.org','@graph':[
        {'@type':'WebSite','name':'Pulse','url':site_url},
        {'@type':'SoftwareApplication','name':'Pulse','url':site_url,'description':'A local Windows PC dashboard for live performance, storage exploration and recorded history.','applicationCategory':'UtilitiesApplication','operatingSystem':'Windows x64','softwareVersion':__version__,'downloadUrl':urljoin(site_url,latest['download']),'fileSize':str(latest['bytes'])+' bytes','image':urljoin(site_url,'assets/'+social_name)}]}
    html=html.replace('{{STRUCTURED_DATA}}',json.dumps(structured).replace('<','\\u003c'))
    html=html.replace('downloads/{{VERSION}}/SHA256SUMS.txt',str(Path(latest['download']).parent).replace('\\','/')+'/SHA256SUMS.txt').replace('{{RELEASE_OPTIONS}}',options).replace('{{RELEASE_ROWS}}',release_rows).replace('{{RELEASE_CATALOG}}',json.dumps(catalog,ensure_ascii=True).replace('<','\\u003c'))
    for key,value in replacements.items():html=html.replace('{{'+key+'}}',escape(value,quote=True))
    # A fresh HTML release must never run an older cached script or stylesheet.
    for asset in output.iterdir():
        if asset.suffix in ('.js','.css'):
            fingerprint=hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
            html=html.replace('src="'+asset.name+'"','src="'+asset.name+'?v='+fingerprint+'"')
            html=html.replace('href="'+asset.name+'"','href="'+asset.name+'?v='+fingerprint+'"')
    if '{{' in html:raise SystemExit('An unresolved website template value remains.')
    (output/'index.html').write_text(html,encoding='utf-8')
    (output/'release.json').write_text(json.dumps(latest,indent=2),encoding='utf-8')
    (output/'releases.json').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    (output/'robots.txt').write_text('User-agent: *\nAllow: /\nSitemap: '+urljoin(site_url,'sitemap.xml')+'\n',encoding='utf-8')
    (output/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>'+escape(site_url)+'</loc></url></urlset>\n',encoding='utf-8')
    bundle=ROOT/'dist/Pulse-website.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as package:
        for file in sorted(output.rglob('*')):
            if file.is_file():package.write(file,file.relative_to(output))
    (ROOT/'dist/Pulse-website.zip.sha256').write_text(hashlib.sha256(bundle.read_bytes()).hexdigest()+'  Pulse-website.zip\n',encoding='utf-8')
    print('Website ready:',output)
    print('Retained releases:',', '.join(r['version'] for r in releases))
    print('Deployment archive (not a visitor download):',bundle)


if __name__=='__main__':main()
