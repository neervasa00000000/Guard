# Configure your own issuer

A mathematically valid signature is not an identity check. Readers must decide which issuers they trust and verify their public-key fingerprints through a separate, reliable channel. Do not approve an embedded key merely because its file opened successfully.

## Create a key locally

Create a secure directory outside this checkout, then run with Node.js 22+:

```sh
node scripts/create-signer.mjs --private /secure/signer.pem --public /secure/signer-public.pem --owner "Your issuer name"
```

The command refuses to overwrite files, writes the private key with owner-only permissions, and prints only public configuration and the SHA-256 fingerprint. Protect/back up the private key; share only the public key and fingerprint. Never put private keys in Git, the static website, or a browser import form.

## Issue and verify an asset

```sh
python3 grd.py seal original.png --key /secure/signer.pem -o original.GRD
python3 grd.py verify original.GRD --trusted-key /secure/signer-public.pem
```

Install `requirements.txt` first, preferably inside a virtual environment. Supplying `--trusted-key` is a deliberate trust decision for that command. Exit 0 means GENUINE only. Other verdicts use grouped non-zero exit codes (table in README). Treat any non-zero code as 'not proven genuine'. Operational/argument errors may return **1** or **2**. Do not treat a nonempty JSON report or a valid signature alone as a pass.

## Configure a viewer you distribute

After checking issuer identity and the printed fingerprint:

1. Add the printed entry to `src/trusted-keys.json`, remove entries your readers should not trust, run `npm ci && npm test && npm run build`, and publish the rebuilt HTML. To revoke, set `revoked:true`, `revokedAt` and `reason`, then bump `version`/`asOf`.
2. Review `src/trust-policy.json`; retain any applicable revoked fingerprints. A listed key is rejected even if pinned.
3. Distribute the rebuilt HTML through a trusted channel. Confirm a fixture from your issuer becomes GENUINE and an unknown issuer does not.

This creates trust in **your configured viewer**, not a globally approved signer or C2PA trust-list membership. The repository's default anchor is the legacy key supplied in the original viewer (`97bb1a09…fce691`, full key in source); its identity has not been independently established here. Tests use temporary anchors and must never replace production output.

Browser conversions deliberately use signed `purpose:personal`, an empty public label and a discarded ephemeral private key. They always remain **UNVERIFIED: SELF-SIGNED**, even if that public key were later pinned. For an identity-bearing file, issue a new `purpose:asset` file with the local issuer and a reviewed private key. Anyone can edit an image and self-sign a replacement; without a known root or trusted issuer, this establishes no authenticity.

To revoke an issuer, add its full SHA-256 public-key fingerprint, UTC `revokedAt` and reason to the bundled policy, increment the policy version/date and redistribute the viewer. Old offline copies cannot know later revocations. Revocation dates must use exact `YYYY-MM-DDTHH:MM:SSZ` UTC syntax.
