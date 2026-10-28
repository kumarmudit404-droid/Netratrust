/**
 * Sites — T-16. The performance dashboard, which doubles as the drift monitor.
 *
 * Per SPEC.md section 7 and design.md section 5: a forest plot of Wilson
 * intervals against the pooled line. Per-site performance is always a
 * DISTRIBUTION — there is no headline mean anywhere on this screen, and the
 * pooled line is labelled as a reference, not as the programme's score.
 *
 * Two panels, not one chart with two series: gradability has a pooled
 * reference line because Lane A sends pooled counts for it. Abstention does
 * NOT, and this screen will not invent one — averaging the per-site abstention
 * rates would be exactly the mean SPEC.md forbids.
 */

import { useState } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ForestPlot } from "@/components/ForestPlot"
import { StatusBadge } from "@/components/StatusBadge"
import { useSiteMetrics, useSiteStatus } from "@/lib/api/queries"
import { formatCounts, isSmallN, MIN_N_FOR_RATE } from "@/lib/formatRate"
import { formatModelVersion, isUnpinned } from "@/lib/modelVersion"
import {
  driftingSites,
  emptyRows,
  pooledEstimate,
  toForestPoints,
} from "@/lib/forest"
import { cn } from "@/lib/utils"

export default function Sites() {
  const { data, isLoading, isError, error, isFetching, dataUpdatedAt } =
    useSiteMetrics()
  const [selected, setSelected] = useState<string | null>(null)

  if (isLoading) {
    return (
      <Shell>
        <Card>
          <CardContent className="py-12 text-center text-body text-text-muted">
            Loading per-site performance…
          </CardContent>
        </Card>
      </Shell>
    )
  }

  if (isError || !data) {
    return (
      <Shell>
        <Card className="border-l-4 border-l-reject">
          <CardContent className="flex flex-wrap items-center gap-3 py-6">
            <StatusBadge status="error" label="Could not load site metrics" />
            <p className="text-body text-text">
              {error instanceof Error ? error.message : "The API did not respond."}
            </p>
          </CardContent>
        </Card>
      </Shell>
    )
  }

  const rows = data.rows

  // Zero sites is a real state on a fresh server, and without this the screen
  // renders two empty plots plus a table whose only row is "Pooled — no data",
  // which reads as broken rather than as empty.
  if (rows.length === 0) {
    return (
      <Shell>
        <Card className="mt-6 border-dashed">
          <CardContent className="space-y-3 py-10">
            <p className="text-subhead text-text">No sites registered yet.</p>
            <p className="max-w-prose text-body text-text-muted">
              Per-site performance appears here once a site exists and has
              screened at least one patient.
            </p>
            <p className="max-w-prose text-caption text-text-muted">
              There is no endpoint that creates a site — the nine are frozen —
              so registering one is a server-side step.
            </p>
          </CardContent>
        </Card>
      </Shell>
    )
  }

  const gradability = toForestPoints(rows, "gradability")
  const abstention = toForestPoints(rows, "abstention")
  const pooled = pooledEstimate(data.pooled?.gradability)
  const drifting = driftingSites(rows)
  const unplotted = emptyRows(rows, "gradability")

  return (
    <Shell>
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-body text-text-muted">
          {rows.length} {rows.length === 1 ? "site" : "sites"}. Every figure is a
          count with a Wilson interval — no rate is shown below n={MIN_N_FOR_RATE}.
        </p>
        <span className="ml-auto flex items-center gap-2 font-mono text-caption text-text-muted">
          <RefreshCw
            aria-hidden="true"
            className={cn("size-4", isFetching && "animate-spin")}
          />
          {isFetching
            ? "refreshing…"
            : dataUpdatedAt
              ? `updated ${new Date(dataUpdatedAt).toLocaleTimeString()}`
              : ""}
        </span>
      </div>

      {/* Drift is the thing a programme manager opens this screen to find, so
          it is stated in words at the top, not left to a colour in a table. */}
      {drifting.length > 0 && (
        <Card className="mt-4 border-l-4 border-l-reject">
          <CardContent className="flex flex-wrap items-center gap-3 py-4">
            <AlertTriangle aria-hidden="true" className="size-5 shrink-0 text-reject" />
            <p className="text-body text-text">
              <span className="font-semibold">Drift flagged</span> at{" "}
              {drifting.join(", ")} by its latest audit. Grades from a drifting
              site should be reviewed before they are acted on.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Gradability by site</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 max-w-prose text-caption text-text-muted">
              Images the gate admitted, over every image it saw. A rejected
              image counts in the denominator — that is what gradability
              measures.
            </p>
            <ForestPlot
              points={gradability}
              pooled={pooled}
              pooledLabel="pooled"
              xLabel="proportion (0–1)"
            />
            <p className="mt-1 text-caption text-text-muted">
              Bars are 95% Wilson intervals. The dashed line is the pooled count
              across all sites
              {data.pooled?.gradability
                ? ` (${formatCounts(data.pooled.gradability)})`
                : ""}
              , drawn as a reference. It is not the programme's headline score,
              and it is not a mean of the per-site rates.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Abstention by site</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-2 max-w-prose text-caption text-text-muted">
              Admitted images the model abstained on, over admitted images
              only. A rejected image was never graded, so it cannot have
              abstained.
            </p>
            <ForestPlot
              points={abstention}
              pooled={null}
              xLabel="proportion (0–1)"
            />
            <p className="mt-1 text-caption text-text-muted">
              Bars are 95% Wilson intervals. No pooled line: the API sends
              pooled counts for gradability only, and averaging the per-site
              rates would be the mean this project does not report.
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ------------------------------------------------------- the table */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Exact counts</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[34rem] border-collapse text-body">
            <caption className="sr-only">
              Per-site gradability and abstention as counts with 95% Wilson
              intervals, and the drift flag from each site's latest audit.
            </caption>
            <thead>
              <tr className="border-b border-border-subtle text-left">
                <th scope="col" className="py-2 pr-4 font-semibold">Site</th>
                <th scope="col" className="py-2 pr-4 font-semibold">Gradability</th>
                <th scope="col" className="py-2 pr-4 font-semibold">Abstention</th>
                <th scope="col" className="py-2 font-semibold">Drift</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const small =
                  isSmallN(row.gradability.n) || isSmallN(row.abstention.n)
                return (
                  <tr
                    key={row.site_id}
                    className="border-b border-border-subtle last:border-0"
                  >
                    <th scope="row" className="py-2 pr-4 text-left font-normal">
                      <button
                        type="button"
                        onClick={() =>
                          setSelected((s) => (s === row.site_id ? null : row.site_id))
                        }
                        aria-expanded={selected === row.site_id}
                        className="rounded-md px-1 font-mono underline decoration-border-subtle underline-offset-4 hover:decoration-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-text focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                      >
                        {row.site_id}
                      </button>
                      {small && (
                        <span className="ml-2 text-caption text-borderline">
                          n&lt;{MIN_N_FOR_RATE}
                        </span>
                      )}
                    </th>
                    <td className="py-2 pr-4 font-mono tabular">
                      {formatCounts(row.gradability)}
                    </td>
                    <td className="py-2 pr-4 font-mono tabular">
                      {formatCounts(row.abstention)}
                    </td>
                    <td className="py-2">
                      {row.drift_flag ? (
                        <StatusBadge status="error" label="Drift" />
                      ) : (
                        <span className="text-caption text-text-muted">—</span>
                      )}
                    </td>
                  </tr>
                )
              })}
              <tr className="border-t-2 border-border-subtle">
                <th scope="row" className="py-2 pr-4 text-left font-semibold">
                  Pooled
                </th>
                <td className="py-2 pr-4 font-mono tabular">
                  {data.pooled?.gradability
                    ? formatCounts(data.pooled.gradability)
                    : "no data"}
                </td>
                <td className="py-2 pr-4 text-caption text-text-muted">
                  not pooled
                </td>
                <td className="py-2" />
              </tr>
            </tbody>
          </table>

          {unplotted.length > 0 && (
            <p className="mt-3 text-caption text-text-muted">
              {unplotted.map((r) => r.site_id).join(", ")} have no encounters
              yet, so they appear in the table but not in the plots.
            </p>
          )}
        </CardContent>
      </Card>

      {selected && <SiteDetail siteId={selected} />}
    </Shell>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-display">Sites</h1>
      {children}
    </section>
  )
}

