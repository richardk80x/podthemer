#!/usr/bin/env python3
"""Offline packaged-app QA. Requires owner-provided stock IPSWs; never flashes.
Usage: check_packaged_app.py APP_PATH FIRMWARE_DIRECTORY OUTPUT_REPORT
"""
from pathlib import Path
import hashlib,json,os,plistlib,re,shutil,subprocess,sys,tempfile,zipfile
FILES=['iPod_1.1.5.ipsw','iPod_2.2.3.ipsw','iPod_4.3.1.1.ipsw','iPod_3.1.4.1.ipsw','iPod_7.1.4.1.ipsw']

def main():
 if len(sys.argv)!=4:raise SystemExit(__doc__)
 app,firmwares,report_path=map(lambda s:Path(s).resolve(),sys.argv[1:])
 baseline=json.loads(Path(__file__).with_name('profile-baselines.json').read_text())
 env={'PATH':'/usr/bin:/bin','LANG':'en_US.UTF-8','TMPDIR':tempfile.gettempdir()}
 reports={};counts=dict(exports=0,previews=0)
 with tempfile.TemporaryDirectory(prefix='pod-themer-qa-') as folder:
  work=Path(folder);copy=work/'Moved app with spaces'/'Pod Themer.app';copy.parent.mkdir()
  shutil.copytree(app,copy,symlinks=True)
  exe=copy/'Contents/Helpers/PodThemerEngine.app/Contents/MacOS/PodThemerEngine'
  def call(*args,ok=True):
   p=subprocess.run([str(exe),*map(str,args)],env=env,capture_output=True,text=True)
   if ok:assert p.returncode==0,(p.stdout,p.stderr)
   else:assert p.returncode!=0
   return json.loads(p.stdout)
  assert [t['id'] for t in call('--list')]==['clear','focus','compact','enlarge']
  for index,name in enumerate(FILES):
   source=firmwares/name;digest=hashlib.sha256(source.read_bytes()).hexdigest()
   renamed=work/('unrelated-name-'+str(index)+'.ipsw');shutil.copyfile(source,renamed)
   profile=call('--input',renamed,'--inspect')['device'];pid=profile['id'];reports[pid]={}
   print('Checking',profile['display_name'],flush=True)
   for theme in baseline[pid]:
    target=work/(pid+'-'+theme+'.ipsw')
    response=call('--input',renamed,'--theme',theme,'--output',target);counts['exports']+=1
    report=response['report'];reports[pid][theme]=report
    assert report['icons']==[] and report['icon_source']=='supplied-firmware'
    assert report['checks']['original_pictures_unchanged']
    assert report['result_payload_sha256']==baseline[pid][theme]['payload_sha256']
    assert response['device']==profile and not report['hardware_tested']
    with zipfile.ZipFile(target) as z,zipfile.ZipFile(source) as orig:
     assert z.testzip() is None and z.read('manifest.plist')==orig.read('manifest.plist')
     payload=z.read(profile['payload_name']);stock=orig.read(profile['payload_name'])
     assert hashlib.sha256(payload).hexdigest()==baseline[pid][theme]['payload_sha256']
     mapping=json.loads((Path(__file__).parent/profile['resource_map']).read_text())
     for entry in mapping['pictures'].values():
      p,n=entry['offset'],entry['size'];assert payload[p:p+n]==stock[p:p+n]
    for screen in ['main','music','settings','playing']:
     preview=work/(pid+'-'+theme+'-'+screen+'.png')
     call('--input',renamed,'--theme',theme,'--screen',screen,'--preview',preview);counts['previews']+=1
     contents=preview.read_bytes();assert contents[:8]==b'\x89PNG\r\n\x1a\n'
     import struct
     assert struct.unpack('>II',contents[16:24])==(profile['lcd_width'],profile['lcd_height'])
    if theme=='enlarge':
     assert [f['actual_pixels'] for f in report['fonts']]==[13,11,10,11]
     assert report['theme']['weight']==600
     assert {f['source_font'] for f in report['fonts']}=={'InterTight.ttf'}
   assert not call('--input',target,'--inspect',ok=False)['ok']
   assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
  subprocess.run(['codesign','--verify','--deep','--strict',str(copy)],check=True)
 binaries=[]
 for p in app.rglob('*'):
  if not p.is_file() or p.is_symlink():continue
  with p.open('rb') as f:magic=f.read(4)
  if magic not in [b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe',b'\xca\xfe\xba\xbe']:continue
  text=subprocess.run(['otool','-l',str(p)],capture_output=True,text=True,check=True).stdout
  mins=re.findall(r'\bminos\s+(\d+(?:\.\d+)*)',text)
  if not mins:mins=re.findall(r'cmd LC_VERSION_MIN_MACOSX\n\s*cmdsize \d+\n\s*version\s+(\d+(?:\.\d+)*)',text)
  assert mins and all(tuple(map(int,v.split('.'))) <= (14,0,0) for v in mins),(str(p),mins)
  links=subprocess.run(['otool','-L',str(p)],capture_output=True,text=True,check=True).stdout
  assert '/opt/homebrew/' not in links and '/Library/Frameworks/Python.framework/' not in links,(p,links)
  binaries.append(dict(path=str(p.relative_to(app)),minimum_macos=mins))
 assert not any(p.name.startswith('fa-') and p.suffix=='.otf' for p in app.rglob('*'))
 info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
 assert info['CFBundleDisplayName']=='Pod Themer' and (app/'Contents/Resources'/info['CFBundleIconFile']).is_file()
 summary=dict(version=info['CFBundleShortVersionString'],standalone_runtime=True,clean_environment=True,relocated_app_test=True,theme_reports=reports,native_binaries=binaries,checks=counts,original_inputs_unchanged=True,developer_id_signed=False,notarized=False,hardware_tested=False)
 summary['fixture_note']=json.loads(Path(__file__).with_name('migration-verification.json').read_text())['fixture_note']
 report_path.write_text(json.dumps(summary,indent=2)+'\n')
 print('PASS:',counts,'native binaries:',len(binaries))

if __name__=='__main__':main()
