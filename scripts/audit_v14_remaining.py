#!/usr/bin/env python3
"""Record prerequisites, not fabricated experiment results, for pending v1.4 runs."""
import csv,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/v1_4_archive/prerequisites'
EXPECTED='7b8cac46a1c86d2533a616b1fcf4e1926b8e39bda69034508b0df96791f56d97'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    candidates=[]
    # Official candidates already downloaded for hash comparison; no implicit network.
    for p in sorted(Path('/private/tmp').glob('guard-noto-*.ttf')):
        candidates.append(dict(file=p.name,sha256=sha(p),expected_sha256=EXPECTED,matches_pinned=sha(p)==EXPECTED))
    for p in sorted((ROOT/'research/realworld_e1_eval').glob('**/NotoSans*.ttf')):
        if p.is_file():candidates.append(dict(file=str(p.relative_to(ROOT)),sha256=sha(p),expected_sha256=EXPECTED,matches_pinned=sha(p)==EXPECTED))
    write(OUT/'font_candidates.csv',candidates)
    available=any(r['matches_pinned'] for r in candidates)
    # Do not assert missing outside the locations actually audited.
    rows=[
      dict(item='email_digits_sweep',status='prerequisite_available' if available else 'blocked',reason='Fresh six-font rendering requires pinned Noto Sans; surname geometry cannot substitute for email/digit geometry.'),
      dict(item='noto_fresh_rerender',status='prerequisite_available' if available else 'blocked',reason='No checked binary matches fonts.json; retained geometry is not a fresh render.'),
      dict(item='mock_form_renderer_mismatch',status='not_run',reason='Repository has replayed geometry/hit CSVs, but no original LibreOffice mock-form document/PDF/scan input set or end-to-end form generator.'),
      dict(item='rerender_188_and_2',status='not_run',reason='Archived counts exist, but the mixed-font rerender generator, same-target mapping and per-render settings needed to rerun those specific 2000 targets are absent from released code.'),
      dict(item='tileseal_392',status='blocked' if not available else 'not_run',reason='e1_validate_guard.py requires all six pinned fonts via E.check_render_inputs; no replacement and no claimed 392-case rerun.'),
      dict(item='alternative_font_builds_36_cells',status='not_run',reason='Original alternative-build manifest and 36-cell experiment harness are not in released code; do not choose different builds and label them a reproduction.'),
      dict(item='v931_figure_script',status='available' if (ROOT/'manuscript/figures/make_figs_v931.py').is_file() else 'blocked',reason='User-supplied make_figs_v931.py absent from repository, accessible filename search, Git history and attached Python files.'),
      dict(item='final_v14_release_check',status='blocked',reason='New experiment coverage and v931 figure checks are incomplete; current expected_numbers.json has no v1_4 section. Do not create v1.4-artifact.')]
    write(OUT/'summary.csv',rows)
    config=dict(status='incomplete',experiment_results=False,seed=20261121,bootstrap_resamples=10000,
      command='.venv/bin/python -B scripts/audit_v14_remaining.py',python=sys.version,
      pinned_noto_sha256=EXPECTED,font_sources=[
       'https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/NotoSans%5Bwdth,wght%5D.ttf',
       'https://api.github.com/repos/google/fonts/commits?path=ofl/notosans/NotoSans%5Bwdth,wght%5D.ttf&per_page=100',
       'https://raw.githubusercontent.com/notofonts/noto-fonts/main/unhinted/variable-ttf/NotoSans-VF.ttf'],
      google_fonts_commits_checked=['ab3683d56ecc64a4d3eee573f7671791e0eb077b','62c17bc045b0f8317386c1c55464125bbb7a96ef','81a94f4d3d09c8be8669faaa9a8c7f622e21d931','c92b209a838649c205a1565b5f28c1973e049659'],
      local_search='Filename search across /Users/neervasa plus /Library/Fonts and /System/Library/Fonts; 352 matching font/script names; some folders denied by macOS privacy even after escalation. No v931 script found in accessible locations.',
      remote_figure_search='GitHub connector fetch of manuscript/figures/make_figs_v931.py on the default branch returned 404; filename search returned no results.',
      git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      protected_v13=subprocess.check_output(['git','rev-parse','v1.3-artifact^{commit}'],cwd=ROOT,text=True).strip(),
      protected_tileseal=subprocess.check_output(['git','rev-parse','f8f2558'],cwd=ROOT,text=True).strip(),
      libreoffice_version=subprocess.check_output(['/Users/neervasa/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice','--version'],text=True).strip(),
      source_sha256=sha(Path(__file__)))
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    text='# Remaining v1.4 prerequisite audit\n\nThis is an inventory, not an experimental rerun. No missing performance number is filled in. The anchor-margin experiment is complete at data/v1_5_anchor_margin; prior available-font and FUNSD-only OCR runs retain their documented limits.\n\n'
    text+='The pinned Noto binary was not found among accessible local candidates or six official current/historical builds. The supplied Figure v9.31 script was not found in accessible files or Git history. Searches were limited by macOS privacy denials in some folders. No substitute font or figure script was used.\n\n'
    search=OUT/'local_font_hash_search.json'
    if search.is_file():
        info=json.loads(search.read_text())
        text+=f'The broader name-independent search hashed {info["fonts_hashed"]} local TTF/OTF files in accessible roots, including renamed fonts, and found {len(info["matching_files"])} pinned-hash matches. GitHub default-branch fetch of the v931 script returned 404 and filename search returned no results.\n\n'
    text+='| Item | Status | Reason |\n|---|---|---|\n'
    text+='\n'.join(f'| {r["item"]} | {r["status"]} | {r["reason"]} |' for r in rows)+'\n\n'
    text+='The user protocol says to stop when prerequisites are unavailable. Fresh six-font email/digit and archive experiments have not been represented as completed. LibreOffice is installed, but its availability alone does not supply the missing original mock forms. No new tag or push is authorized by this audit.\n'
    legacy=OUT/'legacy_make_all.json'
    if legacy.is_file():
        check=json.loads(legacy.read_text())
        text+='\nExisting locked-manuscript baseline check in a clean local clone of '+check['clone_commit']+': exit '+str(check['returncode'])+'; '+ '; '.join(check['output_summary'])+'. This checks the existing v9.4 expectations, not the missing v9.31 figures or new v1.4-number integration. See legacy_make_all.json and legacy_make_all.log.\n'
    (OUT/'README.md').write_text(text)
    print('\n'.join(f'{r["item"]}: {r["status"]}' for r in rows))
if __name__=='__main__':main()
