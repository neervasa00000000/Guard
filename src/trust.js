// SPDX-License-Identifier: MIT
import policy from "./trust-policy.json" with { type: "json" };
import trustedData from "./trusted-keys.json" with { type: "json" };

const revokedFromKeys = (trustedData.signers || [])
  .filter((s) => s.revoked)
  .map((s) => ({
    fingerprint: s.fingerprint_sha256,
    reason: s.reason || "Revoked key",
    revokedAt: s.revokedAt,
  }));

export const TRUST_POLICY = Object.freeze({
  ...policy,
  revoked: Object.freeze([
    ...policy.revoked.map((entry) => Object.freeze({ ...entry })),
    ...revokedFromKeys.map((entry) => Object.freeze({ ...entry })),
  ]),
});
function policyDate(value) {
  return (
    typeof value === "string" &&
    !value.startsWith("0000") &&
    /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value) &&
    Number.isFinite(Date.parse(value)) &&
    new Date(value).toISOString() === value.replace("Z", ".000Z")
  );
}
export async function checkRevocation(publicKey, snapshot = TRUST_POLICY) {
  if (
    !snapshot ||
    !Number.isSafeInteger(snapshot.version) ||
    snapshot.version < 1 ||
    !policyDate(snapshot.asOf) ||
    !Array.isArray(snapshot.revoked) ||
    snapshot.revoked.some(
      (r) =>
        !r ||
        typeof r.fingerprint !== "string" ||
        !/^[0-9a-f]{64}$/.test(r.fingerprint) ||
        typeof r.reason !== "string" ||
        !policyDate(r.revokedAt),
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
