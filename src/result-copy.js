// SPDX-License-Identifier: MIT
// Presentation only. Technical verdicts, JSON and verification remain unchanged.
export function resultTitle(report) {
  if(report.verdict==='GENUINE'&&report.signerStatus==='trusted')return 'Genuine';
  if(report.verdict==='VERIFIED WITH REDACTIONS'&&report.signerStatus==='trusted')return 'Genuine, with parts blacked out';
  if(report.verdict==='FULLY REDACTED')return report.personal||report.demo?'Everything is blacked out':'Genuine, but everything is blacked out';
  if(report.verdict==='UNTRUSTED SIGNER')return report.signerStatus==='unknown'?'Unknown signer':"Couldn't check this file";
  return ({'UNVERIFIED: SELF-SIGNED':'Unknown signer',TAMPERED:'Changed',DEMO:'Example only','NOT A GRD':'Not a Guard file','REVOKED KEY':'Revoked signer'})[report.verdict]||"Couldn't check this file";
}
export function resultDescription(report,areas=report.redactionMap?.length||0) {
  const name=report.signerDisplayName||'the trusted signer';
  if(report.verdict==='GENUINE'&&report.signerStatus==='trusted')return `This picture matches what ${name} signed. Nothing was changed.`;
  if(report.verdict==='VERIFIED WITH REDACTIONS'&&report.signerStatus==='trusted')return `Everything you can see matches what ${name} signed. ${areas} ${areas===1?'area was':'areas were'} blacked out after signing.`;
  if(report.verdict==='FULLY REDACTED')return 'The whole picture was blacked out after signing. No original pixels remain to inspect.';
  if(report.verdict==='TAMPERED')return "This file failed its integrity checks. Don't rely on it.";
  if(report.signerStatus==='unknown')return "The file is intact, but this device doesn't know who signed it. Anyone can make a file like this.";
  if(report.verdict==='UNVERIFIED: SELF-SIGNED')return 'This file uses a self-signed key, so anyone could have made it.';
  if(report.verdict==='DEMO')return 'This is a sample file. It does not come from a real signer.';
  if(report.verdict==='REVOKED KEY')return "The key that signed this file has been withdrawn. Don't rely on it.";
  if(report.verdict==='NOT A GRD')return 'Choose the original .GRD file from the sender.';
  return "Guard couldn't finish the check. This is not a sign of tampering.";
}
export function signerSummary(report) {
  const fp=report.fingerprint||'';
  if(report.signerStatus==='revoked')return `${report.revocation?.reason||'Key revoked'}, revoked ${report.revocation?.revokedAt||'date unavailable'}. The picture is not shown. Do not rely on this file.`;
  if(report.signerStatus==='trusted'&&!report.personal&&!report.demo)return `Signed by ${report.signerDisplayName||'trusted key'} · trusted on this device`;
  if(report.signerStatus==='unknown')return `Fingerprint ${fp}. Ask the sender to confirm it another way.`;
  if(report.signerStatus==='self')return `Fingerprint ${fp}.`;
  if(report.verdict==='TAMPERED')return 'The picture is not shown.';
  if(['CANNOT VERIFY','UNSUPPORTED','LIMIT EXCEEDED','UNREADABLE'].includes(report.verdict))return 'Reason: '+(report.problems?.[0]||'The check could not finish.').slice(0,180);
  return '';
}
