"""Verify an extracted Pulse website before switching the live web root."""
import hashlib
import json
from pathlib import Path
import sys


def verify(directory):
    root=Path(directory).resolve()
    catalog=json.loads((root/'releases.json').read_text(encoding='utf-8'))
    latest=json.loads((root/'release.json').read_text(encoding='utf-8'))
    if latest['version']!=catalog['latest']:
        raise ValueError('Latest release metadata is inconsistent.')
    html=(root/'index.html').read_text(encoding='utf-8')
    if '{{' in html:
        raise ValueError('The page still contains unrendered templates.')
    for release in catalog['releases']:
        binary=(root/release['download']).resolve()
        try:
            binary.relative_to(root)
        except ValueError:
            raise ValueError('A release path escapes the website directory.')
        content=binary.read_bytes()
        digest=hashlib.sha256(content).hexdigest()
        if not content.startswith(b'MZ') or digest!=release['sha256'] or len(content)!=release['bytes']:
            raise ValueError('Executable integrity check failed: '+release['version'])
        sums=(binary.parent/'SHA256SUMS.txt').read_text(encoding='utf-8')
        if release['sha256']+'  '+release['filename'] not in sums:
            raise ValueError('Published checksum file does not match the executable.')
        if release['version']==latest['version'] and (digest!=latest['sha256'] or digest not in html or release['download'] not in html):
            raise ValueError('The page, release manifest and executable disagree.')
    alias=root/'downloads/Pulse.exe'
    if hashlib.sha256(alias.read_bytes()).hexdigest()!=latest['sha256']:
        raise ValueError('The compatibility download does not match the latest release.')
    print('PASS: website, release metadata, EXE and checksums agree.')
    print('App version:',latest['version'])
    print('Download:',latest['download'])
    print('SHA-256:',latest['sha256'])


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Usage: python verify_website_bundle.py PATH_TO_EXTRACTED_WEBSITE')
    try:
        verify(sys.argv[1])
    except (OSError,ValueError,KeyError) as error:
        raise SystemExit('Verification failed: '+str(error))
