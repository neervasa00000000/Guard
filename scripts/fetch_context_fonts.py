#!/usr/bin/env python3
"""Restore exact, manifest-pinned context fonts from public or supplied archives."""
import argparse,hashlib,io,json,subprocess,tarfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive-dir',type=Path,required=True)
    parser.add_argument('--download',action='store_true');args=parser.parse_args()
    manifest=json.loads((ROOT/'results/reruns/context_font_sources/manifest.json').read_text())
    args.archive_dir.mkdir(parents=True,exist_ok=True);missing=[]
    for asset in manifest['assets']:
        path=args.archive_dir/asset['archive_filename']
        if not path.is_file() and args.download and asset['url']:
            subprocess.run(['curl','--fail','--location','--proto','=https','--tlsv1.2',asset['url'],'--output',str(path)],check=True)
        if not path.is_file():missing.append(str(path));continue
        data=path.read_bytes();assert sha(data)==asset['archive_sha256'],path
        if path.suffix=='.zip':
            with zipfile.ZipFile(io.BytesIO(data)) as z:payloads={f['member']:z.read(f['member']) for f in asset['files']}
        else:
            if path.suffix=='.deb':
                member=next(n for n in subprocess.check_output(['ar','t',str(path)],text=True).splitlines() if n.startswith('data.tar'))
                data=subprocess.check_output(['ar','p',str(path),member])
            with tarfile.open(fileobj=io.BytesIO(data),mode='r:*') as t:
                payloads={f['member']:t.extractfile(f['member']).read() for f in asset['files']}
        for f in asset['files']:
            target=(ROOT/f['path']).resolve()
            assert target.is_relative_to(ROOT/'research/realworld_e1_eval/fonts/context')
            body=payloads[f['member']];assert sha(body)==f['sha256']
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():assert sha(target.read_bytes())==f['sha256'],target
            else:target.write_bytes(body)
        print('Verified',asset['archive_filename'],len(asset['files']),'members')
    if missing:raise SystemExit('Unavailable original archives (not substituted): '+', '.join(missing))
if __name__=='__main__':main()
