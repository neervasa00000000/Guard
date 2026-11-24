#!/usr/bin/env python3
"""Build the supplied paper figures with pinned fonts and enforce its checks."""
from __future__ import annotations
import argparse,contextlib,csv,hashlib,io,json,os,re,runpy,shlex,shutil,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMIT='ce77773581f4d454f0fa985c073bb25c721bfcf5'
FONTS={'Regular':'774614c463f3c9bd6a3707e59eeb7c85c0753267ba2fd5105f8751c54b74b102',
       'Bold':'294f0a2c1caa4c543ca67f5a88cc0474a471a247214b1fdde0257a018f596a84'}
FIGURES={'fig2_leakage_area':'fig2','fig3_same_knowledge':'fig3','fig4_pointwise':'fig4',
         'fig5_realworld':'fig6','figA1_releases':'fig5'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font-dir',type=Path,default=ROOT/'out/fonts/source-sans-pro-2.045')
    parser.add_argument('--out',type=Path,default=ROOT/'out/figure_check')
    args=parser.parse_args();args.font_dir.mkdir(parents=True,exist_ok=True);args.out.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'out/matplotlib-cache';cache.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(cache))
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager as fm,ft2font
    # Avoid choosing a different installed build with the same family name.
    fm.fontManager.ttflist=[f for f in fm.fontManager.ttflist if f.name!='Source Sans Pro']
    fonts=[]
    for face,expected in FONTS.items():
        filename=f'SourceSansPro-{face}.otf';path=args.font_dir/filename
        url=f'https://raw.githubusercontent.com/adobe-fonts/source-sans/{COMMIT}/OTF/{filename}'
        if not path.exists():
            print('Downloading pinned figure font:',filename,flush=True)
            if curl:=shutil.which('curl'):
                # Use the OS trust store on macOS Python framework installs;
                # TLS verification stays enabled and content is hash checked.
                data=subprocess.check_output([curl,'--fail','--location','--silent','--show-error','--max-time','45',url])
            else:
                with urllib.request.urlopen(url,timeout=45) as response:data=response.read()
            if hashlib.sha256(data).hexdigest()!=expected:raise RuntimeError('Downloaded figure-font hash mismatch: '+filename)
            path.write_bytes(data)
        if sha(path)!=expected:raise RuntimeError('Figure-font hash mismatch: '+str(path))
        fm.fontManager.addfont(str(path))
        fonts.append(dict(face=face,sha256=expected,url=url))
    source=ROOT/'manuscript/figures/make_figures.py';data=source.with_name('figs_data.csv')
    captured=io.StringIO()
    with contextlib.redirect_stdout(captured),contextlib.redirect_stderr(captured):
        namespace=runpy.run_path(str(source),run_name='__main__')
    log=captured.getvalue();print(log,end='')
    (args.out/'run.log').write_text(log)
    plotted=namespace['PLOTTED'];values={}
    for r in namespace['rows']:
        for key in ('x','y'):
            try:values.setdefault(r['figure'],set()).add(round(float(r[key]),4))
            except (ValueError,TypeError):pass
    bad=[p for p in plotted if p[2] is not None and round(p[2],4) not in values.get(p[0][:4],set())]
    statuses={m[0]:(0 if m[1]=='OK' else int(m[2])) for m in re.findall(r'^(fig\S+): (OK|(\d+) problems)$',log,re.M)}
    summary=[dict(figure=figure,layout_problems=statuses.get(figure,''),
        n_plotted_values=sum(p[0][:4]==group for p in plotted),
        n_values_not_in_csv=sum(p[0][:4]==group for p in bad)) for figure,group in FIGURES.items()]
    write(args.out/'summary.csv',summary)
    write(args.out/'raw.csv',[dict(source_figure=p[0],label=p[1],value=p[2]) for p in plotted])
    passed=(set(statuses)==set(FIGURES) and namespace['total']==0 and not bad and namespace['FONT']=='Source Sans Pro')
    outputs={p.name:sha(p) for name in FIGURES for p in [source.with_name(name+'.png')]}
    outputs['contact_sheet.png']=sha(source.with_name('contact_sheet.png'))
    config=dict(status='passed' if passed else 'failed',command=shlex.join(['python3','scripts/check_figures.py',*sys.argv[1:]]),randomness='none',
        python=sys.version,matplotlib=matplotlib.__version__,freetype=ft2font.__freetype_version__,
        font=namespace['FONT'],fonts=fonts,script_sha256=sha(source),figs_data_sha256=sha(data),
        checker_sha256=sha(Path(__file__)),total_problems=int(namespace['total']),
        n_plotted_values=len(plotted),n_values_not_in_csv=len(bad),outputs_png_sha256=outputs,
        provenance='Supplied make_figures.py is unchanged; fonts from official Adobe release 2.045R-ro/1.095R-it; no images or font binaries distributed.')
    (args.out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    verdict=('All five figures have zero reported layout problems; '+str(len(plotted))+' plotted values match the source CSV.') if passed else 'The checks failed; see run.log and summary.csv.'
    (args.out/'README.md').write_text('# paper figure checks\n\nThe supplied script draws Figures 2–5 and A1 from the existing figs_data.csv. Its content is unchanged. '+verdict+' The contact sheet was visually inspected during initial integration; changed inputs or renderer versions need renewed visual review.\n\nRun `make figures PY=python3` from the repository root, or `python3 scripts/check_figures.py`. The first run downloads Source Sans Pro Regular and Bold from the pinned official Adobe commit, verifies SHA-256, and caches them under ignored out/fonts/. Later runs use that cache. Network access is needed only when those font files are absent. No document text or images are uploaded.\n\nSource Sans Pro is required for these five-inch layouts; the DejaVu fallback produced 24 layout problems in the initial check. The checked font builds and renderer versions are in config.json. Font binaries, generated PNG/PDF files and the contact sheet are excluded from Git. raw.csv records the plotted numerical values; run.log and summary.csv record the supplied checks. These figure checks do not reproduce the remaining blocked experiments.\n')
    if not passed:raise SystemExit('paper figure checks failed; inspect out/figure_check/run.log')
if __name__=='__main__':main()
