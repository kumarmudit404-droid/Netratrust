/**
 * The n<30 rule, implemented exactly once (design.md section 7).
 *
 * "No bare percentage is rendered for n < 30." Below the threshold this returns
 * "k of n" with no percentage; at or above it, "k/n (lo-hi)" using the Wilson
 * bounds the API supplies.
 *
 * The front end NEVER computes a statistic: Wilson bounds come from the server,
 * which gets them from netra/eval/metrics.py. If the interval is missing we
 * print counts only - never a bare percentage as a fallback.
 */

import type { RateCounts } from "./api/types"

/** Mirrors config/thresholds.yaml -> sites.min_n_for_rate. */
export const MIN_N_FOR_RATE = 30

export function formatRate(k: number, n: number, ci?: [number, number]): string {
  if (n <= 0) return "no data"
  if (n < MIN_N_FOR_RATE) return `${k} of ${n}`
  if (!ci) return `${k}/${n}`
  return `${k}/${n} (${ci[0].toFixed(2)}-${ci[1].toFixed(2)})`
}

export function formatCounts(r: RateCounts): string {
  return formatRate(r.k, r.n, r.ci)
}

/** True when the sample is too small for a rate. Screens use this to show the
 *  "n<30" marker and to sort small-n rows last. */
export function isSmallN(n: number): boolean {
  return n < MIN_N_FOR_RATE
}
