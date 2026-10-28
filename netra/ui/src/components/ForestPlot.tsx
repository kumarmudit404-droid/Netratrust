/**
 * A forest plot of Wilson intervals, one row per site (T-16, SPEC.md section 7).
 *
 * Deliberately NOT a violin or a density: "KDE invents structure at realistic
 * per-site n". One marker, one interval, one optional pooled reference line.
 *
 * Nothing here computes a statistic. The intervals are the server's Wilson
 * bounds; the marker position is k/n only so it sits between them. Every
 * NUMBER rendered — axis ticks aside — comes from `formatRate` via
 * `point.label`.
 */

import {
  CartesianGrid,
  ErrorBar,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { ForestPoint } from "@/lib/forest"

/** Row height, so a 4-site and a 12-site plot both read at the same density. */
const ROW_PX = 44
const MIN_H = 160

/** Exported for testing: this is where a point's figures become text, so it is
 *  the place the n<30 rule can actually be asserted against rendered output. */
export function ForestTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: { payload: ForestPoint }[]
}) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="rounded-md border border-border-subtle bg-surface px-3 py-2 shadow-sm">
      <p className="text-caption font-semibold text-text">{p.site_id}</p>
      {/* formatRate output, never a bare percentage. */}
      <p className="font-mono text-caption text-text tabular">{p.label}</p>
      {p.smallN && (
        <p className="mt-1 text-caption text-borderline">
          n below 30 — counts only
        </p>
      )}
      {p.driftFlag && (
        <p className="mt-1 text-caption text-reject">drift flagged</p>
      )}
    </div>
  )
}

export function ForestPlot({
  points,
  pooled,
  pooledLabel,
  xLabel,
}: {
  points: ForestPoint[]
  /** Pooled reference x position, or null when there is nothing to pool. */
  pooled: number | null
  pooledLabel?: string
  xLabel: string
}) {
  if (points.length === 0) {
    return (
      <p className="px-2 py-8 text-center text-body text-text-muted">
        No site has enough data to plot yet.
      </p>
    )
  }

  const height = Math.max(MIN_H, points.length * ROW_PX + 56)

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 24, bottom: 28, left: 8 }}>
          <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="2 4" />
          <XAxis
            type="number"
            dataKey="est"
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tick={{ fill: "var(--text-muted)", fontSize: 13 }}
            stroke="var(--border-subtle)"
            label={{
              value: xLabel,
              position: "insideBottom",
              offset: -16,
              fill: "var(--text-muted)",
              fontSize: 13,
            }}
          />
          <YAxis
            type="category"
            dataKey="site_id"
            width={78}
            tick={{ fill: "var(--text)", fontSize: 13 }}
            stroke="var(--border-subtle)"
          />
          <Tooltip
            content={<ForestTooltip />}
            // The marker is small; without this the tooltip is hard to hit.
            cursor={{ stroke: "var(--border-subtle)" }}
          />

          {/* The pooled line is a REFERENCE, not a headline number. It is drawn
              only when the server sent pooled counts to draw it from. */}
          {pooled !== null && (
            <ReferenceLine
              x={pooled}
              stroke="var(--text-muted)"
              strokeDasharray="6 4"
              label={{
                value: pooledLabel ?? "pooled",
                position: "top",
                fill: "var(--text-muted)",
                fontSize: 13,
              }}
            />
          )}

          <Scatter data={points} fill="var(--text)" shape="circle">
            <ErrorBar
              dataKey="xErr"
              direction="x"
              width={6}
              strokeWidth={2}
              stroke="var(--text)"
            />
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
