"""Cross-family software checks. Supply owner-provided IPSWs in
PODTHEMER_TEST_FIRMWARE_DIR; no Apple firmware is bundled with the tests.
"""
from pathlib import Path
import json, os, plistlib, struct, tempfile, unittest, zipfile
import theme_engine as e

FILES = ['iPod_1.1.5.ipsw', 'iPod_2.2.3.ipsw', 'iPod_4.3.1.1.ipsw',
         'iPod_3.1.4.1.ipsw', 'iPod_7.1.4.1.ipsw']


@unittest.skipUnless(os.environ.get('PODTHEMER_TEST_FIRMWARE_DIR'), 'Supply monochrome firmware fixtures')
class MultiDeviceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = []
        folder = Path(os.environ['PODTHEMER_TEST_FIRMWARE_DIR'])
        for name in FILES:
            raw, archive = e.load_stock(folder/name)
            profile = e.identify_firmware(raw)
            outputs = {t['id']: e.build(raw, t) for t in e.THEMES}
            cls.records.append((profile, raw, archive, outputs))

    def test_every_family_retains_commands_strings_headers_and_updater(self):
        for profile, raw, _, outputs in self.records:
            e.activate_device(profile)
            for theme, (data, report) in outputs.items():
                with self.subTest(device=profile['id'], theme=theme):
                    for ranges in e.MAP['protected'].values():
                        for p, n in ranges: self.assertEqual(raw[p:p+n], data[p:p+n])
                    for f in e.MAP['fonts']:
                        self.assertEqual(raw[f['offset']:f['metric']], data[f['offset']:f['metric']])
                        self.assertEqual(raw[f['bitmap_header']:f['data']], data[f['bitmap_header']:f['data']])
                    self.assertEqual(raw[e.flash_update_start(raw):], data[e.flash_update_start(raw):])
                    self.assertEqual(len(raw), len(data))
                    part = struct.unpack_from('<4s4s8I', data, 0x4200)
                    start = part[3]+e.MAP.get('os_payload_bias',512)
                    self.assertEqual(sum(data[start:start+part[4]]) & 0xffffffff, part[7])
                    self.assertFalse(report['hardware_tested'])
                    self.assertEqual(report['icons'],[])
                    self.assertEqual(report['icon_source'],'supplied-firmware')
                    for entry in e.MAP['pictures'].values():
                        p,n=entry['offset'],entry['size']
                        self.assertEqual(raw[p:p+n],data[p:p+n])

    def test_all_20_exports_and_80_previews_match_profiles(self):
        baseline = json.loads((e.HERE/'profile-baselines.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            for profile, _, archive, outputs in self.records:
                e.activate_device(profile)
                for theme, (data, report) in outputs.items():
                    with self.subTest(device=profile['id'], theme=theme):
                        self.assertEqual(e.sha(data), baseline[profile['id']][theme]['payload_sha256'])
                        path=Path(folder)/(profile['id']+'-'+theme+'.ipsw')
                        e.export(archive,data,report,path)
                        with zipfile.ZipFile(path) as z:
                            self.assertIsNone(z.testzip())
                            self.assertEqual(z.read(profile['payload_name']),data)
                            original_manifest=next(data for info,data in archive if info.filename=='manifest.plist')
                            self.assertEqual(z.read('manifest.plist'),original_manifest)
                        for screen in ('main','music','settings','playing'):
                            self.assertEqual(e.preview(data,e.theme_named(theme),screen).size,
                                             (profile['lcd_width'],profile['lcd_height']))
                        if theme=='enlarge':
                            self.assertEqual([f['actual_pixels'] for f in report['fonts']],[13,11,10,11])

    def test_mini_payload_names_and_manifest_families_are_checked(self):
        profile, raw, archive, _ = next(r for r in self.records if r[0]['id']=='ipodmini1g-1.4.1')
        self.assertEqual(profile['payload_name'],'Firmware-3.2.6.1')
        manifest=plistlib.loads(next(data for info,data in archive if info.filename=='manifest.plist'))
        manifest['FirmwarePayload']['UpdaterFamilyID']=7
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad-manifest.ipsw'
            with zipfile.ZipFile(path,'w') as z:
                for info,data in archive:
                    z.writestr(info,plistlib.dumps(manifest) if info.filename=='manifest.plist' else data)
            with self.assertRaisesRegex(ValueError,'manifest'):
                e.load_stock(path)


if __name__ == '__main__': unittest.main()
