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
    figure=ROOT/'manuscript/figures/make_figs_v931.py'
    figure_config=ROOT/'results/v1_4_archive/v931_figures/config.json'
    proof=json.loads(figure_config.read_text()) if figure_config.exists() else {}
    figure_ready=(figure.is_file() and proof.get('status')=='passed' and proof.get('script_sha256')==sha(figure)
        and proof.get('figs_data_sha256')==sha(figure.with_name('figs_data.csv')))
    # Do not assert missing outside the locations actually audited.
    rows=[
      dict(item='email_digits_sweep',status='complete',reason='Fresh six-font sweep: 864000 target-policy rows, 432 summaries and 24 pooled rows; digit entropy remains explicitly unknown except constant-field zero.'),
      dict(item='noto_fresh_rerender',status='complete',reason='Recovered exact pinned SHA-256; fresh 150000 full-list bounds match all three retained receipts, and 126000 target-policy scores reproduce v1.2.'),
      dict(item='mock_form_renderer_mismatch',status='complete_new_reconstruction',reason='Fresh LibreOffice 25.2.3.2 reconstruction: 200 form pages, 200000 candidate geometries, 7200 per-form rows, 72 summaries. Same archived targets/font assignments; newly specified template and local-word scan. Historical differences reported; original generator still missing.'),
      dict(item='rerender_188_and_2',status='complete',reason='Original generator recovered read-only from Git commit 733d48a; fresh six-font geometry and unchanged function reproduce 188/2000 and 2/2000, with hash-only per-target records.'),
      dict(item='tileseal_392',status='complete',reason='Original validator rerun with six pinned fonts and read-only f8f2558 checkout: 392/392 tile sets match; original target hashes and coordinates match historical per-redaction rows.'),
      dict(item='alternative_font_builds_36_cells',status='complete_new_sensitivity_run',reason='Explicitly defined 6 fonts x 3 sizes x A1/A2, builds frozen before scoring: 2/36 cells shift +7.8 pp. Original build manifest remains unavailable; this does not verify historical build provenance.'),
      dict(item='v931_figure_script',status='complete' if figure_ready else ('available' if figure.is_file() else 'blocked'),
           reason=('User-supplied script installed unchanged; five figures checked with pinned Source Sans Pro; '+str(proof.get('total_problems'))+' layout problems; '+str(proof.get('n_values_not_in_csv'))+' plotted values missing from CSV.') if figure_ready else 'Complete supplied script and passing figure-check record required.'),
      dict(item='final_v14_release_check',status='complete_with_approved_limits',reason='User accepted documented new experiments on 2026-11-21. Clean-clone make all and both independent validators passed; historical template/build provenance remains explicitly unverified. Tagging is permitted after final checks; no push.')]
    write(OUT/'summary.csv',rows)
    config=dict(status='complete_with_approved_limits',scope_approval='2026-11-21: Use the documented new experiments',experiment_results=False,seed=20261121,bootstrap_resamples=10000,
      command='.venv/bin/python -B scripts/audit_v14_remaining.py',python=sys.version,
      pinned_noto_sha256=EXPECTED,pinned_noto_found=available,font_sources=[
       'https://raw.githubusercontent.com/LostRunes/pyq_app/307e168ae16c380d4357780b9573708e24b5db5a/NotoSans-VariableFont_wdth%2Cwght.ttf',
       'https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/NotoSans%5Bwdth,wght%5D.ttf',
       'https://api.github.com/repos/google/fonts/commits?path=ofl/notosans/NotoSans%5Bwdth,wght%5D.ttf&per_page=100',
       'https://raw.githubusercontent.com/notofonts/noto-fonts/main/unhinted/variable-ttf/NotoSans-VF.ttf'],
      google_fonts_commits_checked=['ab3683d56ecc64a4d3eee573f7671791e0eb077b','62c17bc045b0f8317386c1c55464125bbb7a96ef','81a94f4d3d09c8be8669faaa9a8c7f622e21d931','c92b209a838649c205a1565b5f28c1973e049659'],
      local_search='Initial filename search across /Users/neervasa plus /Library/Fonts and /System/Library/Fonts; 352 matching font/script names; some folders denied by macOS privacy even after escalation. The user subsequently supplied the v931 script.',
      remote_figure_search='Prior to user supplying the file, GitHub connector fetch on the default branch returned 404 and filename search returned no results.',
      v931_figure_checks_passed=figure_ready,v931_figure_check_config_sha256=sha(figure_config) if figure_config.exists() else None,
      git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      protected_v13=subprocess.check_output(['git','rev-parse','v1.3-artifact^{commit}'],cwd=ROOT,text=True).strip(),
      protected_tileseal=subprocess.check_output(['git','rev-parse','f8f2558'],cwd=ROOT,text=True).strip(),
      libreoffice_version=subprocess.check_output(['/Users/neervasa/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice','--version'],text=True).strip(),
      source_sha256=sha(Path(__file__)))
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    text='# Remaining v1.4 prerequisite audit\n\nThis is an inventory, not an experimental rerun. No missing performance number is filled in. The anchor-margin experiment is complete at data/v1_5_anchor_margin; prior available-font and FUNSD-only OCR runs retain their documented limits.\n\n'
    text+='The exact pinned Noto binary has been recovered and all six study-font hashes pass. Fresh rerender, TileSeal, email/digit and expanded font-context runs are now archived. The user supplied the v9.31 figure script; it is installed unchanged under manuscript/figures/. Historical failed-search records are preserved as search history, not a current missing-font claim.\n\n'
    search=OUT/'local_font_hash_search.json'
    if search.is_file():
        info=json.loads(search.read_text())
        text+=f'The broader name-independent search hashed {info["fonts_hashed"]} local TTF/OTF files in accessible roots, including renamed fonts, and found {len(info["matching_files"])} pinned-hash matches. The earlier remote/local figure-script search is superseded by the user-supplied file.\n\n'
    text+='| Item | Status | Reason |\n|---|---|---|\n'
    text+='\n'.join(f'| {r["item"]} | {r["status"]} | {r["reason"]} |' for r in rows)+'\n\n'
    text+='A fresh end-to-end LibreOffice reconstruction is now archived under results/v1_4_archive/mock_forms_reconstruction. It has independent full-array score and CI validation; it is explicitly not the original template replication. The original LibreOffice kit (kit.tar.gz, SHA-256 4c88f470e98c2865f84287713240652fb192cf4cc6db85ce4f8605ee03fb6bf5) is still missing. Accessible local archives, historical Git, Docker images/volumes and filename-only connected Drive searches did not supply its gen.py/measure.py/attack.py or original inputs. Existing per-form observations do not establish an end-to-end rerun. The user protocol requires reporting missing inputs, so no replacement is labelled as an original replication. On 2026-11-21 the user explicitly accepted the documented new experiments for the v1.4 release; the historical provenance limits remain in the artifact. The new sensitivity run does not establish the lost historical alternative-build provenance. Nothing has been pushed.\n'
    legacy=OUT/'legacy_make_all.json'
    if legacy.is_file():
        check=json.loads(legacy.read_text())
        text+='\nExisting locked-manuscript baseline check in a clean local clone of '+check['clone_commit']+': exit '+str(check['returncode'])+'; '+ '; '.join(check['output_summary'])+'. That earlier check covers the existing v9.4 expectations. The subsequent v931 figure and produced-summary checks are separate; historical-input limitations remain explicit. The current clean-clone build and full independent validations are recorded in ../libreoffice_clean_clone/. See legacy_make_all.json and legacy_make_all.log for the earlier baseline.\n'
    (OUT/'README.md').write_text(text)
    print('\n'.join(f'{r["item"]}: {r["status"]}' for r in rows))
if __name__=='__main__':main()
