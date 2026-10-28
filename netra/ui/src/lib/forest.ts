/**
 * Data shaping for the per-site forest plot (T-16, SPEC.md section 7).
 *
 * SPEC.md: "forest plot of Wilson intervals against the pooled line. Avoid
 * violins — KDE invents structure at realistic per-site n." So this produces
 * one point plus one interval per site and nothing smoothed.
 *
 * The front end never computes a STATISTIC. The Wilson bounds come from the
 * server (which gets them from netra/eval/metrics.py); `est` here is k/n used
 * only to POSITION the marker between those server-supplied bounds, and
 * `xErr` is the two offsets Recharts' ErrorBar wants. Neither is ever
 * rendered as a number — every figure on screen goes through `formatRate`.
 *
 * TODO(review): a plotted marker is a visual proportion even when n < 30. The
 * small-n rule in design.md section 7 forbids a bare PERCENTAGE, and a point
 * shown with its (wide) Wilson interval is the honest alternative the rule
 * prefers, so small-n sites are plotted, flagged `smallN`, sorted last, and
 * labelled "k of n" with no percentage anywhere.
 */

import { formatRate, isSmallN } from "./formatRate"
import type { RateCounts, SiteMetricsRow } from "./api/types"

export interface ForestPoint {
  site_id: string
  /** k/n, for MARKER POSITION only. Never rendered as a number. */
  est: number
  /** [distance to lower bound, distance to upper bound] — Recharts ErrorBar. */
  xErr: [number, number]
  k: number
  n: number
  ci?: [number, number]
  /** n < sites.min_n_for_rate. Drives the marker style and the sort order. */
  smallN: boolean
  driftFlag: boolean
  /** The only figure allowed on screen: counts, or counts + interval. */
  label: string
}

/** Which measure of a row to plot. */
export type Measure = "gradability" | "abstention"

function toPoint(row: SiteMetricsRow, measure: Measure): ForestPoint | null {
  const r: RateCounts = row[measure]
  // A site with no encounters has no proportion to place. It stays in the
  // table as "no data" rather than being plotted at a misleading zero.
  if (r.n <= 0) return null

  const est = r.k / r.n
  const lo = r.ci ? r.ci[0] : est
  const hi = r.ci ? r.ci[1] : est
  return {
    site_id: row.site_id,
    est,
    // Clamped at zero: a server interval should bracket the estimate, but a
    // negative bar would render as a spike pointing the wrong way.
    xErr: [Math.max(0, est - lo), Math.max(0, hi - est)],
    k: r.k,
    n: r.n,
    ci: r.ci,
    smallN: isSmallN(r.n),
    driftFlag: row.drift_flag,
    label: formatRate(r.k, r.n, r.ci),
  }
}

/**
 * Points for one measure, ordered for reading: well-powered sites first
 * (largest n at the top of the plot), small-n sites last.
 *
 * Ordering by n rather than by estimate is deliberate — ranking sites by a
 * rate invites reading the top row as "the worst site" when the difference is
 * sampling noise.
 */
export function toForestPoints(
  rows: SiteMetricsRow[],
  measure: Measure,
): ForestPoint[] {
  return rows
    .map((row) => toPoint(row, measure))
    .filter((p): p is ForestPoint => p !== null)
    .sort((a, b) => {
      if (a.smallN !== b.smallN) return a.smallN ? 1 : -1
      if (a.n !== b.n) return b.n - a.n
      return a.site_id.localeCompare(b.site_id)
    })
}

/** Rows with nothing to plot, so the table can still account for them. */
export function emptyRows(rows: SiteMetricsRow[], measure: Measure): SiteMetricsRow[] {
  return rows.filter((row) => row[measure].n <= 0)
}

/**
 * The pooled reference line's x position, or null when there is nothing to
 * pool. Lane A sends pooled SUMMED COUNTS, so this is k/n over the whole
 * programme — NOT the mean of the per-site rates, which SPEC.md forbids and
 * which differs from this whenever sites have unequal n.
 */
export function pooledEstimate(pooled: RateCounts | undefined): number | null {
  if (!pooled || pooled.n <= 0) return null
  return pooled.k / pooled.n
}

/** Sites whose latest audit flagged drift. The view lists these by name. */
export function driftingSites(rows: SiteMetricsRow[]): string[] {
  return rows.filter((r) => r.drift_flag).map((r) => r.site_id)
}
