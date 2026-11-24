#!/usr/bin/env python3
"""Independent audit of completed font-matched outputs; does not render or read document text."""
import csv
import gzip
import hashlib
import json
import math
import importlib.metadata
import subprocess
from collections import defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'results/font_matched'

def read(path):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'rt',newline='') as f:return list(csv.DictReader(f))

def main():
    config=json.loads((OUT/'config.json').read_text());assert config['status']=='complete_available_font_subset'
    rows=read(OUT/'per_token.csv.gz');summary=read(OUT/'summary.csv')
    assert len(summary)==24
    assert not ({'text','token','surface','string'}&set(rows[0]))
    assert all(len(r['token_sha256'])==64 and int(r['token_char_length'])>0 for r in rows)
    seen=set();groups=defaultdict(list)
    for r in rows:
        key=(r['attacker'],r['policy'],r['token_id']);assert key not in seen;seen.add(key)
        groups[(r['attacker'],r['policy'])].append(r)
        for k in ['truth_in','top1','top10']:assert 0<=float(r[k])<=1
        assert int(r['candidate_count'])>=0
        if r['policy'] in ['nobox','field-1000']:assert abs(float(r['bits']))<1e-9
    for policy in config['policies']:
        sets=[{r['token_id'] for r in groups[(arm,policy)]} for arm in config['attackers']]
        assert all(s==sets[0] for s in sets),'Attackers use different cohorts'
    for s in summary:
        rs=groups[(s['attacker'],s['policy'])];assert len(rs)==int(s['n_tokens'])
        for key in ['truth_in','top1','top10','bits']:
            mean=math.fsum(float(r[key]) for r in rs)/len(rs)
            assert math.isclose(mean,float(s[key]),abs_tol=1e-11),(s['attacker'],s['policy'],key)
            assert math.isfinite(float(s[key+'_lo'])) and math.isfinite(float(s[key+'_hi']))
            assert float(s[key+'_lo'])<=float(s[key+'_hi'])
        assert int(s['tolerance_px'])==config['tolerances_px'][s['attacker']]
        assert float(s['calib_truth_in'])>=.95
    original={(r['token_id'],r['policy']):r for r in read(HERE/'results/generic_attacker/per_token_notext.csv') if r['dataset']=='DocLayNet'}
    for r in rows:
        if r['attacker']=='generic':
            o=original[(r['token_id'],r['policy'])]
            assert r['token_sha256']==o['token_sha256']
            for new,old in [('truth_in','truth_in'),('top1','hit1'),('top10','hit10'),('bits','bits')]:
                assert float(r[new])==float(o[old]),'Generic baseline changed'
    cal=read(OUT/'calibration.csv.gz')
    for arm in config['attackers'][:-1]:
        rs=[r for r in cal if r['attacker']==arm];t=config['tolerances_px'][arm]
        values=[int(r['min_tolerance_px']) for r in rs]
        assert len(values)==config['n_calibration']
        assert sum(x<=t for x in values)/len(values)>=.95
        assert t==0 or sum(x<=t-1 for x in values)/len(values)<.95
    ev=read(OUT/'evaluation_renderable_cohort.csv.gz');cv=read(OUT/'calibration_renderable_cohort.csv.gz')
    assert not ({r['page_id'] for r in ev}&{r['page_id'] for r in cv})
    assert len(ev)==config['n_evaluation'] and len(cv)==config['n_calibration']
    with (HERE/'results/generic_attacker/calibration_pages.json').open() as f:splits=json.load(f)
    assert {r['page_id'] for r in cv}<=set(splits['doclaynet'])
    for p,expected in config['inputs_sha256'].items():
        with (ROOT/p).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==expected
    expected_tag='18cfe521088c90750ba6bc627fbd1bbe10072fab'
    actual_tag=subprocess.run(['git','rev-parse',expected_tag+'^{commit}'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    assert actual_tag==expected_tag
    config['numpy']=importlib.metadata.version('numpy')
    config['source_artifact_commit']=expected_tag
    with Path(__file__).open('rb') as f:config['validation_script_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
    (OUT/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    # Grid widening must not remove a true candidate in this horizontal model.
    for arm in config['attackers']:
        g={p:{r['token_id']:float(r['truth_in']) for r in groups[(arm,p)]} for p in ['exact','grid-16','grid-64']}
        for token in g['exact']:assert g['exact'][token]<=g['grid-16'][token]<=g['grid-64'][token]
    report=dict(passed=True,summary_rows=len(summary),per_target_policy_rows=len(rows),evaluation_targets=len(ev),
                calibration_targets=len(cv),generic_matches_generic_run=True,paired_cohorts=True,
                evaluation_pages=len({r['page_id'] for r in ev}),calibration_pages=len({r['page_id'] for r in cv}),
                calibration_evaluation_pages_disjoint=True,tolerances_minimal_at_95_percent=True,
                point_estimates_recomputed=True,no_document_text_columns=True,source_hashes_unchanged=True)
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# Available-font attacker comparison','',
        'All numbers below come from this run’s summary.csv. This is the user-authorized available-font subset, with additional explicit exclusions where no independent context geometry exists or the pinned renderer fails. It is not a full-cohort replication.','',
        'The font-known arm uses neighbour font metadata and a locally available matching font name. Matching a font name does not establish equality of source font binaries/builds. Point sizes are converted to horizontal page pixels using page metadata. The renderer-mismatch arm uses Pillow BASIC instead of RAQM.','',
        'The font-estimated arm is one explicitly specified **anonymous-geometry baseline**, not an optimal font-recognition attack: it uses no visible word identities, character counts, pixels or font names. It compares width/height quantiles with 512 fixed prior-weighted Census probes per candidate font/size. Source context cells can contain several words, so the probe width distribution can be misspecified. Accuracy is strict equality to the neighbour modal font identity; true identities outside the regular six-font bank count incorrect.','',
        'All six study fonts, including the recovered hash-matched Noto Sans binary, are rendered at the fixed sizes and the observed context size. Native context fonts are matched by embedded identity, including Type 1 fonts where available; this does not verify equality to the document’s original font build. The generic arm is unchanged generic-attacker per-token scoring on the same paired tokens, with its original pooled calibration tolerance.','',
        'Each other arm uses the original held-out page split, restricted to common usable DocLayNet calibration targets. FUNSD supplies no font metadata. Tolerances are the smallest integer symmetric edge slack reaching 95% exact-box truth-in, then frozen across policies. Padding and empty-set fallback retain the generic-attacker feasibility/scoring convention. CIs are 10,000 page-cluster percentile draws, seed 20261121.','',
        'The first-1000 field row includes only targets in that bounded list and uses its renormalized prior, as generic-attacker does; its n and prior differ from the full-list rows.','',
        '| Attacker | Policy | n | Tolerance px | Calib truth-in % | Truth-in % [95% CI] | Top-1 % [95% CI] | Top-10 % [95% CI] | Attacker performance (bits) [95% CI] |',
        '|---|---|---:|---:|---:|---|---|---|---|']
    for s in summary:
        cells=[s['attacker'],s['policy'],s['n_tokens'],s['tolerance_px'],f"{100*float(s['calib_truth_in']):.2f}"]
        for key in ['truth_in','top1','top10','bits']:
            factor=1 if key=='bits' else 100
            cells.append(f"{factor*float(s[key]):.3f} [{factor*float(s[key+'_lo']):.3f}, {factor*float(s[key+'_hi']):.3f}]")
        lines.append('| '+' | '.join(cells)+' |')
    acc=config['estimator_accuracy']
    old=read(HERE/'results/font_consistency/attacker_per_token_notext.csv')
    overlap=len({r['token_id'] for r in old}&{r['token_id'] for r in ev})
    lines+=['',f"Strict neighbour-font estimate accuracy: {100*acc['neighbour']:.3f}%; target-font accuracy: {100*acc['target']:.3f}%. Only {acc['exact_true_neighbour_in_regular_bank']} evaluated neighbour font identities are in the regular six-font bank.",
            '',f"The expanded cohort includes {overlap} of the preliminary test's {len(old)} tokens. It uses a new calibrated tolerance and cohort, so its bits are not a direct replacement for the old 66-token estimate.",
            '',f"Evaluation targets: {len(ev)}; calibration targets: {len(cv)}. Full exclusion counts and native font provenance are in config.json; failed font-size cells are in render_failures.csv; omitted targets are in excluded.csv.gz and render_excluded.csv.gz.",
            '', 'No old result files, source fonts, page images or document text were changed or redistributed. Validation recomputes all point estimates, verifies exact generic replay, common cohorts, source hashes, split separation and minimal calibration tolerances.','']
    (OUT/'README.md').write_text('\n'.join(lines))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
