"""Validate the built marketing site and the release files users will download."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit, unquote
import xml.etree.ElementTree as ET
import zipfile

from pulse import __version__

ROOT=Path(__file__).resolve().parent.parent
SITE=ROOT/'website/dist'


class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.ids=[];self.links=[];self.images=[];self.feed(text)

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        for key in ('href','src'):
            if key in attrs:self.links.append(attrs[key])
        if tag=='img':self.images.append(attrs)


@unittest.skipUnless((SITE/'index.html').is_file(),'Build the website with python scripts/build_website.py first.')
class WebsiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(SITE/'index.html').read_text(encoding='utf-8')
        cls.page=Page(cls.html)
        cls.release=json.loads((SITE/'release.json').read_text(encoding='utf-8'))

    def test_templates_and_all_local_links_resolve(self):
        self.assertNotIn('{{',self.html)
        self.assertEqual(len(self.page.ids),len(set(self.page.ids)))
        for link in self.page.links:
            parsed=urlsplit(link)
            if parsed.scheme or parsed.netloc:continue
            if parsed.path:
                self.assertTrue((SITE/unquote(parsed.path)).is_file(),link)
            elif parsed.fragment:
                self.assertIn(parsed.fragment,self.page.ids)

    def test_product_tour_is_native_interactive_content(self):
        self.assertIn('data-pulse-demo="tour"', self.html)
        self.assertEqual(self.html.count('data-pulse-demo='), 1)
        self.assertIn('src="demo.js?v=', self.html)
        self.assertIn('href="demo.css?v=', self.html)
        self.assertNotIn('assets/screens/', self.html)
        self.assertNotIn('id="product-preview"', self.html)
        self.assertIn('never reads your device or files', self.html)
        self.assertTrue((SITE/'demo.js').is_file())
        self.assertFalse((SITE/'assets/screens').exists())

    def test_clear_intro_and_progressive_enhancement(self):
        self.assertNotIn('laptop', self.html.lower())
        self.assertIn('class="principles-strip"', self.html)
        self.assertIn('class="launch-steps"', self.html)
        self.assertIn('class="app-story-card"', self.html)
        self.assertIn('<noscript>', self.html)
        self.assertIn('assets/demo-poster.svg', self.html)
        catalog=json.loads((SITE/'releases.json').read_text())
        if len(catalog['releases'])==1:
            self.assertIn('for="download-version" hidden', self.html)

    def test_download_matches_version_checksum_and_archive(self):
        self.assertEqual(self.release['version'],__version__)
        executable=(SITE/self.release['download']).read_bytes()
        self.assertEqual(hashlib.sha256(executable).hexdigest(),self.release['sha256'])
        self.assertEqual(len(executable),self.release['bytes'])
        self.assertTrue(executable.startswith(b'MZ'))
        self.assertIn(self.release['sha256'],(SITE/'downloads/SHA256SUMS.txt').read_text())
        catalog=json.loads((SITE/'releases.json').read_text())
        self.assertEqual(catalog['latest'],__version__)
        for release in catalog['releases']:
            self.assertEqual(hashlib.sha256((SITE/release['download']).read_bytes()).hexdigest(),release['sha256'])
            self.assertIn(release['sha256'],((SITE/release['download']).parent/'SHA256SUMS.txt').read_text())
        self.assertFalse(any((SITE/'downloads').rglob('*.zip')))

    def test_previews_are_valid_private_data_free_vectors(self):
        for image in self.page.images:
            self.assertTrue(image.get('alt'))
            self.assertTrue(image.get('width') and image.get('height'))
        for file in (SITE/'assets').glob('*.svg'):
            ET.fromstring(file.read_text(encoding='utf-8'))
            self.assertLess(file.stat().st_size,60000)
            self.assertNotIn('shiva',file.read_text(encoding='utf-8').lower())
        self.assertIn('illustrative sample data',self.html.lower())

    def test_no_third_party_scripts_or_user_data_in_site_archive(self):
        self.assertNotIn('<script src="http',self.html)
        self.assertNotIn('fonts.googleapis',self.html)
        with zipfile.ZipFile(ROOT/'dist/Pulse-website.zip') as archive:
            self.assertIn('index.html',archive.namelist())
            self.assertIn('downloads/Pulse.exe',archive.namelist())
            self.assertFalse(any(name.endswith(('.sqlite3','.py','.log')) for name in archive.namelist()))

    def test_no_public_source_or_stack_marketing(self):
        for term in ('github','python','sqlite','open-source','open source','source code'):
            self.assertNotIn(term,self.html.lower())
        self.assertNotIn('repository',self.release)

    def test_checksum_guide_uses_selected_exe_and_stays_on_page(self):
        self.assertIn('href="#verify-download" id="open-checksum"',self.html)
        self.assertIn('data-exe-hash="'+self.release['sha256']+'"',self.html)
        self.assertIn('data-filename="'+self.release['filename']+'"',self.html)
        self.assertIn('id="download-version"',self.html)
        self.assertIn('id="release-catalog"',self.html)
        self.assertIn('id="checksum-command"',self.html)
        self.assertNotIn('type="file"',self.html)
        self.assertIn('<dialog class="checksum-modal"',self.html)
        self.assertIn('Copy verification command',self.html)
        self.assertNotIn('Download ZIP',self.html)
        self.assertNotIn('ARCHIVE_URL',self.html)

    def test_social_metadata_is_server_rendered_absolute_and_complete(self):
        import re
        import struct
        config=json.loads((ROOT/'website/site.config.json').read_text())
        for prop in ('og:url','og:image','og:image:secure_url'):
            match=re.search(r'<meta property="'+prop+r'" content="([^"]+)"',self.html)
            self.assertIsNotNone(match)
            self.assertTrue(match.group(1).startswith(config['siteUrl']))
        self.assertIn('property="og:image:width" content="1200"',self.html)
        self.assertIn('property="og:image:height" content="630"',self.html)
        self.assertIn('property="og:image:type" content="image/png"',self.html)
        self.assertIn('rel="canonical" href="'+config['siteUrl']+'"',self.html)
        image_path=re.search(r'<meta property="og:image" content="([^"]+)"',self.html).group(1)
        image=SITE/urlsplit(image_path).path.lstrip('/')
        data=image.read_bytes()
        self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II',data[16:24]),(1200,630))
        schema=re.search(r'<script type="application/ld\+json">(.*?)</script>',self.html,re.S)
        self.assertEqual(json.loads(schema.group(1))['@graph'][1]['name'],'Pulse')
        ET.fromstring((SITE/'sitemap.xml').read_text())


if __name__=='__main__':unittest.main()
