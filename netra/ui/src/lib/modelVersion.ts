/**
 * Rendering for `SiteStatusResponse.model_version`.
 *
 * Lane A returns the sentinel `"unpinned"` for a site that has never PASSED an
 * audit, rather than null, so the field stays a non-nullable string on this
 * side. SPEC.md section 6: a site must pass a local audit before its grades
 * count — so "no audited model yet" is a true statement about the site, not a
 * failure to fetch.
 *
 * It is therefore rendered as ordinary text, never with the error treatment.
 * A site awaiting its first audit is a normal state in a screening programme,
 * and showing it in red would train operators to ignore red.
 */

/** Must match `netra/api/routes/sites.py` -> `UNPINNED`. */
export const UNPINNED_MODEL_VERSION = "unpinned"

/** Plain-language text for a model version. Never an error string. */
export function formatModelVersion(version: string): string {
  if (!version || version === UNPINNED_MODEL_VERSION) {
    return "no audited model yet"
  }
  return version
}

/** True when no audit has pinned a version. Screens use this to pick a plain
 *  muted treatment, NOT the error treatment. */
export function isUnpinned(version: string): boolean {
  return !version || version === UNPINNED_MODEL_VERSION
}
