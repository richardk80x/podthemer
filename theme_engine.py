#!/usr/bin/env python3
"""Local theme builder for exact verified monochrome iPod firmware profiles.
No firmware is bundled. No device is accessed. Requires Pillow.
"""
from pathlib import Path
import argparse,base64,gzip,hashlib,json,plistlib,struct,sys,zipfile,zlib
sys.dont_write_bytecode=True  # Keep signed app resources immutable when loading reference modules.
from PIL import Image,ImageDraw,ImageFont,ImageOps

HERE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
ASSETS=HERE/'assets'/'fonts'
MAP=json.loads((HERE/'resource-map.json').read_text())
THEMES=json.loads((HERE/'themes.json').read_text())
DEVICES=json.loads((HERE/'device-profiles.json').read_text())
ORIGINAL={'id': 'original', 'name': 'Original', 'description': 'Reference view of the unmodified firmware.', 'font': 'stock', 'weight': 400, 'main_size': 12, 'secondary_size': 10, 'row_height': 18, 'inset': 6, 'icons': 'stock'}
sha=lambda data:hashlib.sha256(data).hexdigest()
RASTER_PATH=HERE/'assets'/'theme-rasters.json.gz'
ALL_RASTERS=json.loads(gzip.decompress(RASTER_PATH.read_bytes())) if RASTER_PATH.exists() else None
ACTIVE_DEVICE=next(p for p in DEVICES if p['id']=='ipod4g-monochrome-3.1.1')
RASTERS=(ALL_RASTERS.get('profiles',{}).get(ACTIVE_DEVICE['id']) if 'profiles' in ALL_RASTERS else ALL_RASTERS) if ALL_RASTERS else None


def require(test,message):
    if not test:raise ValueError(message)


def theme_named(name):
    if name=='original':return ORIGINAL.copy()
    for theme in THEMES:
        if theme['id']==name:return theme
    raise ValueError('Unknown theme. Choose an entry listed by --list.')


def identify_firmware(raw):
    digest=sha(raw)
    matches=[p for p in DEVICES if p['payload_sha256']==digest and p.get('supported')]
    require(len(matches)==1,'This firmware is not supported. No device profile matches its verified contents.')
    profile=matches[0]
    return profile.copy()


def activate_device(profile):
    global MAP,ACTIVE_DEVICE,RASTERS
    target=HERE/profile['resource_map']
    require(profile['resource_map'] in ('resource-map.json','profiles/'+profile['id']+'.json'),'Invalid profile map path.')
    mapping=json.loads(target.read_text())
    require(mapping['stock_sha256']==profile['payload_sha256'] and mapping['payload_name']==profile['payload_name'],'Device profile and resource map disagree.')
    MAP=mapping;ACTIVE_DEVICE=profile.copy()
    RASTERS=(ALL_RASTERS.get('profiles',{}).get(profile['id']) if 'profiles' in ALL_RASTERS else (ALL_RASTERS if profile['id']=='ipod4g-monochrome-3.1.1' else None)) if ALL_RASTERS else None


def flash_update_start(raw):
    return struct.unpack_from('<I',raw,0x4234)[0]


def supported_characters(path):
    """Read Unicode coverage from an unmodified TrueType format 4/12 cmap."""
    data=Path(path).read_bytes()
    u16=lambda p:struct.unpack_from('>H',data,p)[0]
    u32=lambda p:struct.unpack_from('>I',data,p)[0]
    tables={data[p:p+4]:u32(p+8) for p in range(12,12+16*u16(4),16)}
    table=tables[b'cmap'];choices=[]
    for p in range(table+4,table+4+8*u16(table+2),8):
        platform,encoding,offset=struct.unpack_from('>HHI',data,p);at=table+offset;fmt=u16(at)
        if (platform==0 or platform==3 and encoding in (1,10)) and fmt in (4,12):choices.append((fmt,at))
    require(bool(choices),'Font has no supported Unicode cmap.')
    fmt,p=max(choices);result=set()
    if fmt==12:
        for at in range(p+16,p+16+12*u32(p+12),12):
            first,last,glyph=u32(at),u32(at+4),u32(at+8)
            result.update(c for c in range(first,min(last,0x10ffff)+1) if glyph+c-first)
    else:
        count=u16(p+6)//2;end_base=p+14;start_base=end_base+2*count+2;delta_base=start_base+2*count;range_base=delta_base+2*count
        for i in range(count):
            first,last=u16(start_base+2*i),u16(end_base+2*i);delta=u16(delta_base+2*i);offset=u16(range_base+2*i)
            for code in range(first,last+1):
                glyph=u16(range_base+2*i+offset+2*(code-first)) if offset else code
                if glyph and ((glyph+delta)&65535):result.add(code)
    return result


