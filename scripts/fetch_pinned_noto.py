#!/usr/bin/env python3
"""Obtain only the exact manifest-pinned Noto Sans build; never substitute."""
import json,subprocess
from pathlib import Path
from v14_runtime import ROOT,digest
SHA='7b8cac46a1c86d2533a616b1fcf4e1926b8e39bda69034508b0df96791f56d97'
URL='https://raw.githubusercontent.com/LostRunes/pyq_app/307e168ae16c380d4357780b9573708e24b5db5a/NotoSans-VariableFont_wdth%2Cwght.ttf'
def main():
    p=ROOT/'research/realworld_e1_eval/fonts/NotoSans-VariableFont_wdth,wght.ttf'
    if not p.exists():
        data=subprocess.check_output(['curl','--fail','--location','--silent','--show-error','--max-time','60',URL])
        import hashlib
        assert hashlib.sha256(data).hexdigest()==SHA,'Pinned Noto download mismatch; do not substitute'
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    assert digest(p)==SHA,'Existing Noto file differs from manifest; not replaced'
    out=ROOT/'results/v1_4_archive/noto_source';out.mkdir(parents=True,exist_ok=True)
    config=dict(status='exact_hash_verified',sha256=SHA,url=URL,
        source_commit='307e168ae16c380d4357780b9573708e24b5db5a',font_name='Noto Sans Regular',font_version='2.015',
        license='SIL Open Font License 1.1; verified from embedded name records 13 and 14',license_url='https://openfontlicense.org',
        local_path=str(p.relative_to(ROOT)),redistributed=False,command='research/realworld_e1_eval/.venv/bin/python -B scripts/fetch_pinned_noto.py')
    (out/'config.json').write_text(json.dumps(config,indent=2)+'\n');print(json.dumps(config,indent=2))
if __name__=='__main__':main()
