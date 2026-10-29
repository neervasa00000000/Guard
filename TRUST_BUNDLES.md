# Offline signed trust bundles

This is opt-in tooling, a browser-capable API, and a session-only manual import in the v4 local viewer. It defaults to the bundled snapshot; no new production root or identity has been provisioned. Never deploy the public test root from the fixture generator.

A bundle is canonical UTF-8 JSON with exactly `payload` and `signature`. The payload has exactly:

```json
{"format":"GUARD-TRUST-1","sequence":2,"issued":"2026-10-27T00:00:00Z","expires":"2026-11-27T00:00:00Z","keys":{"version":1,"asOf":"2026-10-27T00:00:00Z","signers":[]}}
```

The root signs the bytes `GUARD-TRUST-BUNDLE-V1\0 || canonical(payload)` directly with Ed25519. The 64-byte signature uses canonical base64. The root public key is supplied separately; a key embedded in a bundle cannot authorize itself. Unknown fields, duplicate signers, mismatched key fingerprints/IDs, nonportable JSON, malformed dates and invalid signatures fail closed. The keys snapshot uses the existing signer schema, with a nonempty reason and timestamp required for revoked keys. Maximum bundle size is 2 MiB and maximum signer count is 4096.

`issued <= local time < expires`, with a maximum 90-day interval. A configurable minimum sequence and remembered `{rootFingerprint, sequence, digest}` reject older snapshots, a different bundle at the same sequence and a mismatched root. Identical repeated imports are allowed. Signature validity does not make the local clock trustworthy, and the issue date does not authenticate image capture time.

## Issuer workflow

Provision the root outside this repository. Keep its private key offline. Supply a separately verified public PEM to recipients. To sign an existing keys snapshot (whose `asOf` equals `issued`):

```sh
python3 trust_bundle.py sign --keys keys.json --root-key /secure/root-private.pem \
  --sequence 2 --issued 2026-10-27T00:00:00Z --expires 2026-11-27T00:00:00Z \
  -o trust-bundle.json
```

The command validates the bundle before writing, refuses to overwrite an output and does not generate a root.

## Recipient workflow

```sh
python3 trust_bundle.py verify image.GRD --bundle trust-bundle.json \
  --root /verified/root-public.pem --state /local/guard-trust-state.json
```

The parent directory of the state file must exist and be trusted. On macOS/Linux, an advisory sidecar lock serializes this CLI's read/check/atomic-replace sequence. The authenticated state advances before the image is checked, including when the image fails. Invalid or stale bundles do not advance it. A revoked issuer returns REVOKED KEY, exit 6; an invalid bundle returns CANNOT VERIFY, exit 4. Invalid image proofs retain the verifier's usual failure verdicts.

Protect both the local clock and state directory. Deleting, replacing or rolling back the cache defeats remembered-sequence protection; first use relies on the independently supplied root and minimum sequence. An administrator can also replace the verifier itself. No claim covers such a compromised recipient environment. The lock is cooperative and local, not a distributed database lock or a defense against a hostile filesystem owner. The CLI uses POSIX locking; Windows support is pending.

## JavaScript API

`verifyTrustBundle(bytes, rootPublicKeyHex, {now, minSequence, previous})` from `src/trust-bundle.js` returns `{keys, anchors, policy, state, expires}` only after all checks pass. Use the returned anchors and policy together with `verifyGRD2` or `createVerifier`. A revoked issuer is absent from anchors and present in policy. Keep `state` in trusted, serialized persistent storage before using newer snapshots; the API itself performs no storage or network operations. Recheck expiry for each use; do not retain a successful result past `expires` without checking the bundle again.

The v4 local viewer has manual import/expiry UI. It requires a separately verified public root PEM, retains sequence/digest history in memory per root, checks expiry on each verification, clears active approvals at expiry, and resets the displayed file when trust changes. Bundled revocations cannot be undone by an imported bundle. Browser persistence, production root provisioning/rotation and deployment remain pending. The existing standalone viewer's no-storage privacy statement therefore remains accurate.

## Reproduction and evidence

```sh
node --test tests/trust-bundle.test.mjs
python3 scripts/make-trust-bundle-vectors.py
```

Serve the repository locally and open `bench/trust-bundle-browser.html`; click **Check trust bundles**. The fixtures have public deterministic TEST ONLY keys. JavaScript/Python tests exercise valid and revoked issuers, forged signatures, malformed snapshots, expiry boundary, future/overlong validity, duplicate keys, sequence floor, rollback, same-sequence equivocation and wrong roots. CLI tests cover real image verification and persisted rollback state. Native Chrome 156 agreed with Python on all 14 browser fixture cases. This establishes the tested behavior, not an independent security certification or proof of all possible inputs.
