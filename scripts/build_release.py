"""Build from the project root using the isolated packaging environment."""
import hashlib
import json
import shutil
import zipfile
import importlib.metadata
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pulse import __version__


def main():
    import PyInstaller.__main__
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
    work = ROOT / 'build'
    work.mkdir(exist_ok=True)
    version = tuple(map(int, __version__.split('.'))) + (0,)
    resource = VSVersionInfo(ffi=FixedFileInfo(filevers=version, prodvers=version, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('FileDescription','Pulse laptop dashboard'), StringStruct('FileVersion',__version__), StringStruct('ProductName','Pulse'), StringStruct('ProductVersion',__version__), StringStruct('OriginalFilename','Pulse.exe')])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])
    resource_path = work / 'version.txt'
    resource_path.write_text(str(resource), encoding='utf-8')
    licenses = work / 'licenses'
    licenses.mkdir(exist_ok=True)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license, licenses / 'Python.txt')
    for package in ('psutil', 'pyinstaller'):
        distribution = importlib.metadata.distribution(package)
        for file in distribution.files or []:
            if 'license' in str(file).lower() or 'copying' in str(file).lower():
                source = distribution.locate_file(file)
                if source.is_file():
                    shutil.copy2(source, licenses / (package + '-' + source.name))
    for name in ('tcl8.6', 'tk8.6'):
        source = Path(sys.base_prefix) / 'tcl' / name / 'license.terms'
        if source.is_file():
            shutil.copy2(source, licenses / (name + '.txt'))
    (licenses / 'NOTICE.txt').write_text('Pulse bundles Python, SQLite (public domain), Tcl/Tk, psutil, and the PyInstaller bootloader. Respective notices are included here.\n', encoding='utf-8')
    PyInstaller.__main__.run([
        '--noconfirm', '--clean', '--onefile', '--windowed', '--noupx',
        '--name', 'Pulse', '--paths', str(ROOT),
        '--distpath', str(ROOT / 'dist'), '--workpath', str(work / 'pyinstaller'), '--specpath', str(work),
        '--version-file', str(resource_path), '--icon', str(ROOT / 'packaging/pulse.ico'),
        '--add-data', str(ROOT / 'static') + ';static',
        '--add-data', str(licenses) + ';licenses',
        '--add-data', str(ROOT / 'packaging/pulse.ico') + ';packaging',
        str(ROOT / 'packaging/desktop_entry.py')])
    exe = ROOT / 'dist/Pulse.exe'
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (ROOT / 'dist/release-build.json').write_text(json.dumps(dict(version=__version__, sha256=digest, bytes=exe.stat().st_size), indent=2), encoding='utf-8')
    (ROOT / 'dist/SHA256SUMS.txt').write_text(digest + '  Pulse.exe\n', encoding='utf-8')
    (ROOT / 'dist/START HERE.txt').write_text('Pulse ' + __version__ + '\n\nDouble-click Pulse.exe. No Python installation is needed.\nThe dashboard opens in your default browser. Keep the Pulse control window open while monitoring. Click Quit Pulse to stop.\n\nYour readings and scans are saved in %LOCALAPPDATA%\\Pulse. This download contains no existing user history.\nNo administrator privileges are required. Some system processes and folders may be inaccessible.\n\nThis release is unsigned; Windows may show an unknown publisher prompt. Only run copies obtained from a trusted source.\n', encoding='utf-8')
    shutil.copytree(licenses, ROOT / 'dist/licenses', dirs_exist_ok=True)
    architecture = 'x64' if sys.maxsize > 2**32 else 'x86'
    archive = ROOT / 'dist' / ('Pulse-' + __version__ + '-Windows-' + architecture + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for source in [exe, ROOT / 'dist/START HERE.txt', ROOT / 'dist/SHA256SUMS.txt', *(ROOT / 'dist/licenses').iterdir()]:
            bundle.write(source, source.relative_to(ROOT / 'dist'))
    print('Release ready:', archive)


if __name__ == '__main__':
    main()
