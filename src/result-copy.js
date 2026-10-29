// SPDX-License-Identifier: MIT
// UI wording only. Technical verdict strings and verifier decisions are unchanged.
export function resultTitle(report) {
  const titles={
    'UNVERIFIED: SELF-SIGNED':'Not verified: anyone could have made this',
    'TAMPERED':'Changed after signing',
    'DEMO':'Demonstration only',
    'FULLY REDACTED':'Everything is hidden',
    'CANNOT VERIFY':"Couldn't check this file (this is not evidence of tampering)",
    'UNSUPPORTED':"Couldn't check this file (this is not evidence of tampering)",
    'LIMIT EXCEEDED':"Couldn't check this file (this is not evidence of tampering)",
    'UNREADABLE':"Couldn't check this file (this is not evidence of tampering)",
    'NOT A GRD':'Not a Guard file',
    'REVOKED KEY':'Signer key revoked',
  };
  if(report.verdict==='GENUINE'&&report.signerStatus==='trusted')return 'Verified: '+(report.signerDisplayName||'trusted key');
  if(report.verdict==='VERIFIED WITH REDACTIONS'&&report.signerStatus==='trusted')return 'Real, with parts hidden';
  if(report.verdict==='UNTRUSTED SIGNER')return report.signerStatus==='unknown'?'Valid signature, unknown signer':'Verification did not establish a valid file';
  return titles[report.verdict]??'Verification did not establish a valid file';
}
export function signerSummary(report) {
  const fp=report.fingerprint||'';
  if(report.signerStatus==='revoked')return `${report.revocation?.reason||'Key revoked'} (revoked ${report.revocation?.revokedAt||'date unavailable'}). Do not rely on this file.`;
  if(report.signerStatus==='trusted')return `Signed by ${report.signerDisplayName||'trusted key'}. Fingerprint ${fp.slice(0,16)}… · trusted in this viewer`;
  if(report.signerStatus==='unknown')return `Fingerprint ${fp}. Compare it with the sender’s independently published fingerprint.`;
  return '';
}
