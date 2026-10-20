"""Immutable, versioned desktop artifacts for the static website build."""
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

VERSION = re.compile(r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(root, version, artifact_root=None):
    if not VERSION.fullmatch(version):
        raise ValueError('Use a stable major.minor.patch version for the public release.')
    artifacts = Path(artifact_root) if artifact_root else root / 'release-artifacts'
    executable = root / 'dist/Pulse.exe'
    receipt_path = root / 'dist/release-build.json'
    if not receipt_path.is_file():
        raise ValueError('Build the desktop release first: its version receipt is missing.')
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    digest = checksum(executable)
    if receipt.get('version') != version or receipt.get('sha256') != digest:
        raise ValueError('Desktop executable does not match the current version receipt. Rebuild the desktop release.')
    current = artifacts / version
    binary = current / 'Pulse.exe'
    if current.exists():
        if not binary.is_file() or checksum(binary) != digest:
            raise ValueError('Release '+version+' is already archived with different contents. Bump the app version; published versions must not be overwritten.')
    else:
        artifacts.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.release-', dir=artifacts) as staging:
            ready=Path(staging)/version
            ready.mkdir()
            shutil.copy2(executable, ready/'Pulse.exe')
            shutil.copytree(root/'dist/licenses', ready/'licenses')
            if checksum(ready/'Pulse.exe')!=digest:
                raise ValueError('Executable changed while archiving. Try the build again.')
            (ready/'release.json').write_text(json.dumps(dict(version=version, sha256=digest, bytes=executable.stat().st_size), indent=2), encoding='utf-8')
            ready.rename(current)
    configured = json.loads((root/'website/releases.json').read_text(encoding='utf-8'))
    releases=[]
    seen=set()
    for entry in configured['releases']:
        number=entry['version']
        if not VERSION.fullmatch(number) or number in seen:
            raise ValueError('Release versions must be unique stable major.minor.patch numbers.')
        seen.add(number)
        folder=artifacts/number
        metadata=json.loads((folder/'release.json').read_text(encoding='utf-8'))
        exe=folder/'Pulse.exe'
        if metadata.get('version')!=number or metadata.get('sha256')!=checksum(exe) or metadata.get('bytes')!=exe.stat().st_size or not exe.read_bytes().startswith(b'MZ'):
            raise ValueError('Archived release failed integrity checks: '+number)
        filename='Pulse-'+number+'-Windows-x64.exe'
        releases.append(dict(version=number, bytes=metadata['bytes'], sha256=metadata['sha256'],
            download='downloads/'+number+'/'+filename, filename=filename,
            notes=entry.get('notes',[]), platform='Windows x64'))
    releases.sort(key=lambda r:tuple(map(int,r['version'].split('.'))),reverse=True)
    if not releases or releases[0]['version']!=version:
        raise ValueError('List the current app version as the newest release in website/releases.json.')
    return artifacts,releases
