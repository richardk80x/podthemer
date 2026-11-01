"""Run against a user-supplied original IPSW. Firmware is never bundled.
PODTHEME_TEST_IPSW=/path/to/iPod_4.3.1.1.ipsw python3 -m unittest -v test_engine
"""
from pathlib import Path
import copy,json,os,struct,tempfile,unittest,zipfile
import theme_engine as engine

@unittest.skipUnless(os.environ.get('PODTHEME_TEST_IPSW'),'Set PODTHEME_TEST_IPSW to an original IPSW.')
class ThemeEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw,cls.archive=engine.load_stock(Path(os.environ['PODTHEME_TEST_IPSW']))
        cls.results={t['id']:engine.build(cls.raw,t) for t in engine.THEMES if t.get('build_status')!='blocked'}

    def test_presets_are_distinct_and_do_not_include_original(self):
        self.assertEqual([t['id'] for t in engine.THEMES],['clear','focus','compact','enlarge'])
        self.assertEqual(len({engine.sha(data) for data,_ in self.results.values()}),4)

    def test_original_comparison_is_byte_identical(self):
        data,report=engine.build(self.raw,engine.theme_named('original'))
        self.assertEqual(data,self.raw)
        self.assertEqual(report['changed_bytes'],0)

    def test_menus_commands_text_and_manifests_survive_all_themes(self):
        for name,(data,report) in self.results.items():
            with self.subTest(theme=name):
                for typ,ranges in engine.MAP['protected'].items():
                    for p,n in ranges:self.assertEqual(data[p:p+n],self.raw[p:p+n],(typ,p))
                self.assertEqual(report['protected_resources']['uneM'],25)
                self.assertEqual(report['protected_resources'][' rtS'],7019)
                self.assertEqual(data[3520000:],self.raw[3520000:])

    def test_focus_has_larger_text_and_every_preset_fits_font_allocations(self):
        self.assertEqual(self.results['focus'][1]['fonts'][0]['actual_pixels'],14)
        for _,report in self.results.values():
            for f in report['fonts']:self.assertLessEqual(f['atlas_columns'],f['atlas_capacity'])

    def test_checksums_are_valid_after_modification(self):
        for data,_ in self.results.values():
            part=struct.unpack_from('<4s4s8I',data,0x4200);start=part[3]+512
            self.assertEqual(sum(data[start:start+part[4]])&0xffffffff,part[7])

    def test_all_screen_previews_and_later_menu_pages_render(self):
        for name,(data,_) in self.results.items():
            for screen in ['main','music','settings','playing']:
                for offset in [0,2,999]:self.assertEqual(engine.preview(data,engine.theme_named(name),screen,offset).size,(160,128))
        clear=self.results['clear'][0];t=engine.theme_named('clear')
        self.assertNotEqual(engine.preview(clear,t,'settings',0).tobytes(),engine.preview(clear,t,'settings',2).tobytes())

    def test_export_round_trip_preserves_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            for name,(data,report) in self.results.items():
                path=Path(d)/(name+'.ipsw');engine.export(self.archive,data,copy.deepcopy(report),path)
                with zipfile.ZipFile(path) as z:
                    self.assertIsNone(z.testzip());self.assertEqual(z.read(engine.MAP['payload_name']),data)
                    for info,original in self.archive:
                        if info.filename!=engine.MAP['payload_name']:self.assertEqual(z.read(info.filename),original)
                self.assertTrue(path.with_suffix('.preview.png').is_file())
                self.assertTrue(path.with_suffix('.validation.json').is_file())

    def test_existing_outputs_are_never_overwritten(self):
        data,report=self.results['clear']
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'existing.ipsw';path.write_bytes(b'keep this')
            with self.assertRaisesRegex(ValueError,'never overwritten'):engine.export(self.archive,data,copy.deepcopy(report),path)
            self.assertEqual(path.read_bytes(),b'keep this')
            other=Path(d)/'other.ipsw';other.with_suffix('.preview.png').write_bytes(b'keep preview')
            with self.assertRaisesRegex(ValueError,'already exists'):engine.export(self.archive,data,copy.deepcopy(report),other)
            self.assertFalse(other.exists())

    def test_modified_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'modified.ipsw'
            with zipfile.ZipFile(path,'w') as z:
                for info,original in self.archive:z.writestr(info,self.results['clear'][0] if info.filename==engine.MAP['payload_name'] else original)
            with self.assertRaisesRegex(ValueError,'supported original'):engine.load_stock(path)

    def test_unsupported_theme_geometry_is_rejected(self):
        invalid=copy.deepcopy(engine.theme_named('clear'));invalid['row_height']=200
        with self.assertRaisesRegex(ValueError,'spacing'):engine.build(self.raw,invalid)


    def test_current_themes_match_approved_release_baselines(self):
        baseline=json.loads((Path(engine.__file__).parent/'existing-theme-baselines.json').read_text())
        for name,(data,_) in self.results.items():
            self.assertEqual(engine.theme_named(name),baseline[name]['config'])
            self.assertEqual(engine.sha(data),baseline[name]['payload_sha256'])

    def test_enlarge_keeps_enlarged_sizes_with_open_semibold_and_stock_icons(self):
        data,report=self.results['enlarge']
        self.assertEqual([f['requested_pixels'] for f in report['fonts']],[13,11,10,11])
        self.assertEqual([f['actual_pixels'] for f in report['fonts']],[13,11,10,11])
        self.assertEqual({f['source_font'] for f in report['fonts']},{'InterTight.ttf'})
        self.assertEqual(engine.theme_named('enlarge')['row_height'],24)
        self.assertEqual(engine.theme_named('enlarge')['icons'],'stock')
        self.assertEqual(engine.theme_named('enlarge')['weight'],600)
        self.assertEqual(report['icons'],[])
        self.assertEqual(report['icon_source'],'supplied-firmware')
        self.assertNotEqual(engine.sha(data),'816bc5f9c5cb0d89108580c63cb6a66920ea36d3426b7b434538232caf4f4f43')
        self.assertFalse(report['hardware_tested'])

    def test_every_original_picture_is_preserved_in_every_theme(self):
        for name,(data,report) in self.results.items():
            self.assertEqual(report['icons'],[])
            self.assertTrue(report['checks']['original_pictures_unchanged'])
            for entry in engine.MAP['pictures'].values():
                p,n=entry['offset'],entry['size']
                self.assertEqual(data[p:p+n],self.raw[p:p+n],name)

    def test_release_rasters_contain_no_icon_payloads(self):
        for profile in engine.ALL_RASTERS['profiles'].values():
            self.assertEqual(set(profile),{'themes'})
        self.assertFalse(any(p.name.startswith('fa-') for p in engine.ASSETS.iterdir()))

    def test_enlarge_cannot_silently_fall_back_to_small_text(self):
        from unittest.mock import patch
        real=engine.remake_font
        def smaller(*args):
            metrics,pixels,report,images=real(*args)
            report=dict(report,actual_pixels=12)
            return metrics,pixels,report,images
        with patch.object(engine,'remake_font',side_effect=smaller):
            with self.assertRaisesRegex(ValueError,'smaller fallback'):
                engine.build(self.raw,engine.theme_named('enlarge'))

    def test_firmware_identification_uses_contents_not_filename(self):
        profile=engine.identify_firmware(self.raw)
        self.assertEqual(profile['id'],'ipod4g-monochrome-3.1.1')
        self.assertEqual((profile['lcd_width'],profile['lcd_height']),(160,128))
        self.assertEqual(profile['preview_style'],'click-wheel-4g')
        with tempfile.TemporaryDirectory() as d:
            import shutil
            renamed=Path(d)/'completely-unrelated-name.ipsw'
            shutil.copyfile(os.environ['PODTHEME_TEST_IPSW'],renamed)
            raw,_=engine.load_stock(renamed)
            self.assertEqual(engine.identify_firmware(raw),profile)
        with self.assertRaisesRegex(ValueError,'not supported'):
            engine.identify_firmware(self.results['clear'][0])

    def test_inspect_reports_model_without_creating_firmware(self):
        import subprocess,sys
        run=subprocess.run([sys.executable,engine.__file__,'--input',os.environ['PODTHEME_TEST_IPSW'],'--inspect'],capture_output=True,text=True,check=True)
        info=json.loads(run.stdout)
        self.assertTrue(info['ok'])
        self.assertEqual(info['device']['id'],'ipod4g-monochrome-3.1.1')
        self.assertEqual(info['themes'],['clear','focus','compact','enlarge'])

    def test_retired_zune_theme_is_not_selectable(self):
        with self.assertRaises(ValueError):engine.theme_named('zune-like')

if __name__=='__main__':unittest.main()
