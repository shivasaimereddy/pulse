# Windows distribution

## User experience

Share `dist/Pulse-<version>-Windows-x64.zip`, which contains `Pulse.exe`, instructions, a checksum, and third-party notices. Users double-click it; no Python installation, source checkout, terminal, or administrator access is required. Pulse opens its dashboard in the default browser, with a small native controller to reopen the dashboard or quit monitoring. Closing the controller stops the service and flushes history. Closing only the browser does not stop recording.

Only one service can use localhost port 8765. A second launch opens the existing Pulse service. Another application on this port produces a startup error. If the development server is already running, quit it before testing the packaged app.

## Data

Packaged releases use `%LOCALAPPDATA%\Pulse\pulse.sqlite3`, independent of the executable location and its temporary extraction directory. Existing source runs continue using the project `data/` folder. No existing database, scans, logs, or source `.py` files are included as release data. The executable bundles Python bytecode and browser assets; packaging is not source-code encryption.

Desktop startup errors are recorded in `%LOCALAPPDATA%\Pulse\pulse.log` with bounded log rotation. Logs may include local paths. Share them deliberately.

## Build

On 64-bit Windows with Python installed, double-click `scripts/Build Release.cmd`, or install `packaging/requirements-build.txt` into `.build-env` and run `.build-env\Scripts\python.exe scripts\build_release.py`. The build only bundles the static interface, application dependencies, and icon. Version resources and About both use `pulse.__version__`.

The generated executable targets the Windows architecture of the build machine. Test on a clean Windows machine without Python before a public release, including process inspection, Windows settings links, WSL when available, storage scans, quit/relaunch, and history persistence. Build environments and temporary artifacts are excluded from source control.

This initial portable release is unsigned. Public distribution should use your own Authenticode signing certificate and timestamped signature to establish publisher identity. Signing and an installer can be added when the publisher identity and installation requirements are decided. There is no auto-update mechanism; replace the executable when Pulse is closed. User data remains in the Windows profile.

Packaging follows the official PyInstaller usage documentation: https://pyinstaller.org/en/stable/usage.html.

## Packaged smoke check

Run `dist\Pulse.exe --self-test build\release-check.json`. This explicit diagnostic creates a temporary database, opens and closes a hidden native test window, serves bundled assets on an ephemeral localhost port, and verifies real metrics. It does not read or alter the user history database. Inspect the JSON result for `ok: true`. This supplements clean-machine testing rather than replacing it.
