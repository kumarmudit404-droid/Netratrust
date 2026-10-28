/**
 * Referrals — the current referral and its state machine.
 *
 * SPEC.md section 7: "referrals and their current state; actions follow the
 * state machine at the end of the API contract and nothing else."
 *
 * An honest limitation, stated on screen rather than hidden: there is **no
 * list endpoint** in the frozen nine and none will be added, so this view can
 * only show the referral raised in THIS session, tracked from the create and
 * patch responses. The ledger is the durable record; this screen is the
 * operator's working view of one case.
 */

import { useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { Check, CircleSlash } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/StatusBadge"
import { ApiError } from "@/lib/api/client"
import { usePatchReferral } from "@/lib/api/queries"
import {
  HAPPY_PATH,
  actionLabel,
  allowedTransitions,
  canSubmit,
  isTerminal,
  pathIndex,
  requiresChannel,
  requiresReason,
  stateLabel,
} from "@/lib/referralMachine"
import { useEncounter } from "@/state/encounter"
import type { ReferralState } from "@/lib/api/types"
import { cn } from "@/lib/utils"

const CHANNELS = ["phone", "sms", "home visit", "community health worker"]

export default function Referrals() {
  const { current, patchCurrent } = useEncounter()

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-display">Referrals</h1>

      {!current?.referralId || !current.referralState ? (
        <EmptyState hasCase={Boolean(current)} />
      ) : (
        <ReferralDetail
          referralId={current.referralId}
          state={current.referralState}
          encounterId={current.encounterId}
          onAdvanced={(state) => patchCurrent({ referralState: state })}
        />
      )}
    </section>
  )
}

function EmptyState({ hasCase }: { hasCase: boolean }) {
  return (
    <Card className="mt-6 border-dashed">
      <CardContent className="space-y-3 py-10">
        <p className="text-subhead text-text">No referral in this session.</p>
        <p className="max-w-prose text-body text-text-muted">
          {hasCase
            ? "The case on screen has not had a referral issued. Issue one from the Grade view if its grade is referable."
            : "Capture an image and grade it first. A referral can only be issued for a referable grade — never from a rejected image, and never from an abstention, where a clinician decides."}
        </p>
        <p className="max-w-prose text-caption text-text-muted">
          This view shows the referral raised in this session only. The API has
          no endpoint that lists referrals, and the nine endpoints are frozen —
          the durable record is the ledger, not this screen.
        </p>
      </CardContent>
    </Card>
  )
}

