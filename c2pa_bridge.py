#!/usr/bin/env python3
"""C2PA PNG bridge. Credentials identify the exporter; GRD2 independently proves retained pixels."""
import argparse,io,json,tempfile,sys,uuid
from pathlib import Path
import c2pa
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import ec,ed25519
from PIL import Image
import grd
ASSERTION='io.github.neervasa00000000.guard.grd2'
def trusted_keys(paths):return grd.PINNED+[serialization.load_pem_public_key(Path(p).read_bytes()).public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex() for p in paths]
def context(anchor=None):
 settings={'builder':{'thumbnail':{'enabled':False}},'verify':{'remote_manifest_fetch':False,'verify_cert_anchors':True}}
 if anchor:settings['trust']={'trust_anchors':Path(anchor).read_text()}
 return c2pa.Context.from_dict(settings)
def export(source,output,key_file,certificate,grd_keys=(),allow_demo=False):

 if Path(source).stat().st_size>32*1024*1024:raise ValueError('Input exceeds 32 MiB')
 data=Path(source).read_bytes();r=grd.verify(data,trusted_keys(grd_keys))
 if r.get('version')!=2 or not r.get('regionVerified') or (r['verdict'] not in ('GENUINE','VERIFIED WITH REDACTIONS') and not(allow_demo and r['verdict']=='DEMO')):raise ValueError('A verified GRD2 (or explicitly allowed demo) is required: '+r['verdict'])
 if Path(output).exists():raise FileExistsError('Output already exists')
 doc=r['_document'];proof={k:doc[k] for k in ('manifest','signature','tiles','redactions')}
 ingredient_id='xmp:iid:'+str(uuid.uuid4())
 actions=[{'action':'c2pa.opened','parameters':{'ingredientIds':[ingredient_id]}}]
 if r['redactedTiles']:actions.append({'action':'c2pa.edited','parameters':{ASSERTION:r['redactionMap']}})
 manifest={'claim_generator_info':[{'name':'Guard GRD2 bridge','version':'2.0.0-experimental'}],'title':'GRD2 redacted image' if r['redactedTiles'] else 'GRD2 image export','format':'image/png','assertions':[{'label':'c2pa.actions.v2','data':{'actions':actions,'allActionsIncluded':False}},{'label':ASSERTION,'data':{'profile':'grd2-redaction-v1','source_container_sha256':grd.sha(data),'proof':proof,'scope':'Exact retained RGB pixels; hidden tile contents and redactor approval are not attested. Demo is not trusted evidence.','demo':doc['manifest']['purpose']=='demo'}}]}
 key=serialization.load_pem_private_key(Path(key_file).read_bytes(),None)
 if isinstance(key,ec.EllipticCurvePrivateKey) and isinstance(key.curve,ec.SECP256R1):alg=c2pa.C2paSigningAlg.ES256;callback=lambda b:key.sign(b,ec.ECDSA(hashes.SHA256()))
 elif isinstance(key,ed25519.Ed25519PrivateKey):alg=c2pa.C2paSigningAlg.ED25519;callback=key.sign
 else:raise ValueError('C2PA bridge supports ES256 or Ed25519 signing keys')
 with tempfile.TemporaryDirectory(prefix='guard-c2pa-') as temp:
  image=Path(temp)/'export.png';image.write_bytes(grd.un64(doc['image']))
  with context() as ctx, c2pa.Signer.from_callback(callback,alg,Path(certificate).read_text()) as signer, c2pa.Builder(manifest,ctx) as builder:
   with image.open('rb') as stream:builder.add_ingredient({'title':'GRD2 rendered pixels','format':'image/png','relationship':'parentOf','instance_id':ingredient_id},'image/png',stream)
   builder.sign_file(str(image),str(Path(temp)/'signed.png'),signer)
  with open(output,'xb') as handle:handle.write((Path(temp)/'signed.png').read_bytes())
 return {'output':str(output),'root':r['root'],'redactedTiles':r['redactedTiles'],'credentialTrust':'Determined by the inspecting tool’s C2PA trust policy. This export does not grant mainstream trust.'}
def inspect(source,grd_keys=(),anchor=None):
 if Path(source).stat().st_size>64*1024*1024:raise ValueError('Input exceeds 64 MiB')
 with context(anchor) as ctx,c2pa.Reader(str(source),context=ctx) as reader:store=json.loads(reader.json())
 active=store['manifests'][store['active_manifest']];assertion=next((a for a in active.get('assertions',[]) if a.get('label')==ASSERTION),None)
 if not assertion:raise ValueError('No Guard GRD2 proof assertion')
 payload=assertion['data']
 if payload.get('profile')!='grd2-redaction-v1':raise ValueError('Unsupported Guard C2PA profile')
 with Image.open(source) as image:
  if image.width>4096 or image.height>4096 or image.width*image.height>4194304:raise ValueError('Image too large')
  image=image.convert('RGB');png=grd.png_write(image.tobytes(),image.width,image.height)
 proof=dict(payload['proof']);proof['image']=grd.b64(png);r=grd.verify(grd.encode(proof),trusted_keys(grd_keys))
 return {'accepted':store.get('validation_state')=='Trusted' and r['verdict'] in ('GENUINE','VERIFIED WITH REDACTIONS'),'c2pa':store,'grd':{k:v for k,v in r.items() if not k.startswith('_')},'trustAnchorSupplied':bool(anchor),'scope':'C2PA validates the exported PNG and exporter credentials. GRD2 validates retained original pixels. Standard C2PA tools need this custom profile to interpret regional GRD proofs.'}
def main():
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
 e=s.add_parser('export');e.add_argument('source');e.add_argument('-o','--output',required=True);e.add_argument('--key',required=True);e.add_argument('--cert',required=True);e.add_argument('--trusted-grd-key',action='append',default=[]);e.add_argument('--allow-demo',action='store_true')
 v=s.add_parser('verify');v.add_argument('source');v.add_argument('--trusted-grd-key',action='append',default=[]);v.add_argument('--trust-anchor')
 args=p.parse_args()
 result=export(args.source,args.output,args.key,args.cert,args.trusted_grd_key,args.allow_demo) if args.command=='export' else inspect(args.source,args.trusted_grd_key,args.trust_anchor)
 print(json.dumps(result,indent=2));return 0 if args.command=='export' or result['accepted'] else 2
if __name__=='__main__':sys.exit(main())
