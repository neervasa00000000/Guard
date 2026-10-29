# Configure your own issuer

A mathematically valid signature is not an identity check. Readers must decide which issuers they trust and verify their public-key fingerprints through a separate, reliable channel. Do not approve an embedded key merely because its file opened successfully.

## Sign inside Guard, including offline

1. Open **Advanced → Your signer key**.
2. Create a signer using a name and a unique password of at least 12 characters. Save `signer.guardkey` and a separate backup. There is no password recovery. The name becomes public in signed files.
3. On a later visit, choose that saved `.guardkey` file and unlock it. The unlocked signing key is nonextractable and held in memory only. **Lock signer**, reload, or close the page when finished. Locking does not erase copies already downloaded and cannot guarantee immediate erasure from browser process memory.
4. Save **public.guardsigner** to share with recipients. Never send the `.guardkey` file or password. Confirm the full SHA-256 fingerprint and name through a separate trusted channel.
5. The recipient opens **Advanced → Trust a person**, selects the public file and enters the independently confirmed fingerprint. This deliberately trusts that key for this tab only; reload clears it. Reopen the .GRD file to check it. It remains unknown in other viewers until they explicitly trust it. Creating or unlocking a signer never automatically adds trust.

With a saved signer, conversion produces the existing `purpose:asset` format with the name in its signed label. Without one, the disposable `purpose:personal` behavior stays unchanged. Existing personal files remain self-signed even if their key is trusted later. Revoked keys cannot be imported as trusted people. Bundled identities cannot be renamed through public-file import. Offline copies only know the revocations included in their snapshot or imported bundle; this is not a hardware key, timestamp service, identity certificate or C2PA credential.

Use **Advanced → Offline copy → Download offline viewer** to save the self-contained HTML, then open it in a current browser. No network service or browser storage is required for key creation, unlocking, signing or checking. Direct local-file browser validation is pending because the automated browser tool refuses file URLs; local HTTP browser tests cover the same bundled code with network connections disabled by CSP.

### Encrypted key file v1

`Guard encrypted signer` version 1 fixes PBKDF2-HMAC-SHA-256 at 600,000 iterations, a random 16-byte salt, AES-256-GCM with a random 12-byte nonce and 128-bit tag, and UTF-8 additional authenticated data `Guard encrypted signer v1`. The encrypted JSON contains only name, 32-byte public key hex and PKCS#8 Ed25519 private key base64. The outer JSON carries format/version/kdf/iterations/cipher/salt/iv/data and no plaintext name or private key. Unknown parameters, unexpected fields, invalid sizes, incorrect passwords, altered ciphertext and mismatched private/public pairs are rejected. Imports are capped at 16 KiB; KDF costs cannot be selected by an imported file. Password encryption resists guessing according to the password strength; it does not protect an unlocked key from malicious page code, browser extensions, or a compromised device.

The public `.guardsigner` JSON contains format `Guard public signer`, version 1, name, publicKey and fingerprint. It is a contact claim, not a signed identity certificate. Independent confirmation is essential. Public keys and names are rendered as text, never HTML.

Implementation follows the browser [Web Crypto password-derived key interface](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/deriveKey). Python interoperability can be checked with `GUARD_TEST_PYTHON=.venv/bin/python node scripts/check-offline-signer.mjs`.

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

Without an unlocked saved signer, browser conversions use signed `purpose:personal`, an empty public label and a discarded ephemeral private key. They always remain **UNVERIFIED: SELF-SIGNED**, even if that public key were later pinned. For an identity-bearing file, unlock a saved signer in Guard or issue a new `purpose:asset` file with the local issuer and a reviewed private key. Anyone can edit an image and self-sign a replacement; without a known root or trusted issuer, this establishes no authenticity.

To revoke an issuer, add its full SHA-256 public-key fingerprint, UTC `revokedAt` and reason to the bundled policy, increment the policy version/date and redistribute the viewer. Old offline copies cannot know later revocations. Revocation dates must use exact `YYYY-MM-DDTHH:MM:SSZ` UTC syntax.

## Maintain the published registry

After independently verifying the public fingerprint:

```sh
node scripts/pin-signer.mjs --public /secure/signer-public.pem --name "Neer"
node scripts/pin-signer.mjs --revoke FULL_SHA256_FINGERPRINT --reason "Key lost or compromised" --at YYYY-MM-DDTHH:MM:SSZ
npm run build
```

The helper updates `src/trusted-keys.json`, `.well-known/guard-signers.json`, and revocation policy as applicable. It refuses private-key input, requires `--rename` for an existing key’s name change, and refuses to reactivate revoked keys even with `--rename`. The build fails if the two public registries differ. Our signing key fingerprint is `{NEER_FINGERPRINT}` until the actual public key is supplied. Published endpoint: [guard-signers.json](https://neervasa00000000.github.io/Guard/.well-known/guard-signers.json). Compare the full 64 characters through an independent channel. The offline viewer does not fetch it.

Create keys offline; keep the private key outside Git, the website, email, chat and browser inputs. Keep one encrypted offline backup. Revoke and rotate lost or compromised keys. Old offline viewers cannot discover later revocations. A root PEM loaded with a signed trust bundle is a deliberate trust decision, not identity evidence by itself. Session imports do not persist after reload.

The revoked legacy record is labelled **Legacy viewer key (ownership unconfirmed)**. It does not identify Neer. The future intended signer name is **Neer**, once a separately verified public key is supplied; `{NEER_FINGERPRINT}` remains pending. To deliberately correct an active signer's label, repeat `--public` and `--name` with `--rename`. Same-name imports remain idempotent.