/** One site's registry status. `model_version` is the place Lane A's
 *  "unpinned" sentinel surfaces, and it is rendered as ordinary muted text —
 *  a site awaiting its first audit is normal, not an error. */
function SiteDetail({ siteId }: { siteId: string }) {
  const { data, isLoading, isError } = useSiteStatus(siteId)

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>{siteId} — registry status</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && (
          <p className="text-body text-text-muted">Loading site status…</p>
        )}
        {isError && (
          <div className="flex flex-wrap items-center gap-3">
            <StatusBadge status="error" label="Could not load site status" />
          </div>
        )}
        {data && (
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-caption text-text-muted">Pinned model version</dt>
              <dd
                className={cn(
                  "font-mono text-body",
                  isUnpinned(data.model_version) ? "text-text-muted" : "text-text",
                )}
              >
                {formatModelVersion(data.model_version)}
              </dd>
            </div>
            <div>
              <dt className="text-caption text-text-muted">Last audit</dt>
              <dd className="font-mono text-body text-text">
                {data.last_audit
                  ? new Date(data.last_audit).toLocaleString()
                  : "not audited yet"}
              </dd>
            </div>
            <div>
              <dt className="text-caption text-text-muted">Gradability</dt>
              <dd className="font-mono text-body tabular text-text">
                {formatCounts(data.gradability)}
              </dd>
            </div>
            <div>
              <dt className="text-caption text-text-muted">Drift</dt>
              <dd className="text-body">
                {data.drift_flag ? (
                  <StatusBadge status="error" label="Flagged by latest audit" />
                ) : (
                  <span className="text-text-muted">Not flagged</span>
                )}
              </dd>
            </div>
          </dl>
        )}
        {data && isUnpinned(data.model_version) && (
          <p className="mt-4 max-w-prose text-caption text-text-muted">
            A site must pass a local audit before its grades count. This site
            has not pinned a model version yet.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
