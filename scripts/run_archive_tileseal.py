#!/usr/bin/env python3
"""Rerun the original 100-image/392-redaction TileSeal check, hash-only output."""
from __future__ import annotations
import ast,contextlib,io,json,os,subprocess,sys,time
from pathlib import Path
from v14_runtime import ROOT,E,renderer,read,write,digest,text_hash
PIN='f8f2558a5f82bb99842781a0e3bc03fec39fd3c5'
ORIGINAL='733d48a'
def cells(rects):
    result=set()
    for x,y,w,h in rects:
        assert x%8==y%8==w%8==h%8==0
        result.update((xx,yy,8,8) for yy in range(y,y+h,8) for xx in range(x,x+w,8))
    return json.dumps(sorted(result),separators=(',',':'))
def predicted(box):
    x0,x1,y0,y1=box
    return cells([(x0,y0,x1-x0,y1-y0)])
def main():
    out=ROOT/'results/v1_4_archive/tileseal';out.mkdir(parents=True,exist_ok=True)
    work=ROOT/'out/v14-tileseal';work.mkdir(parents=True,exist_ok=True)
    checkout=ROOT/'out/tileseal-f8f2558-readonly'
    if not checkout.exists():
        subprocess.run(['git','clone','--quiet','--no-hardlinks','--no-checkout',str(ROOT),str(checkout)],check=True)
        subprocess.run(['git','-C',str(checkout),'checkout','--quiet','--detach',PIN],check=True)
        for p in checkout.rglob('*'):
            if p.is_file():p.chmod(p.stat().st_mode&~0o222)
        checkout.chmod(checkout.stat().st_mode&~0o222)
    assert subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()==PIN
    assert not subprocess.check_output(['git','-C',str(checkout),'status','--porcelain'],text=True)
    versions=renderer();os.environ['E1_GUARD']=str(checkout);E.RUN_ROOT=work;E.CACHE=work/'cache'
    source=ROOT/'research/e1/scripts/e1_validate_guard.py';tree=ast.parse(source.read_text(),filename=str(source))
    # Instrument output fields only: original sample, rendering, seal/redact/verify
    # calculations execute unchanged. No private key is serialized.
    class Output(ast.NodeTransformer):
        def visit_Call(self,node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='rows' and node.func.attr=='append':
                row=node.args[0];assert isinstance(row,ast.Call)
                row.keywords=[k for k in row.keywords if k.arg!='target']
                for name,expr in [('target_sha256','_hash(s)'),('target_char_length','len(s)'),
                    ('predicted_tiles','_predicted(mb)'),('sealed_tiles',"_cells([(e['x'],e['y'],e['width'],e['height']) for e in rm])")]:
                    row.keywords.append(ast.keyword(arg=name,value=ast.parse(expr,mode='eval').body))
            if isinstance(node.func,ast.Name) and node.func.id=='print' and any(isinstance(a,ast.Name) and a.id=='s' for a in node.args):
                node.args=[ast.Constant('[hashed target]') if isinstance(a,ast.Name) and a.id=='s' else a for a in node.args]
            return node
    tree=ast.fix_missing_locations(Output().visit(tree));oldargv=sys.argv;sys.argv=[str(source),'100'];log=io.StringIO();start=time.monotonic()
    try:
        with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            exec(compile(tree,str(source),'exec'),dict(__file__=str(source),__name__='__main__',_hash=text_hash,_cells=cells,_predicted=predicted))
    finally:sys.argv=oldargv
    (out/'run.log').write_text(log.getvalue())
    rows=read(work/'csv/e1_validation.csv');assert len(rows)==392
    import csv
    archived=list(csv.DictReader(io.StringIO(subprocess.check_output(['git','show',ORIGINAL+':research/e1/csv/e1_validation.csv'],cwd=ROOT,text=True))))
    old={r['case_id']:r for r in archived};assert set(old)=={r['case_id'] for r in rows}
    for r in rows:
        original=old[r['case_id']]
        for key in ['dict','font','size_px','variant','grid_px','tight_box','model_box','guard_box']:
            assert r[key]==original[key],('Original case differs',r['case_id'],key)
        assert r['target_sha256']==text_hash(original['target'])
        r['tile_sets_match']=r['predicted_tiles']==r['sealed_tiles']
        r['n_predicted_tiles']=len(json.loads(r['predicted_tiles']));r['n_sealed_tiles']=len(json.loads(r['sealed_tiles']))
        assert r['tile_sets_match'] and r['match']=='True'
    write(out/'raw.csv.gz',rows)
    summary=[]
    for g in [8,16,32,64]:
        rs=[r for r in rows if int(r['grid_px'])==g]
        summary.append(dict(grid_px=g,n_redactions=len(rs),matching=sum(r['tile_sets_match'] for r in rs),mismatching=sum(not r['tile_sets_match'] for r in rs),archived_case_matches=len(rs)))
    write(out/'summary.csv',summary)
    assert not subprocess.check_output(['git','-C',str(checkout),'status','--porcelain'],text=True)
    config=dict(status='complete',command='research/realworld_e1_eval/.venv/bin/python -B scripts/run_archive_tileseal.py',
        seed=20261030,guard_commit=PIN,guard_checkout_read_only=True,versions=versions,
        source_script_sha256=digest(source),wrapper_sha256=digest(__file__),archived_rows_commit=ORIGINAL,
        n_generated_images=100,n_accepted_images=98,n_skipped_images=2,n_redactions=392,n_matching=392,
        tile_representation='Both predicted rectangles and actual verify_v2 redactionMap expanded into canonical 8px cells; full tile coordinates archived',
        instrumentation='Only output fields and target-containing progress prints changed in memory; original calculations unchanged',
        key='fresh ephemeral Ed25519 key in memory, discarded; no private key written',elapsed_seconds=time.monotonic()-start)
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'README.md').write_text('# TileSeal 392-redaction rerun\n\nThe existing validator was rerun for its original 100 seeded image attempts, with the same six pinned fonts. Two out-of-page attempts are skipped, leaving 98 images × four grids = 392 redactions. All case IDs, target hashes and box coordinates match the original per-redaction archive recovered read-only from commit 733d48a. All 392 predicted and actual sealed tile sets match.\n\nTileSeal f8f2558 was checked out separately and made read-only; its checkout remained clean. Output-only instrumentation hashes targets and records actual redaction-map cells; no calculation was changed. The signing key exists only in memory and is discarded. No images, names, private keys or raw dataset files are distributed. Run and renderer details are in config.json.\n')
    print('TileSeal rerun: 392/392 actual tile sets match; original cases reproduced',flush=True)
if __name__=='__main__':main()
