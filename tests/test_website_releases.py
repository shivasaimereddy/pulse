import json
from pathlib import Path
import tempfile
import unittest
from scripts.website_releases import prepare, checksum

class ReleaseStoreTests(unittest.TestCase):
    def setUp(self):
        sandbox=Path(__file__).resolve().parent.parent/'build'
        sandbox.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='release-test-',dir=sandbox)
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'dist/licenses').mkdir(parents=True)
        (self.root/'dist/licenses/NOTICE.txt').write_text('Sample legal notice')
        (self.root/'website').mkdir()
    def build(self, version, body=b'MZsample-one'):
        exe=self.root/'dist/Pulse.exe';exe.write_bytes(body)
        (self.root/'dist/release-build.json').write_text(json.dumps(dict(version=version,sha256=checksum(exe))))
    def catalog(self, versions):
        (self.root/'website/releases.json').write_text(json.dumps(dict(releases=[dict(version=v,notes=['Sample notes']) for v in versions])))
    def test_preserves_versions_and_sorts_numerically(self):
        self.build('1.0.0');self.catalog(['1.0.0']);prepare(self.root,'1.0.0')
        self.build('1.0.1',b'MZsample-two');self.catalog(['1.0.0','1.0.1'])
        artifacts,items=prepare(self.root,'1.0.1')
        self.assertEqual([i['version'] for i in items],['1.0.1','1.0.0'])
        self.assertEqual((artifacts/'1.0.0/Pulse.exe').read_bytes(),b'MZsample-one')
        self.assertNotEqual(items[0]['sha256'],items[1]['sha256'])
        self.assertIn('/1.0.0/',items[1]['download'])
    def test_rejects_same_version_replacement(self):
        self.build('1.0.0');self.catalog(['1.0.0']);prepare(self.root,'1.0.0')
        self.build('1.0.0',b'MZdifferent')
        with self.assertRaisesRegex(ValueError,'must not be overwritten'):prepare(self.root,'1.0.0')
    def test_checks_receipt_and_archive_tampering(self):
        self.build('1.0.0');self.catalog(['1.0.0']);artifacts,_=prepare(self.root,'1.0.0')
        (artifacts/'1.0.0/Pulse.exe').write_bytes(b'MZtampered')
        with self.assertRaises(ValueError):prepare(self.root,'1.0.0')
        self.build('1.0.1');self.catalog(['1.0.0','1.0.1'])
        with self.assertRaisesRegex(ValueError,'integrity'):prepare(self.root,'1.0.1')
    def test_rejects_version_path_traversal(self):
        self.build('1.0.0');self.catalog(['../private'])
        with self.assertRaises(ValueError):prepare(self.root,'1.0.0')

if __name__=='__main__':unittest.main()
