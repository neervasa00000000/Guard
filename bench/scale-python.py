#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Sequential isolated Python synthetic sealing measurements, visual layer on AND off."""
import sys,time,json,random,resource,platform,argparse,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import grd
p=argparse.ArgumentParser();p.add_argument('--one',nargs=3,metavar=('WIDTH','HEIGHT','VISUAL'));p.add_argument('--adaptive-verification',action='store_true');a=p.parse_args()
if a.one:
 w,h=map(int,a.one[:2]);visual=a.one[2]=='on'
 image=grd.Image.frombytes('RGB',(w,h),random.Random(42).randbytes(w*h*3));key=grd.Ed25519PrivateKey.generate();pk=key.public_key().public_bytes(grd.serialization.Encoding.Raw,grd.serialization.PublicFormat.Raw).hex()
 start=time.perf_counter();doc=grd.seal(image,key,visual=visual);seal=time.perf_counter();data=grd.encode(doc);encoded=time.perf_counter();r=grd.verify(data,[pk]);done=time.perf_counter();assert r['verdict']=='GENUINE',r
 out=dict(visual_layer='on' if visual else 'off',width=w,height=h,version=doc['manifest']['version'],container_bytes=len(data),seal_ms=(seal-start)*1000,encode_ms=(encoded-seal)*1000,verify_ms=(done-encoded)*1000,verdict=r['verdict'],peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024))
 if a.adaptive_verification and doc['manifest']['version']==3:
  del r,data
  doc['image']=grd.png_write(image.tobytes(),w,h);adaptive_data=grd.encode3(doc);t=time.perf_counter();adaptive=grd.verify(adaptive_data,[pk]);assert adaptive['verdict']=='GENUINE';out['adaptive_png_verify_ms']=(time.perf_counter()-t)*1000
 print(json.dumps(out));sys.exit(0)
rows=[];path=grd.ROOT/'results/python-scale.json';path.parent.mkdir(exist_ok=True)
for w,h in ((2048,2048),(4000,2000),(4000,3000),(6000,4000),(7680,4320)):
 for visual in ('off','on'):
  args=[sys.executable,__file__,'--one',str(w),str(h),visual]+(['--adaptive-verification'] if a.adaptive_verification else [])
  child=subprocess.run(args,capture_output=True,text=True,timeout=240);assert child.returncode==0,child.stderr
  row=json.loads(child.stdout);rows.append(row);print(json.dumps(row),flush=True)
  path.write_text(json.dumps(dict(scope='Sequential isolated synthetic Python runs, visual on/off, fine sub-tiles disabled; one sample per mode/size, not publication statistics.',python=sys.version,platform=platform.platform(),rows=rows),indent=2)+'\n')
