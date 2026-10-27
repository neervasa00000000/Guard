import policy from "./trust-policy.json" with { type: "json" };
export const TRUST_POLICY = Object.freeze({
  ...policy,
  revoked: Object.freeze(
    policy.revoked.map((entry) => Object.freeze({ ...entry })),
  ),
});
export async function checkRevocation(publicKey, snapshot = TRUST_POLICY) {
  if (
    !snapshot ||
    !Number.isSafeInteger(snapshot.version) ||
    snapshot.version < 1 ||
    typeof snapshot.asOf !== "string" ||
    !Number.isFinite(Date.parse(snapshot.asOf)) ||
    !Array.isArray(snapshot.revoked) ||
    snapshot.revoked.some(
      (r) =>
        !r ||
        typeof r.fingerprint !== "string" ||
        !/^[0-9a-f]{64}$/.test(r.fingerprint) ||
        typeof r.reason !== "string" ||
        !Number.isFinite(Date.parse(r.revokedAt)),
    )
  )
    throw new Error("Invalid offline revocation policy.");
  const digest = new Uint8Array(
      await crypto.subtle.digest("SHA-256", publicKey),
    ),
    fingerprint = Array.from(digest)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join(""),
    entry = snapshot.revoked.find((r) => r.fingerprint === fingerprint);
  return {
    revoked: !!entry,
    fingerprint,
    reason: entry?.reason,
    revokedAt: entry?.revokedAt,
    policyVersion: snapshot.version,
    asOf: snapshot.asOf,
    scope: "Bundled offline snapshot only; newer revocations may be unknown.",
  };
}
