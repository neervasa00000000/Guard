# Configure your own issuer

A mathematically valid signature is not an identity check. Readers must decide which issuers they trust and verify their public-key fingerprints through a separate, reliable channel. Do not approve an embedded key merely because its file opened successfully.

## Create a key locally

Create a secure directory outside this checkout, then run the command below. Tested on Node 20.19 and 22; Python 3.13; Chrome 156.

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

This creates trust in **your configured viewer**, not a globally approved signer or C2PA trust-list membership. The repository's legacy key (`97bb1a09…fce691`, full key in source) is now revoked at the owner's request because its identity was not established. Its public record is retained so old files receive an explicit revocation result. No replacement issuer is pinned until its public key is supplied. Tests use temporary anchors and must never replace production output.

Browser conversions deliberately use signed `purpose:personal`, an empty public label and a discarded ephemeral private key. They always remain **UNVERIFIED: SELF-SIGNED**, even if that public key were later pinned. For an identity-bearing file, issue a new `purpose:asset` file with the local issuer and a reviewed private key. Anyone can edit an image and self-sign a replacement; without a known root or trusted issuer, this establishes no authenticity.

To revoke an issuer, add its full SHA-256 public-key fingerprint, UTC `revokedAt` and reason to the bundled policy, increment the policy version/date and redistribute the viewer. Old offline copies cannot know later revocations. Revocation dates must use exact `YYYY-MM-DDTHH:MM:SSZ` UTC syntax.

## Maintain the published registry

After independently verifying the public fingerprint:

```sh
node scripts/pin-signer.mjs --public /secure/signer-public.pem --name "Neer"
node scripts/pin-signer.mjs --revoke FULL_SHA256_FINGERPRINT --reason "Key lost or compromised" --at YYYY-MM-DDTHH:MM:SSZ
npm run build
```

The helper updates `src/trusted-keys.json`, `.well-known/guard-signers.json`, and revocation policy as applicable. It refuses private-key input and refuses to reactivate revoked keys. The build fails if the two public registries differ. Our signing key fingerprint is `{NEER_FINGERPRINT}` until the actual public key is supplied. Published endpoint: [guard-signers.json](https://neervasa00000000.github.io/Guard/.well-known/guard-signers.json). Compare the full 64 characters through an independent channel. The offline viewer does not fetch it.

Create keys offline; keep the private key outside Git, the website, email, chat and browser inputs. Keep one encrypted offline backup. Revoke and rotate lost or compromised keys. Old offline viewers cannot discover later revocations. A root PEM loaded with a signed trust bundle is a deliberate trust decision, not identity evidence by itself. Session imports do not persist after reload.
