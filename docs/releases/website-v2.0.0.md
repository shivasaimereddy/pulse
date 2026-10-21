# Pulse website v2.0.0 deployment

This deployment includes the refreshed product page and a newly packaged **Pulse 1.0.0** Windows x64 executable. Website deployment version and app version are separate. The original Git tag `v1.0.0` is retained; do not move it or replace its GitHub assets.

The app remains unsigned. Public app downloads are EXE only. The ZIP below is an operator deployment bundle, never a visitor download option.

## Prepare and publish from the Windows checkout

The prepared files are `dist/Pulse-website.zip` and `dist/Pulse-website.zip.sha256`. The bundle contains the website, new EXE, checksums, notices and release manifests. Existing user databases are not included.

After committing this deployment preparation and creating the annotated `website-v2.0.0` tag:

```powershell
git push origin main
git push origin website-v2.0.0
gh release create website-v2.0.0 dist/Pulse-website.zip dist/Pulse-website.zip.sha256 --repo shivasaimereddy/pulse --verify-tag --title "Pulse website v2.0.0 - app v1.0.0" --notes-file docs/releases/website-v2.0.0.md
```

If GitHub CLI is unavailable on the laptop, create a release for the pushed `website-v2.0.0` tag in GitHub's Releases page and attach **both files as assets**. A link in the description does not upload an asset. Do not replace the older `v1.0.0` release.

## Fetch from GitHub on Ubuntu

Run from the existing Pulse Git checkout. The server fetches source and deployment assets from GitHub; no laptop-to-server copy is needed. Git SSH access and GitHub release API access are separate; the existing `gh` authentication is needed for a private repository.

```bash
git fetch origin --tags
git checkout website-v2.0.0
mkdir -p "$HOME/pulse-deploy/website-v2.0.0"
gh release download website-v2.0.0 --repo shivasaimereddy/pulse --pattern 'Pulse-website.zip*' --dir "$HOME/pulse-deploy/website-v2.0.0"
(cd "$HOME/pulse-deploy/website-v2.0.0" && sha256sum -c Pulse-website.zip.sha256)
```

Continue only when checksum verification reports **OK**. The checksum confirms transfer integrity, not publisher identity.

## Stage and verify before touching the live site

The current Nginx root is `/var/www/html/pulse`. Keep the new files in a separate directory first. The `test` prevents reusing a deployment directory accidentally.

```bash
test ! -e /var/www/pulse-releases/website-v2.0.0 && \
  sudo install -d -m 755 /var/www/pulse-releases/website-v2.0.0 && \
  sudo unzip -q "$HOME/pulse-deploy/website-v2.0.0/Pulse-website.zip" -d /var/www/pulse-releases/website-v2.0.0
python3 scripts/verify_website_bundle.py /var/www/pulse-releases/website-v2.0.0
sudo nginx -t
```

Continue only after both checks pass. No Windows build runs on Ubuntu: the verified EXE is already in the website bundle.

## Switch the existing Nginx root

These commands retain the old site. They refuse to reuse an existing backup or temporary link. The first migration from a real directory to a symlink has a brief gap between the move and the switch; later symlink switches are atomic.

```bash
(
  set -eu
  live=/var/www/html/pulse
  next=/var/www/html/pulse-next
  target=/var/www/pulse-releases/website-v2.0.0
  backup=/var/www/html/pulse-before-website-v2.0.0
  test -f "$target/index.html"
  test ! -e "$next" && test ! -L "$next"
  sudo ln -s "$target" "$next"
  if [ -L "$live" ]; then
    test ! -e "$backup" && test ! -L "$backup"
    sudo cp -P "$live" "$backup"
  elif [ -d "$live" ]; then
    test ! -e "$backup" && test ! -L "$backup"
    sudo mv "$live" "$backup"
  else
    echo 'Expected an existing Pulse web root; stopping.' >&2
    exit 1
  fi
  if ! sudo mv -Tf "$next" "$live"; then
    if [ ! -e "$live" ] && [ ! -L "$live" ]; then sudo mv "$backup" "$live"; fi
    exit 1
  fi
  sudo systemctl reload nginx
)
```

Keep the existing SSL and Cloudflare configuration. Do not replace the entire Nginx config. If Cloudflare caches HTML or JSON, purge the cached Pulse HTML, manifests and unversioned `/downloads/Pulse.exe` alias after switching. New EXE links include the build hash; new scripts, styles and social artwork also have cache identifiers.

## Verify the live download

```bash
curl -fsS https://pulse.infyss.com/release.json
python3 - <<'PY'
import hashlib, json, urllib.request
base='https://pulse.infyss.com/'
with urllib.request.urlopen(base+'release.json') as response:
    release=json.load(response)
with urllib.request.urlopen(base+release['download']) as response:
    content=response.read()
assert release['version']=='1.0.0'
assert hashlib.sha256(content).hexdigest()==release['sha256']
assert len(content)==release['bytes']
print('PASS: live EXE matches the published v1.0.0 checksum.')
PY
```

Also review the page in a browser: the single demo, mobile navigation, both themes, EXE download, verification command and sharing preview.

## Roll back

The deployment backup may be the original directory or a copy of its symlink. These commands unlink only the confirmed live symlink and restore that backup; no site files are deleted.

```bash
(
  set -eu
  test -L /var/www/html/pulse
  test -e /var/www/html/pulse-before-website-v2.0.0
  sudo unlink /var/www/html/pulse
  sudo mv /var/www/html/pulse-before-website-v2.0.0 /var/www/html/pulse
  sudo systemctl reload nginx
)
```

Purge Cloudflare's HTML/manifests again after a rollback if they are cached. Retain the release bundle and previous deployment directories until the new deployment is confirmed.
