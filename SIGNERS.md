# Signing and trust in TileSeal

The public TileSeal page creates a one-time Ed25519 key in the browser. Files sealed there are self-signed. The checker can establish that the retained pixels match the signed file, while the signer's identity is unverified.

**GENUINE** and **VERIFIED WITH REDACTIONS** require a trusted key configured in the verifier. The public page has no controls for adding a signer. The browser uses the bundled public registry and revocation snapshot.

For a file from a known issuer, compare the public key fingerprint through a separate channel. Then pass the confirmed public key to the Python verifier:

```sh
python3 grd.py verify picture.GRD --trusted-key issuer-public.pem
```

Maintainers can review updates to the bundled registry using [the signer configuration tool](scripts/pin-signer.mjs). The registry in [browser source](src/trusted-keys.json) must match the [published registry](.well-known/guard-signers.json). Rebuild the standalone pages after an approved registry update. Keep private keys outside the repository.

The [offline signer API](src/offline-signer.js), [trust bundle API](src/trust-bundle.js), and their [tests](tests/) support developer and historical workflows. See the [CLI guide](REDACTION.md) and the [archived trust bundle guide](docs/archive/TRUST_BUNDLES.md).
