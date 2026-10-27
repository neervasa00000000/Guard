"""Optional integration test with the real CAI SDK and ephemeral test certificates."""
import sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from datetime import datetime,timedelta,timezone
from cryptography import x509
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec,ed25519
from PIL import Image
import grd,c2pa_bridge
now=datetime.now(timezone.utc);root_key=ec.generate_private_key(ec.SECP256R1());leaf_key=ec.generate_private_key(ec.SECP256R1());root_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Guard TEST ONLY CA')]);leaf_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Guard TEST ONLY exporter')])
root=(x509.CertificateBuilder().subject_name(root_name).issuer_name(root_name).public_key(root_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=90)).add_extension(x509.BasicConstraints(ca=True,path_length=0),True).add_extension(x509.KeyUsage(True,False,False,False,False,True,True,None,None),True).add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()),False).sign(root_key,hashes.SHA256()))
leaf=(x509.CertificateBuilder().subject_name(leaf_name).issuer_name(root_name).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=30)).add_extension(x509.BasicConstraints(ca=False,path_length=None),True).add_extension(x509.KeyUsage(True,False,False,False,False,False,False,None,None),True).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]),False).add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()),False).sign(root_key,hashes.SHA256()))
with tempfile.TemporaryDirectory(prefix='guard-c2pa-test-') as folder:
 d=Path(folder);key=ed25519.Ed25519PrivateKey.generate();pub=d/'grd-public.pem';pub.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo));certificate=d/'chain.pem';certificate.write_bytes(leaf.public_bytes(serialization.Encoding.PEM)+root.public_bytes(serialization.Encoding.PEM));anchor=d/'root.pem';anchor.write_bytes(root.public_bytes(serialization.Encoding.PEM));private=d/'exporter.key';private.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));private.chmod(0o600)
 image=Image.new('RGB',(192,128));image.putdata([(x%256,y%256,(x+y)%256) for y in range(128) for x in range(192)]);original=grd.encode(grd.seal(image,key));redacted=grd.redact(original,[(1,1,30,30)]);source=d/'sample.GRD';source.write_bytes(redacted);output=d/'credential.png';c2pa_bridge.export(source,output,private,certificate,[pub]);report=c2pa_bridge.inspect(output,[pub],anchor)
 assert report['accepted'],report
 assert report['c2pa']['validation_state']=='Trusted'
 assert not report['c2pa']['validation_results']['activeManifest']['failure']
 assert report['grd']['verdict']=='VERIFIED WITH REDACTIONS',report['grd']
 assert report['grd']['redactedTiles']==[0]
 active=report['c2pa']['manifests'][report['c2pa']['active_manifest']]
 assert any(a['label']==c2pa_bridge.ASSERTION for a in active['assertions'])
 # Change only pixels inside a GRD-redacted tile, retaining the C2PA manifest.
 # The GRD region proof may still pass, but C2PA's exported-asset hash MUST fail.
 import struct,zlib
 altered_image=Image.open(output).convert('RGB');altered_image.putpixel((1,1),(255,0,0));new_png=grd.png_write(altered_image.tobytes(),192,128)
 def chunks(data):
  at=8
  while at<len(data):
   length=struct.unpack_from('>I',data,at)[0];yield data[at+4:at+8],data[at:at+12+length];at+=12+length
 replacement=[chunk for kind,chunk in chunks(new_png) if kind==b'IDAT'];parts=[output.read_bytes()[:8]];inserted=False
 for kind,chunk in chunks(output.read_bytes()):
  if kind==b'IDAT':
   if not inserted:parts.extend(replacement);inserted=True
  else:parts.append(chunk)
 tampered=d/'tampered.png';tampered.write_bytes(b''.join(parts));negative=c2pa_bridge.inspect(tampered,[pub],anchor)
 assert not negative['accepted'],negative
 assert negative['c2pa']['validation_state']=='Invalid',negative['c2pa']
 assert negative['grd']['verdict']=='VERIFIED WITH REDACTIONS'
 print(json.dumps({'sdk':'c2pa-python','grd':report['grd']['verdict'],'validation_state':report['c2pa'].get('validation_state'),'validation_status':report['c2pa'].get('validation_status'),'validation_results':report['c2pa'].get('validation_results'),'custom_assertion':True},indent=2))
