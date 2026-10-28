/**
 * Grade / Abstain — T-15.
 *
 * Shows the conformal prediction set and then one of two outcomes:
 *   - a grade, when the set sits inside a single clinical action class;
 *   - ABSTAIN — "a doctor should check this" — when it spans refer and
 *     do-not-refer. Set SIZE is never the trigger.
 *
 * A rejected image never reaches this screen: it has no result to show.
 */

import { Link } from "react-router-dom"
import { motion, useReducedMotion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge, STATUS } from "@/components/StatusBadge"
import { PredictionSet } from "@/components/PredictionSet"
import { isReferable, singleGrade, spansClinicalActions } from "@/lib/clinical"
import { shortHash } from "@/lib/sha256"
import { useCreateReferral, useQueueDepth } from "@/lib/api/queries"
import { ApiError } from "@/lib/api/client"
import { useEncounter } from "@/state/encounter"
import { cn } from "@/lib/utils"
import { useState } from "react"

// Taken from the one status table so this screen never re-decides a treatment.
const AbstainIcon = STATUS.abstain.Icon
const GradeIcon = STATUS.grade.Icon

export default function Grade() {
  const { current, patchCurrent } = useEncounter()
  const reduce = useReducedMotion()
  const createReferral = useCreateReferral()
  const queueDepth = useQueueDepth()
  const [error, setError] = useState<string | null>(null)

  // --- nothing to show -----------------------------------------------------
  if (!current) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-display">Grade</h1>
        <Card className="mt-6 border-dashed">
          <CardContent className="space-y-4 py-10 text-center">
            <p className="text-body text-text-muted">No encounter in progress.</p>
            <Link
              to="/capture"
              className="inline-block text-body font-semibold text-text underline"
            >
              Go to Capture
            </Link>
          </CardContent>
        </Card>
      </section>
    )
  }

  // A reject is "no result" — never a grade, never a referral.
  if (current.verdict === "reject" || current.predictionSet === null) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="text-display">Grade</h1>
        <Card className="mt-6 border border-reject">
          <CardContent className="space-y-4 py-8">
            <StatusBadge status="reject" />
            <p className="max-w-prose text-[18px] text-text">
              This image could not be graded, so there is no result to show. This
              is <strong>not</strong> a negative result — the patient has not been
              screened yet.
            </p>
            <Link
              to="/capture"
              className="inline-block text-body font-semibold text-text underline"
            >
              Take another image
            </Link>
          </CardContent>
        </Card>
      </section>
    )
  }

  const set = current.predictionSet
  const abstain = spansClinicalActions(set)
  const grade = singleGrade(set)
  const referable = !abstain && set.every(isReferable)
  const referred = Boolean(current.referralId)

  async function refer() {
    if (!current?.encounterId) return
    setError(null)
    try {
      const res = await createReferral.mutateAsync(current.encounterId)
      patchCurrent({ referralId: res.referral_id, referralState: res.state })
    } catch (e) {
      setError(
        e instanceof ApiError ? `${e.status} — ${e.message}` : "Could not issue referral.",
      )
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-display">Grade</h1>
        <p className="font-mono text-caption text-text-muted" title={current.imageSha256}>
          sha256 {shortHash(current.imageSha256)} · {current.modelVersion}
        </p>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        {/* ------------------------------------------------- the outcome --- */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          aria-live="polite"
        >
          {abstain ? (
            <section
              className={cn(
                "rounded-lg border-l-4 border bg-surface p-5",
                STATUS.abstain.border,
              )}
            >
              {/* Same weight as a Reject verdict and as a Grade: design.md §1 —
                  refusal is a first-class state, so it gets the display headline,
                  not a caption-sized badge over a paragraph. */}
              <h2 className={cn("flex items-center gap-3 text-display", STATUS.abstain.fg)}>
                <AbstainIcon aria-hidden="true" className="size-8 shrink-0" />
                A doctor should check this.
              </h2>
              <p className="mt-3 max-w-prose text-[18px] leading-relaxed text-text">
                The prediction set spans two different clinical actions — it holds
                both referable and non-referable grades — so the model is not
                confident enough to decide. It has been routed for specialist
                review rather than graded.
              </p>
              <p className="mt-3 max-w-prose text-caption text-text-muted">
                This is an abstention, not a failure, and not a negative result.
              </p>
            </section>
          ) : (
            <section
              className={cn(
                "rounded-lg border-l-4 border bg-surface p-5",
                STATUS.grade.border,
              )}
            >
              <h2 className={cn("flex items-center gap-3 text-display", STATUS.grade.fg)}>
                <GradeIcon aria-hidden="true" className="size-8 shrink-0" />
                {grade !== null ? `Grade ${grade}` : "Single action class"}
              </h2>
              <p className="mt-3 max-w-prose text-[22px] font-semibold leading-snug text-text">
                {referable
                  ? "Refer this patient."
                  : "No referral needed from this image."}
              </p>
              <p className="mt-3 max-w-prose text-body text-text">
                {referable
                  ? "Every grade in the prediction set is referable (moderate NPDR or worse), so the action is unambiguous even where the exact grade is not."
                  : "Every grade in the prediction set is below the referral threshold."}
              </p>
              {current.verdict === "borderline" && (
                <p className="mt-3 max-w-prose text-caption text-borderline">
                  Image quality was borderline — treat this grade as provisional and
                  retake if you can.
                </p>
              )}
            </section>
          )}
        </motion.div>

        {/* ------------------------------------------------ the set + act -- */}
        <div className="space-y-6">
          <Card>
            <CardContent className="pt-4">
              <PredictionSet set={set} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Next step</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {abstain ? (
                <>
                  <p className="text-body text-text-muted">
                    In the specialist queue. No referral is issued from an abstention —
                    a clinician decides.
                  </p>
                  {/* SPEC §7: the abstain state shows the pending count from
                      GET /v1/queue/depth. This is the DEVICE's unsynced-record
                      depth — the same figure as the TopNav strip — not a count of
                      cases a specialist has yet to read. Said in those words so
                      no one reads it as a clinical backlog we have not measured. */}
                  {queueDepth.data && (
                    <p className="text-caption text-text-muted tabular">
                      {queueDepth.data.queued} record
                      {queueDepth.data.queued === 1 ? "" : "s"} on this device still
                      waiting to sync.
                    </p>
                  )}
                </>
              ) : referable ? (
                <>
                  <Button
                    size="lg"
                    onClick={() => void refer()}
                    disabled={createReferral.isPending || referred || !current.encounterId}
                  >
                    {createReferral.isPending
                      ? "Issuing…"
                      : referred
                        ? "Referral issued"
                        : "Issue referral"}
                  </Button>
                  {referred && (
                    <p className="font-mono text-caption text-text-muted">
                      referral {current.referralId} · state issued
                    </p>
                  )}
                </>
              ) : (
                <p className="text-body text-text-muted">
                  Nothing to do. The encounter is recorded.
                </p>
              )}

              {!current.encounterId && (
                <p className="text-caption text-borderline">
                  This encounter has not been recorded yet — go back to Capture and
                  record it before issuing a referral.
                </p>
              )}

              {error && (
                <div role="alert" className="flex items-start gap-2">
                  <StatusBadge status="error" label="Failed" />
                  <p className="text-body text-text">{error}</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Lane C owns the overlay; the screen reads correctly without it. */}
          <p className="text-caption text-text-muted">
            Grad-CAM overlay is a Lane C stretch task (T-20) and is not shown.
          </p>
        </div>
      </div>
    </section>
  )
}