function ReferralDetail({
  referralId,
  state,
  encounterId,
  onAdvanced,
}: {
  referralId: string
  state: ReferralState
  encounterId?: string
  onAdvanced: (state: ReferralState) => void
}) {
  const reduce = useReducedMotion()
  const patch = usePatchReferral(referralId)
  const [target, setTarget] = useState<ReferralState | null>(null)
  const [channel, setChannel] = useState(CHANNELS[0])
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [lastLedgerIdx, setLastLedgerIdx] = useState<number | null>(null)

  const transitions = allowedTransitions(state)
  const terminal = isTerminal(state)

  async function submit(to: ReferralState) {
    setError(null)
    try {
      const res = await patch.mutateAsync({
        to_state: to,
        channel: requiresChannel(to) ? channel : null,
        reason: requiresReason(to) ? reason.trim() : null,
      })
      onAdvanced(res.state)
      setLastLedgerIdx(res.ledger_idx)
      setTarget(null)
      setReason("")
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.status} — ${e.message}`
          : "Could not advance the referral.",
      )
    }
  }

  return (
    <>
      <motion.div
        key={state}
        initial={reduce ? false : { opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: "easeOut" }}
        className={cn(
          "mt-6 rounded-lg border border-border-subtle border-l-4 bg-surface p-5",
          state === "examined" && "border-l-usable",
          state === "abandoned" && "border-l-border-subtle",
          !terminal && "border-l-text",
        )}
        aria-live="polite"
      >
        <h2 className="flex items-center gap-3 text-display text-text">
          {state === "examined" && (
            <Check aria-hidden="true" className="size-8 shrink-0 text-usable" />
          )}
          {state === "abandoned" && (
            <CircleSlash
              aria-hidden="true"
              className="size-8 shrink-0 text-text-muted"
            />
          )}
          {stateLabel(state)}
        </h2>
        <p className="mt-2 font-mono text-caption text-text-muted">
          referral {referralId}
          {encounterId && ` · encounter ${encounterId}`}
          {lastLedgerIdx !== null && ` · ledger idx ${lastLedgerIdx}`}
        </p>

        <Progress state={state} />

        {terminal && (
          <p className="mt-4 max-w-prose text-body text-text-muted">
            {state === "examined"
              ? "This referral is complete. Terminal states accept no further transitions."
              : "This referral was abandoned. Terminal states accept no further transitions."}
          </p>
        )}
      </motion.div>

      {!terminal && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Next step</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="max-w-prose text-body text-text-muted">
              Only the transitions the state machine allows are offered. The
              server enforces the same rules and refuses anything else with a
              409.
            </p>

            <div className="flex flex-wrap gap-3">
              {transitions.map((to) => (
                <Button
                  key={to}
                  variant={to === "abandoned" ? "secondary" : "primary"}
                  onClick={() => {
                    // A move that needs no extra field goes straight through;
                    // the others open their field first.
                    if (requiresChannel(to) || requiresReason(to)) setTarget(to)
                    else void submit(to)
                  }}
                  disabled={patch.isPending}
                  aria-expanded={
                    requiresChannel(to) || requiresReason(to)
                      ? target === to
                      : undefined
                  }
                >
                  {actionLabel(to)}
                </Button>
              ))}
            </div>

            {target && requiresChannel(target) && (
              <div>
                <label
                  htmlFor="channel"
                  className="block text-caption text-text-muted"
                >
                  Channel (required)
                </label>
                <select
                  id="channel"
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                  className="mt-1 h-11 w-full max-w-sm rounded-md border border-border-subtle bg-bg px-2 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-text focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                >
                  {CHANNELS.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {target && requiresReason(target) && (
              <div>
                <label
                  htmlFor="reason"
                  className="block text-caption text-text-muted"
                >
                  Reason (required)
                </label>
                <input
                  id="reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. moved away, declined"
                  className="mt-1 h-11 w-full max-w-sm rounded-md border border-border-subtle bg-bg px-2 text-body focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-text focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                />
              </div>
            )}

            {target && (
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => void submit(target)}
                  disabled={
                    patch.isPending || !canSubmit(state, target, channel, reason)
                  }
                >
                  {patch.isPending ? "Recording…" : `Confirm — ${stateLabel(target)}`}
                </Button>
                <Button variant="ghost" onClick={() => setTarget(null)}>
                  Cancel
                </Button>
              </div>
            )}

            <p className="max-w-prose text-caption text-text-muted">
              Every transition is appended to the ledger before it returns.
            </p>

            {error && (
              <div
                role="alert"
                className="flex flex-wrap items-center gap-3 rounded-md border border-reject bg-surface p-3"
              >
                <StatusBadge status="error" label="Could not advance" />
                <p className="text-body text-text">{error}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </>
  )
}

/** Where this referral sits on the happy path. `abandoned` is off the path, so
 *  it is never shown as the final successful step. */
function Progress({ state }: { state: ReferralState }) {
  const here = pathIndex(state)

  if (here === null) {
    return (
      <p className="mt-4 text-body text-text-muted">
        Ended off the referral path.
      </p>
    )
  }

  return (
    <ol className="mt-4 flex flex-wrap gap-2" aria-label="Referral progress">
      {HAPPY_PATH.map((s, i) => (
        <li
          key={s}
          aria-current={i === here ? "step" : undefined}
          className={cn(
            "rounded-md border px-2 py-1 text-caption",
            i < here && "border-border-subtle text-text-muted",
            i === here && "border-text font-semibold text-text",
            i > here && "border-border-subtle text-text-muted opacity-60",
          )}
        >
          {/* The step number is text, so progress is never colour-only. */}
          {i + 1}. {stateLabel(s)}
          {i < here && " ✓"}
        </li>
      ))}
    </ol>
  )
}