def text_font(theme,size,bold=False):
    if theme['font']=='atkinson':
        path=ASSETS/('AtkinsonHyperlegible-Bold.ttf' if bold or theme['weight']>=600 else 'AtkinsonHyperlegible-Regular.ttf')
    elif theme['font']=='inter-tight':path=ASSETS/'InterTight.ttf'
    elif theme['font']=='roboto':path=ASSETS/'RobotoCondensed.ttf'
    else:path=ASSETS/'Inter.ttf'
    font=ImageFont.truetype(str(path),size)
    if theme['font']=='inter':font.set_variation_by_axes([14,theme['weight']])
    elif theme['font'] in ('roboto','inter-tight'):font.set_variation_by_axes([theme['weight']])
    return font,path


def char_map(data,font):
    mapped={}
    for g in range(font['groups']):
        first,offset,length=struct.unpack_from('<HHI',data,font['offset']+16+g*8)
        for i in range(length):
            idx=struct.unpack_from('<H',data,font['header']+100+(offset+i-1)*2)[0]
            require(idx<font['num_metrics'],'Font mapping is outside its metrics block.')
            mapped.setdefault(idx,[]).append(first+i)
    return mapped


def glyph(data,font,idx):
    a,z,w,ident=struct.unpack_from('<HHhh',data,font['metric']+idx*8)
    require(0<=a<=z<=font['bitmap_width'],'Glyph exceeds its bitmap allocation.')
    im=Image.new('L',(max(1,z-a),font['bitmap_height']))
    for y in range(im.height):
        for x in range(z-a):
            bit=a+x;im.putpixel((x,y),255*((data[font['data']+y*font['stride']+bit//8]>>(7-bit%8))&1))
    return im,w,ident


def font_layout(images,compact=False):
    """Store each glyph as contiguous columns; optionally share identical column runs.
    Only Enlarge opts in. Unicode mappings, advances and glyph pixels are unchanged.
    """
    unique={};metrics=[];columns=0
    if compact:
        packed=b'';height=images[0][0].height
        require(all(im.height==height for im,_,_ in images),'Mixed glyph cell heights.')
        for im,_,_ in sorted(images,key=lambda item:-item[0].width):
            key=(im.size,im.tobytes())
            if key in unique:continue
            vertical=b''.join(im.crop((x,0,x+1,height)).tobytes() for x in range(im.width))
            at=packed.find(vertical)
            while at>=0 and at%height:at=packed.find(vertical,at+1)
            if at>=0:a=at//height
            else:
                overlap=min(im.width,columns)
                while overlap and not packed.endswith(vertical[:overlap*height]):overlap-=1
                a=columns-overlap;packed+=vertical[overlap*height:];columns=len(packed)//height
            unique[key]=(a,a+im.width,im)
    else:
        for im,_,_ in images:
            key=(im.size,im.tobytes())
            if key not in unique:unique[key]=(columns,columns+im.width,im);columns+=im.width
    for im,w,ident in images:
        a,z,_=unique[(im.size,im.tobytes())];metrics.append((a,z,w,ident))
    return metrics,list(unique.values()),columns


def packed_font_images(font,images,compact=False):
    metrics,placements,columns=font_layout(images,compact)
    require(columns<=font['bitmap_width'],'Canonical font exceeds original allocation.')
    atlas=Image.new('L',(font['bitmap_width'],font['bitmap_height']))
    for a,z,im in placements:atlas.paste(im,(a,0))
    packed=bytearray(font['end']-font['data'])
    for y in range(atlas.height):
        for x in range(columns):
            if atlas.getpixel((x,y)):packed[y*font['stride']+x//8]|=1<<(7-x%8)
    return b''.join(struct.pack('<HHhh',*m) for m in metrics),bytes(packed)


def remake_font(base,font,theme,use_cache=True):
    if use_cache and RASTERS is not None:
        canonical=RASTERS['themes'].get(theme['id'])
        require(canonical is not None and canonical['config']==theme,'Theme does not match its canonical open-font rasters.')
        record=canonical['fonts'][str(font['offset'])]
        path=ASSETS/record['report']['source_font']
        require(sha(path.read_bytes())==record['source_sha256'],'Open-font source asset changed; rebuild canonical rasters.')
        images=[glyph(base,font,idx) for idx in range(font['num_metrics'])]
        for index,item in record['replacements'].items():
            im=Image.frombytes('L',tuple(item['size']),zlib.decompress(base64.b64decode(item['pixels'])))
            images[int(index)]=(im,item['advance'],item['bearing'])
        metrics,pixels=packed_font_images(font,images,compact=theme['id']=='enlarge')
        return metrics,pixels,record['report'].copy(),images
    wanted=theme['main_size'] if font['name']=='Chicago' else theme['secondary_size']-(1 if font['size']==9 else 0)
    cmap=char_map(base,font);baseline=font['height']-1
    for size in range(wanted,8,-1):
        ft,path=text_font(theme,size);coverage=supported_characters(path);images=[];replaced=[];retained=[]
        for idx in range(font['num_metrics']):
            old,advance,ident=glyph(base,font,idx)
            code=next((c for c in cmap.get(idx,[]) if c in coverage and (33<=c<127 or 160<=c<=1279)),None)
            if code is None:images.append((old,advance,ident));retained.append(idx);continue
            im=Image.new('L',(96,80));ImageDraw.Draw(im).text((24,40),chr(code),font=ft,fill=255,anchor='ls')
            im=im.point(lambda p:255 if p>=112 else 0);bb=im.getbbox()
            if not bb or bb[1]-40+baseline<0 or bb[3]-40+baseline>font['bitmap_height']:
                images.append((old,advance,ident));retained.append(idx);continue
            out=Image.new('L',(bb[2]-bb[0],font['bitmap_height']));out.paste(im.crop(bb),(0,bb[1]-40+baseline))
            images.append((out,max(round(ft.getlength(chr(code))),bb[2]-24+1),bb[0]-24));replaced.append(idx)
        metrics,placements,columns=font_layout(images,compact=theme['id']=='enlarge')
        if columns>font['bitmap_width']:continue
        # Reject a nominal theme that silently leaves letters/numbers in the old font.
        require(all(any(i in replaced for i,codes in cmap.items() if cp in codes) for cp in list(range(48,58))+list(range(65,91))+list(range(97,123))),f'Font cannot fully render letters and numbers at {size}px.')
        atlas=Image.new('L',(font['bitmap_width'],font['bitmap_height']))
        for a,z,im in placements:atlas.paste(im,(a,0))
        packed=bytearray(font['end']-font['data'])
        for y in range(atlas.height):
            for x in range(columns):
                if atlas.getpixel((x,y)):packed[y*font['stride']+x//8]|=1<<(7-x%8)
        metric_bytes=b''.join(struct.pack('<HHhh',*m) for m in metrics)
        report=dict(font=font['name'],style=font['style'],source_font=path.name,requested_pixels=wanted,actual_pixels=size,replaced_glyphs=len(replaced),retained_original_glyphs=len(retained),atlas_columns=columns,atlas_capacity=font['bitmap_width'])
        return metric_bytes,bytes(packed),report,images
    raise ValueError('The selected text font cannot fit the original firmware font allocation.')


def picture_shape(base,rid):
    entry=MAP['pictures'][str(rid)];p=entry['offset']
    h,w,stride,depth,_,_,length=struct.unpack_from('<IIHHHHI',base,p+8)
    require(depth in (1,2,4) and length==h*stride and entry['size']==28+length,'Unexpected bitmap layout.')
    return p,w,h,stride,depth,length


def decode_picture(data,rid):
    p,w,h,stride,depth,length=picture_shape(data,rid);im=Image.new('L',(w,h),255);maximum=(1<<depth)-1
    for y in range(h):
        for x in range(w):
            bit=x*depth;value=(data[p+28+y*stride+bit//8]>>(8-depth-bit%8))&maximum
            im.putpixel((x,y),255-round(value*255/maximum))
    return im


def load_stock(path):
    with zipfile.ZipFile(path) as z:
        require(len(z.infolist())==2 and 'manifest.plist' in z.namelist(),'Choose an original monochrome iPod IPSW.')
        require(all(i.file_size<10_000_000 for i in z.infolist()),'Unexpectedly large firmware archive.')
        require(z.testzip() is None,'Archive integrity check failed.')
        archive=[(i,z.read(i.filename)) for i in z.infolist()]
    payloads=[(info,data) for info,data in archive if info.filename!='manifest.plist']
    require(len(payloads)==1,'Unexpected firmware archive structure.')
    info,raw=payloads[0]
    try:profile=identify_firmware(raw)
    except ValueError:raise ValueError('Choose a supported original monochrome iPod IPSW, not modified firmware. Its contents do not match an implemented profile.')
    require(info.filename==profile['payload_name'],'The archive payload name disagrees with its verified firmware identity.')
    manifest=plistlib.loads(next(data for info,data in archive if info.filename=='manifest.plist'))['FirmwarePayload']
    require(manifest.get('FirmwareName')==profile['payload_name'] and manifest.get('FamilyID')==profile['manifest_family_id'] and manifest.get('UpdaterFamilyID')==profile['manifest_updater_family_id'],'Firmware manifest and verified device family disagree.')
    activate_device(profile)
    require(len(raw)==MAP['payload_length'],'Unexpected firmware length.')
    part=struct.unpack_from('<4s4s8I',raw,0x4200);start=part[3]+MAP.get('os_payload_bias',512);length=part[4]
    require((sum(raw[start:start+length])&0xffffffff)==part[7],'Original firmware checksum failed.')
    return raw,archive


def build(raw,theme):
    activate_device(identify_firmware(raw))
    require(sha(raw)==MAP['stock_sha256'],'Only the exact original firmware is supported.')
    require(theme['font'] in ('stock','inter','inter-tight','roboto','atkinson') and theme['icons']=='stock','Unknown theme font or icon style.')
    require(18<=theme['row_height']<=28 and 6<=theme['inset']<=12,'Theme spacing is outside supported bounds.')
    require(9<=theme['main_size']<=14 and 9<=theme['secondary_size']<=11 and 400<=theme['weight']<=700,'Theme typography is outside supported bounds.')
    result=bytearray(raw);allowed=[];font_reports=[];icon_reports=[]
    if theme['font']!='stock':
        for f in MAP['fonts']:
            metrics,pixels,report,images=remake_font(raw,f,theme)
            if theme['id']=='enlarge':require(report['actual_pixels']==report['requested_pixels'],'Enlarge requires its enlarged font sizes; smaller fallback is not allowed.')
            p=f['metric'];result[p:p+len(metrics)]=metrics;allowed.append((p,p+len(metrics)))
            result[f['data']:f['end']]=pixels;allowed.append((f['data'],f['end']));font_reports.append(report)
            # Decode every stored glyph and check preserved/replaced raster data.
            for idx,(expected,w,ident) in enumerate(images):
                im,actual_w,actual_i=glyph(result,f,idx)
                require((im.size,im.tobytes(),actual_w,actual_i)==(expected.size,expected.tobytes(),w,ident),'Encoded font did not round-trip.')
    for p in MAP['rows']:struct.pack_into('<i',result,p,theme['row_height']);allowed.append((p,p+4))
    for p in MAP['insets']:struct.pack_into('<i',result,p,theme['inset']);allowed.append((p,p+4))
    # Retain the supplied firmware's complete picture resources, including animations.
    for entry in MAP['pictures'].values():
        p,n=entry['offset'],entry['size']
        require(raw[p:p+n]==result[p:p+n],'Original firmware picture changed.')
    part=struct.unpack_from('<4s4s8I',raw,0x4200);start=part[3]+MAP.get('os_payload_bias',512);length=part[4];checksum=sum(result[start:start+length])&0xffffffff
    struct.pack_into('<I',result,0x421c,checksum);allowed.append((0x421c,0x4220))
    mask=bytearray(len(raw))
    for a,b in allowed:mask[a:b]=b'\1'*(b-a)
    changed=[i for i,(a,b) in enumerate(zip(raw,result)) if a!=b]
    require(len(raw)==len(result) and all(mask[i] for i in changed),'Unexpected change outside theme allocations.')
    protected={}
    for typ,ranges in MAP['protected'].items():
        for p,n in ranges:require(raw[p:p+n]==result[p:p+n],f'Protected {typ} resource changed.')
        protected[typ]=len(ranges)
    for f in MAP['fonts']:
        require(raw[f['offset']:f['metric']]==result[f['offset']:f['metric']],'Font header or Unicode mapping changed.')
        require(raw[f['bitmap_header']:f['data']]==result[f['bitmap_header']:f['data']],'Font bitmap header changed.')
    require(raw[flash_update_start(raw):]==result[flash_update_start(raw):],'Flash update partition changed.')
    report=dict(device=ACTIVE_DEVICE.copy(),theme=theme,asset_sha256={p.name:sha(p.read_bytes()) for p in ASSETS.iterdir() if p.suffix in ('.ttf','.otf')},source_payload_sha256=sha(raw),result_payload_sha256=sha(result),changed_bytes=len(changed),fonts=font_reports,icons=icon_reports,icon_source='supplied-firmware',protected_resources=protected,allowed_ranges=allowed,hardware_tested=False,checks=dict(font_raster_round_trip=True,original_pictures_unchanged=True,all_changes_within_allowlist=True,menus_and_commands_unchanged=True,all_text_resources_unchanged=True,unicode_maps_and_font_headers_unchanged=True,firmware_length_unchanged=True,flash_update_partition_unchanged=True,os_checksum_valid=True))
    return bytes(result),report


def preview(data,theme,screen='main',offset=0):
    sw,sh=ACTIVE_DEVICE['lcd_width'],ACTIVE_DEVICE['lcd_height']
    im=Image.new('L',(sw,sh),255);d=ImageDraw.Draw(im);f=MAP['fonts'][0];mapping={c:i for i,codes in char_map(data,f).items() for c in codes}
    def width(s):return sum(glyph(data,f,mapping.get(ord(c),0))[1] for c in s)
    def fitted(s,maxwidth):
        if width(s)>maxwidth:
            while s and width(s+'…')>maxwidth:s=s[:-1]
            s+='…'
        return s
    def text(s,x,y,inverted=False,maxwidth=148):
        s=fitted(s,maxwidth)
        for c in s:
            ink,w,ident=glyph(data,f,mapping.get(ord(c),0));im.paste(255 if inverted else 0,(x+ident,y),ink);x+=w
    items={'main':('iPod',['Music','Extras','Settings','Shuffle Songs','Backlight','Now Playing']),'music':('Music',['Playlists','Artists','Albums','Songs','Podcasts','Genres','Composers','Audiobooks']),'settings':('Settings',['About','Main Menu','Shuffle','Repeat','Backlight Timer','Audiobooks','EQ','Sound Check','Contrast','Clicker','Date & Time','Contacts','Language','Legal','Reset All Settings'])}
    items=MAP.get('preview_menus',items)
    title='Now Playing' if screen=='playing' else items[screen][0]
    # Header/menu centering illustrates the resource geometry, not an emulated OS.
    text(title,(sw-width(title))//2,1,maxwidth=sw-62)
    icons=MAP.get('preview_icons',dict(play=13104,battery=9684,chevron=9646))
    im.paste(decode_picture(data,icons['play']),(2,4));im.paste(decode_picture(data,icons['battery']),(sw-26,4));d.line((0,18,sw-1,18),fill=0)
    if screen=='playing':
        # Stock metadata is centered; only overlong fields need truncation here.
        positions=(31,53,74) if sh==128 else (23,43,63)
        for label,y in zip(('Dreams','Fleetwood Mac','Rumours'),positions):
            label=fitted(label,sw-16)
            text(label,(sw-width(label))//2,y,maxwidth=sw-16)
        d.rectangle((8,sh-28,sw-9,sh-25),outline=0);d.rectangle((8,sh-28,round(sw*0.41),sh-25),fill=0)
        # Progress labels use the theme's bundled open font only in this illustrative preview.
        if theme['id']=='enlarge':
            secondary=MAP['fonts'][1]
            cmap={c:i for i,codes in char_map(data,secondary).items() for c in codes}
            def timestamp(label,x):
                for c in label:
                    ink,w,ident=glyph(data,secondary,cmap.get(ord(c),0))
                    im.paste(0,(x+ident,sh-18),ink);x+=w
            timestamp('1:42',8);timestamp('-2:29',sw-35)
        else:
            small,_=text_font(theme if theme['font']!='stock' else theme_named('compact'),9)
            d.text((8,sh-18),'1:42',font=small,fill=0);d.text((sw-35,sh-18),'-2:29',font=small,fill=0)
    else:
        row=theme['row_height'];count=(sh-19)//row
        offset=max(0,min(offset,max(0,len(items[screen][1])-count)))
        for i,label in enumerate(items[screen][1][offset:offset+count]):
            y=19+i*row;selected=i==0
            if selected:d.rectangle((0,y,sw-1,y+row-1),fill=0)
            text(label,theme['inset'],y+(row-f['bitmap_height'])//2,inverted=selected,maxwidth=sw-26-theme['inset'])
            icon=decode_picture(data,icons['chevron'])
            if selected:icon=ImageOps.invert(icon)
            im.paste(icon,(sw-icon.width-2,y+(row-icon.height)//2))
    return ImageOps.colorize(im,'#18251e','#d4dfca')


def export(archive,result,report,path):
    path=Path(path);require(not path.exists(),'Choose a new output filename; existing files are never overwritten.')
    # Reject sidecar collisions too, so a preview/report can never overwrite unrelated work.
    report_path=path.with_suffix('.validation.json');png=path.with_suffix('.preview.png')
    require(not report_path.exists() and not png.exists(),'A report or preview already exists for this output name.')
    with path.open('xb') as f:
        with zipfile.ZipFile(f,'w') as z:
            for info,data in archive:z.writestr(info,result if info.filename==MAP['payload_name'] else data)
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None and z.read(MAP['payload_name'])==result,'Final archive verification failed.')
        for info,data in archive:
            if info.filename!=MAP['payload_name']:require(z.read(info.filename)==data,'Manifest changed.')
    report['checks']['zip_integrity']=True;report['checks']['manifest_unchanged']=True;report['ipsw_sha256']=sha(path.read_bytes())
    report_path.write_text(json.dumps(report,indent=2)+'\n');preview(result,report['theme']).save(png)
    return str(path)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--list',action='store_true');p.add_argument('--inspect',action='store_true');p.add_argument('--input',type=Path);p.add_argument('--theme',default='clear',choices=[t['id'] for t in THEMES]+['original']);p.add_argument('--output',type=Path);p.add_argument('--preview',type=Path);p.add_argument('--offset',type=int,default=0);p.add_argument('--screen',default='main',choices=['main','music','settings','playing']);args=p.parse_args()
    if args.list:print(json.dumps(THEMES));return
    try:
        require(args.input is not None,'Choose the original IPSW first.');raw,archive=load_stock(args.input);device=identify_firmware(raw);theme=theme_named(args.theme)
        if args.inspect:
            require(not args.output and not args.preview,'Inspection does not create outputs.')
            print(json.dumps(dict(ok=True,device=device,themes=[t['id'] for t in THEMES])));return
        result,report=build(raw,theme)
        if args.preview:preview(result,theme,args.screen,args.offset).save(args.preview)
        if args.output:export(archive,result,report,args.output)
        print(json.dumps(dict(ok=True,device=device,theme=theme['name'],report=report,preview=str(args.preview) if args.preview else None,output=str(args.output) if args.output else None)))
    except Exception as e:print(json.dumps(dict(ok=False,error=str(e))));sys.exit(1)

if __name__=='__main__':main()
