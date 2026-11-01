#!/usr/bin/env python3
"""Developer-only: freeze replacement open glyphs, never stock glyphs.
Supply the exact owner's raw stock firmware; no complete firmware is written.
Use the canonical RAQM-enabled Pillow build recorded in raster metadata.
"""
from pathlib import Path
import sys,json,gzip,base64,zlib
from PIL import ImageFont,features
import theme_engine as e

def encoded(im):
 return dict(size=list(im.size),pixels=base64.b64encode(zlib.compress(im.tobytes(),9)).decode())

def main():
 if len(sys.argv)<2:raise SystemExit('Usage: freeze_theme_rasters.py RAW_STOCK_FIRMWARE [MORE_RAW_FILES ...]')
 import PIL
 cache=dict(format='podthemer-open-rasters-v3',pillow=PIL.__version__,freetype=features.version_module('freetype2'),raqm=features.version_feature('raqm'),profiles={})
 e.require(features.check_feature('raqm'),'Use the canonical RAQM-enabled renderer; baseline tests must pass after regeneration.')
 for filename in sys.argv[1:]:
  raw=Path(filename).read_bytes();profile=e.identify_firmware(raw);e.activate_device(profile)
  target=dict(themes={})
  for theme in e.THEMES:
   record=dict(config=theme,fonts={})
   for font in e.MAP['fonts']:
    _,_,report,images=e.remake_font(raw,font,theme,use_cache=False)
    replacements={}
    for idx,(im,advance,bearing) in enumerate(images):
     old,w,b=e.glyph(raw,font,idx)
     if (old.size,old.tobytes(),w,b)==(im.size,im.tobytes(),advance,bearing):continue
     item=encoded(im);item.update(advance=advance,bearing=bearing);replacements[str(idx)]=item
    record['fonts'][str(font['offset'])]=dict(report=report,source_sha256=e.sha((e.ASSETS/report['source_font']).read_bytes()),replacements=replacements)
   target['themes'][theme['id']]=record
  cache['profiles'][profile['id']]=target
 e.RASTER_PATH.write_bytes(gzip.compress(json.dumps(cache,separators=(',',':')).encode(),mtime=0))
 print(e.RASTER_PATH, e.RASTER_PATH.stat().st_size)

if __name__=='__main__':main()
