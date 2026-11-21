#!/usr/bin/env python3
"""Local-only LibreOffice document generation and fresh PDF-ink measurement.

This is a documented reconstruction, not the recovered original form generator.
Run in the recorded network-disabled container via run_lo_reconstruction.py.
"""
import argparse,hashlib,json,math,os,shutil,subprocess,time
from pathlib import Path
from xml.sax.saxutils import escape
import numpy as np
from PIL import Image
import pymupdf

FAMILIES={'DejaVuSans':'DejaVu Sans','LiberationSerif':'Liberation Serif'}
NS=' '.join(f'xmlns:{k}="{v}"' for k,v in {
 'office':'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
 'style':'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
 'text':'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
 'fo':'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
 'svg':'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0'}.items())

def document(styles,body,width,height):
    faces=''.join(f'<style:font-face style:name="{key}" svg:font-family="{name}"/>' for key,name in FAMILIES.items())
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document {NS} office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.text">
<office:font-face-decls>{faces}</office:font-face-decls>
<office:styles><style:default-style style:family="paragraph"><style:paragraph-properties fo:margin-top="0pt" fo:margin-bottom="0pt"/><style:text-properties style:font-name="DejaVuSans" fo:font-size="9pt"/></style:default-style></office:styles>
<office:automatic-styles><style:page-layout style:name="Page"><style:page-layout-properties fo:page-width="{width}px" fo:page-height="{height}px" fo:margin="32px" style:print-orientation="portrait"/></style:page-layout>
{styles}</office:automatic-styles><office:master-styles><style:master-page style:name="Standard" style:page-layout-name="Page"/></office:master-styles>
<office:body><office:text>{body}</office:text></office:body></office:document>'''

def table(path,strings,font,size,phases=None):
    line=2*size;styles=[];body=[]
    for i in range(0,len(strings),4):
        phase=0 if phases is None else phases[i//4]
        name='R'+str(i//4)
        tabs=''.join(f'<style:tab-stop style:position="{x}px" style:type="left"/>' for x in [480,960,1440])
        styles.append(f'<style:style style:name="{name}" style:family="paragraph"><style:paragraph-properties fo:line-height="{line}px" fo:margin-left="{phase}px"><style:tab-stops>{tabs}</style:tab-stops></style:paragraph-properties><style:text-properties style:font-name="{font}" fo:font-size="{size*.75}pt"/></style:style>')
        body.append(f'<text:p text:style-name="{name}">'+('<text:tab/>'.join(escape(s) for s in strings[i:i+4]))+'</text:p>')
    path.write_text(document(''.join(styles),''.join(body),2000,2000))

def forms(path,records,size):
    styles=[];body=[]
    for i,r in enumerate(records):
        name='T'+str(i);margin=max(0,r['margin']-32)
        styles.append(f'<style:style style:name="{name}" style:family="paragraph"><style:paragraph-properties fo:margin-left="{margin}px" fo:line-height="64px"/><style:text-properties style:font-name="{r["font"]}" fo:font-size="{size*.75}pt"/></style:style>')
        header='First' if i==0 else 'Break'
        body.append(f'<text:p text:style-name="{header}">SYNTHETIC GEOMETRY VALIDATION</text:p><text:p>Reconstructed template; case {r["doc"]}; size {size} px.</text:p><text:p>Family name</text:p><text:p text:style-name="{name}">{escape(r["truth"])}</text:p><text:p>End of synthetic field.</text:p>')
    styles.append('<style:style style:name="Break" style:family="paragraph"><style:paragraph-properties fo:break-before="page"/></style:style>')
    path.write_text(document(''.join(styles),''.join(body),816,1056))

def words(page):
    """Read word characters and their actual PDF text origins; no OCR guesses."""
    result=[]
    for block in page.get_text('rawdict')['blocks']:
        if 'lines' not in block:continue
        for line in block['lines']:
            current=[];previous=None
            def flush():
                if current:
                    result.append(dict(text=''.join(c['c'] for c,_,_ in current),origin=current[0][0]['origin'],
                        bbox=[min(c['bbox'][0] for c,_,_ in current),min(c['bbox'][1] for c,_,_ in current),max(c['bbox'][2] for c,_,_ in current),max(c['bbox'][3] for c,_,_ in current)],
                        font=current[0][1],size=current[0][2]))
                    current.clear()
            for span in line['spans']:
                for char in span['chars']:
                    if char['c'].isspace():flush();previous=None;continue
                    if previous is not None and char['bbox'][0]-previous['bbox'][2]>span['size']*.5:flush()
                    current.append((char,span['font'],span['size']));previous=char
            flush()
    return result

def measure(page,item,pixels,glyph=None):
    scale=96/72;box=item['bbox'];h,w=pixels.shape
    x0=max(0,math.floor(box[0]*scale)-4);y0=max(0,math.floor(box[1]*scale)-4)
    x1=min(w,math.ceil(box[2]*scale)+4);y1=min(h,math.ceil(box[3]*scale)+4)
    crop=pixels[y0:y1,x0:x1];ys,xs=np.nonzero(crop<128)
    assert len(xs),'No measured ink'
    assert xs.min()>0 and ys.min()>0 and xs.max()<crop.shape[1]-1 and ys.max()<crop.shape[0]-1,'Ink touches measurement boundary'
    ink=[x0+int(xs.min()),y0+int(ys.min()),x0+int(xs.max())+1,y0+int(ys.max())+1]
    ox,oy=[round(v*scale) for v in item['origin']]
    if glyph is not None:
        glyph.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(pixels[ink[1]:ink[3],ink[0]:ink[2]]).save(glyph)
    return dict(bounds=[ink[0]-ox,ink[1]-oy,ink[2]-ox,ink[3]-oy],pen_x=ox,baseline_y=oy,
                pdf_origin_px=[v*scale for v in item['origin']],pdf_font=item['font'],pdf_font_size_pt=item['size'],
                page_width=w,page_height=h)

def extract(path,expected,forms_mode=False,glyph_dir=None):
    results=[];document=pymupdf.open(path)
    if forms_mode:assert len(document)==len(expected),(path,len(document),len(expected))
    for pageno,page in enumerate(document):
        items=words(page)
        if forms_mode:
            wanted=expected[pageno];items=[x for x in items if x['text']==wanted['truth'] and abs(x['size']-wanted['size']*.75)<.01]
            assert len(items)==1,('Unidentified target',pageno,len(items))
        pix=page.get_pixmap(matrix=pymupdf.Matrix(96/72,96/72),colorspace=pymupdf.csGRAY,alpha=False)
        pixels=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width)
        for item in items:
            idx=len(results);text=expected[pageno]['truth'] if forms_mode else expected[idx]
            assert item['text']==text,('PDF word order mismatch',pageno,idx)
            glyph=None if glyph_dir is None else glyph_dir/(str(idx)+'.png')
            result=measure(page,item,pixels,glyph);result['page']=pageno;results.append(result)
    assert len(results)==len(expected),(path,len(results),len(expected));return results

def main():
    parser=argparse.ArgumentParser();parser.add_argument('work',type=Path);args=parser.parse_args();work=args.work
    plan=json.loads((work/'request.json').read_text());fontdir=work/'pinned-fonts';fontdir.mkdir(exist_ok=True)
    for font,r in plan['fonts'].items():
        source=Path('/fonts')/r['filename'];assert hashlib.sha256(source.read_bytes()).hexdigest()==r['sha256']
        shutil.copyfile(source,fontdir/source.name)
    fc=work/'fontconfig.xml';fc.write_text(f'<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig><dir>{fontdir}</dir><cachedir>{work}/font-cache</cachedir></fontconfig>')
    os.environ['FONTCONFIG_FILE']=str(fc);subprocess.run(['fc-cache','-f'],check=True)
    for font,family in FAMILIES.items():
        selected=subprocess.check_output(['fc-match','-f','%{file}',family],text=True)
        assert hashlib.sha256(Path(selected).read_bytes()).hexdigest()==plan['fonts'][font]['sha256'],('Font substitution',font,selected)
    version=subprocess.check_output(['soffice','--version'],text=True).strip();assert '25.2.3.2' in version
    for sub in ['documents','pdf','measured']: (work/sub).mkdir(exist_ok=True)
    jobs=[]
    for font in FAMILIES:
        for size in [16,24]:
            key=f'{font}_{size}';strings=plan['strings'];cal=plan['calibration'][key]
            for mode,seq in [('bank',strings),('calibration',cal['strings'])]:
                path=work/'documents'/f'{mode}_{key}.fodt';table(path,seq,font,size,None if mode=='bank' else cal['row_phase_px'])
                jobs.append((mode,key,path,seq))
    for size in [16,24]:
        records=[dict(r,size=size) for r in plan['forms']];path=work/'documents'/f'forms_{size}.fodt';forms(path,records,size)
        jobs.append(('forms',str(size),path,records))
    start=time.monotonic();metadata=[]
    for mode,key,path,seq in jobs:
        pdf=work/'pdf'/(path.stem+'.pdf');cache=work/'measured'/(path.stem+'.json')
        fingerprint=hashlib.sha256((path.read_text()+version+Path(__file__).read_text()).encode()).hexdigest()
        if cache.exists() and json.loads(cache.read_text()).get('fingerprint')==fingerprint:
            result=json.loads(cache.read_text());print('Cached',mode,key,flush=True)
        else:
            command=['soffice','-env:UserInstallation=file://'+str(work/'lo-profile'),'--headless','--convert-to','pdf:writer_pdf_Export','--outdir',str(work/'pdf'),str(path)]
            p=subprocess.run(command,text=True,capture_output=True,timeout=1200)
            assert p.returncode==0 and pdf.is_file(),(p.returncode,p.stdout,p.stderr)
            glyphs=None if mode=='bank' else work/'glyphs'/path.stem
            measured=extract(pdf,seq,mode=='forms',glyphs)
            result=dict(fingerprint=fingerprint,mode=mode,key=key,n=len(measured),measurements=measured,
                        pdf_sha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),document_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            cache.write_text(json.dumps(result,separators=(',',':'))+'\n')
            print('Rendered and measured',mode,key,len(measured),'seconds',round(time.monotonic()-start,1),flush=True)
        metadata.append({k:v for k,v in result.items() if k!='measurements'})
    (work/'worker_config.json').write_text(json.dumps(dict(libreoffice=version,pymupdf=pymupdf.VersionBind,jobs=metadata,
        fontconfig='Only the two SHA-256-checked study font files are visible to Fontconfig',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
if __name__=='__main__':main()
