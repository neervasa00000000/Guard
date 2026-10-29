#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create empty v4 measurement templates. Never invent trials or overwrite results."""
import csv
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'results/realworld';root.mkdir(parents=True,exist_ok=True)
schemas={
'realworld_open':'date,device,os_version,app,app_version,carrier,opens_as_picture,looks_correct,guard_verdict,guard_exit_or_banner,notes',
'realworld_share':'date,channel,send_mode,carrier,sender_device,receiver_device,bytes_before,bytes_after,sha256_same,guard_chunk_present,verdict_after,watermark_found,notes',
'realworld_reseal':'date,original_signer,capture_method,zoom,reseal_method,verdict,signerStatus,watermark_found,watermark_payload_correct,conflict_shown,notes',
'watermark_eval':'image_id,corpus,marked,transform,param,found,payload_correct,score,scale_found,psnr_db,ssim,runtime,seconds',
'realworld_timing':'date,device,cpu,ram_gb,browser_or_runtime,version,file,megapixels,operation,run,seconds,peak_mem_mb_if_known,completed,notes',
'usability':'participant_code,device,task,completed,seconds,errors,said_correct_verdict,quote,confusion_point',
'a11y':'date,tool,os,browser,state,task,passed,wcag_ref,issue',
}
for name,header in schemas.items():
 path=root/(name+'.csv')
 if not path.exists():
  with path.open('x',newline='') as out:csv.writer(out).writerow(header.split(','))
print('Empty templates are in '+str(root)+'. No measurements have been recorded by this script.')
