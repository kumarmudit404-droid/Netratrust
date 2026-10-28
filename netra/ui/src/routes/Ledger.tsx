/**
 * Ledger — T-17. Verification, the signed checkpoint, and the tamper demo.
 *
 * SPEC.md section 7 requires this view to CARRY the tamper demo, not merely
 * offer a verify button: "A verify button that has only ever returned ok:true
 * does not demonstrate tamper-evidence."
 *
 * There is no corrupt-the-ledger endpoint, by design — the nine endpoints are
 * frozen and a route that rewrites history would be a liability in a deployed
 * build. The corruption step is a CLI the presenter runs:
 *
 *     python -m netra.ledger.tamper --seq 2
 *
 * So this screen's job is to make the transition legible across that step:
 * a prominent Verify, an optional re-check loop so the flip happens on screen,
 * and a session history so ok:true → ok:false is visible as a TRANSITION
 * rather than as a value that was always false.
 */

import { useCallback, useEffect, useRef, useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { CheckCircle2, ShieldAlert, Stamp, Terminal } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatusBadge } from "@/components/StatusBadge"
import { useCheckpoint, useLedgerVerify } from "@/lib/api/queries"
import {
  describeHistoryEntry,
  isAlarming,
  verifyDisplay,
  verifyExplainer,
  verifyHeadline,
  verifyStatus,
  type VerifyHistoryEntry,
} from "@/lib/ledgerState"
import { shortHash } from "@/lib/sha256"
import { cn } from "@/lib/utils"

/** Fast enough that the CLI step and the flip feel connected on stage. */
const RECHECK_MS = 3000
const HISTORY_MAX = 6

export default function Ledger() {
  const [hasRun, setHasRun] = useState(false)
  const [recheck, setRecheck] = useState(false)
  const [history, setHistory] = useState<VerifyHistoryEntry[]>([])

  const verify = useLedgerVerify({
    enabled: hasRun,
    pollMs: recheck ? RECHECK_MS : false,
  })
  const checkpoint = useCheckpoint()

  const display = verifyDisplay({
    data: verify.data,
    isFetching: verify.isFetching,
    isError: verify.isError,
    error: verify.error,
    hasRun,
  })

  // Record each distinct result, keyed on the fetch timestamp so a poll that
  // returns the same answer does not spam the list.
  const lastRecorded = useRef<number>(0)
  useEffect(() => {
    if (!verify.data || !verify.dataUpdatedAt) return
    if (verify.dataUpdatedAt === lastRecorded.current) return
    lastRecorded.current = verify.dataUpdatedAt
    setHistory((h) =>
      [
        {
          at: verify.dataUpdatedAt,
          ok: verify.data!.ok,
          firstBadIndex: verify.data!.first_bad_index,
        },
        ...h,
      ].slice(0, HISTORY_MAX),
    )
  }, [verify.data, verify.dataUpdatedAt])

  const run = useCallback(() => {
    if (!hasRun) setHasRun(true)
    else void verify.refetch()
  }, [hasRun, verify])

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="text-display">Ledger</h1>
      <p className="mt-2 max-w-prose text-body text-text-muted">
        Every clinical decision is appended to a hash chain before it is
        returned to the operator, and each entry is signed. Verification
        re-walks the whole chain and recomputes it — it does not trust a stored
        flag.
      </p>

      <VerifyPanel
        display={display}
        onRun={run}
        running={verify.isFetching}
        recheck={recheck}
        onToggleRecheck={() => setRecheck((r) => !r)}
      />

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <HistoryCard history={history} />
        <TamperDemoCard />
      </div>

      <CheckpointCard
        data={checkpoint.data}
        isLoading={checkpoint.isLoading}
        isError={checkpoint.isError}
      />
    </section>
  )
}

/* ------------------------------------------------------------- verify panel */

function VerifyPanel({
  display,
  onRun,
  running,
  recheck,
  onToggleRecheck,
}: {
  display: ReturnType<typeof verifyDisplay>
  onRun: () => void
  running: boolean
  recheck: boolean
  onToggleRecheck: () => void
}) {
  const reduce = useReducedMotion()
  const alarming = isAlarming(display)
  const ok = display.kind === "ok"
  const Icon = alarming ? ShieldAlert : ok ? CheckCircle2 : Stamp

  return (
    <motion.section
      // State transition only, <= 200ms, honours prefers-reduced-motion.
      key={display.kind}
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      aria-live="polite"
      className={cn(
        "mt-6 rounded-lg border border-border-subtle border-l-4 bg-surface p-5",
        alarming && "border-l-reject",
        ok && "border-l-usable",
        !alarming && !ok && "border-l-border-subtle",
      )}
    >
      <div className="flex flex-wrap items-start gap-4">
        <h2
          className={cn(
            "flex items-center gap-3 text-display",
            alarming && "text-reject",
            ok && "text-usable",
            !alarming && !ok && "text-text",
          )}
        >
          <Icon aria-hidden="true" className="size-8 shrink-0" />
          {verifyHeadline(display)}
        </h2>

        <div className="ml-auto flex flex-wrap items-center gap-3">
          <Button size="lg" onClick={onRun} disabled={running}>
            {running ? "Verifying…" : "Verify the chain"}
          </Button>
          <label className="flex items-center gap-2 text-body text-text-muted">
            <input
              type="checkbox"
              checked={recheck}
              onChange={onToggleRecheck}
              className="size-5 accent-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-text focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
            />
            Re-check every {RECHECK_MS / 1000}s
          </label>
        </div>
      </div>

      <p className="mt-3 max-w-prose text-[18px] leading-relaxed text-text">
        {verifyExplainer(display)}
      </p>

      {display.kind === "tampered" && (
        <p className="mt-3 font-mono text-body tabular text-reject">
          first_bad_index = {display.firstBadIndex}
        </p>
      )}

      {display.kind === "error" && (
        <p className="mt-3 text-body text-text-muted">{display.message}</p>
      )}

      <div className="mt-4">
        <StatusBadge
          status={verifyStatus(display)}
          label={
            display.kind === "tampered"
              ? `ok: false · first_bad_index: ${display.firstBadIndex}`
              : display.kind === "ok"
                ? "ok: true · first_bad_index: null"
                : verifyHeadline(display)
          }
        />
      </div>
    </motion.section>
  )
}

/* ----------------------------------------------------------------- history */

function HistoryCard({ history }: { history: VerifyHistoryEntry[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>This session's checks</CardTitle>
      </CardHeader>
      <CardContent>
        {history.length === 0 ? (
          <p className="text-body text-text-muted">
            No check run yet. The list below is what makes the demo convincing:
            the same button returning <code>ok: true</code>, then{" "}
            <code>ok: false</code> after one entry is corrupted.
          </p>
        ) : (
          <ol className="space-y-2">
            {history.map((e) => (
              <li
                key={e.at}
                className="flex flex-wrap items-baseline gap-x-3 border-b border-border-subtle pb-2 last:border-0 last:pb-0"
              >
                <span className="font-mono text-caption text-text-muted tabular">
                  {new Date(e.at).toLocaleTimeString()}
                </span>
                <span
                  className={cn(
                    "font-mono text-body",
                    e.ok ? "text-usable" : "text-reject",
                  )}
                >
                  {describeHistoryEntry(e)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

/* ------------------------------------------------------------ tamper demo */

function TamperDemoCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Terminal aria-hidden="true" className="size-5 shrink-0" />
          The tamper demo
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="max-w-prose text-body text-text">
          There is <strong>no endpoint</strong> that corrupts the ledger, and
          there will not be one — the nine endpoints are frozen, and a route
          that rewrites history would be a liability in a deployed build.
        </p>
        <ol className="list-decimal space-y-2 pl-5 text-body">
          <li>Record a few encounters, then press Verify. Expect ok: true.</li>
          <li>
            Turn on <em>Re-check</em> above, then run this on the server:
            <code className="mt-1 block overflow-x-auto rounded-md border border-border-subtle bg-bg px-2 py-1 font-mono text-caption">
              python -m netra.ledger.tamper --seq 2
            </code>
          </li>
          <li>
            Watch this screen flip to <code>ok: false</code> naming entry 2.
          </li>
        </ol>
        <p className="max-w-prose text-caption text-text-muted">
          The command drops the table's append-only trigger, edits one entry and
          puts the trigger back. That is the honest threat model: the triggers
          stop the application from rewriting history, and the hash chain plus
          the signatures are what survive someone with database access.
        </p>
      </CardContent>
    </Card>
  )
}

/* -------------------------------------------------------------- checkpoint */

function CheckpointCard({
  data,
  isLoading,
  isError,
}: {
  data?: {
    idx: number
    head_hash: string
    ts: string
    signature: string
    signer_kid: string
  }
  isLoading: boolean
  isError: boolean
}) {
  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Signed checkpoint</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-4 max-w-prose text-body text-text-muted">
          A checkpoint is a signature over the chain's head. An outside party
          holding yesterday's checkpoint can prove history was rewritten — which
          a bare chain cannot, because a tamperer with the database can re-sign
          every entry after the edit and make verification pass again.
        </p>

        {isLoading && <p className="text-body text-text-muted">Loading checkpoint…</p>}
        {isError && <StatusBadge status="error" label="Could not load the checkpoint" />}

        {data && (
          <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
            <Field label="Head index">
              <span className="tabular">{data.idx}</span>
            </Field>
            <Field label="Signed at">
              {data.ts ? new Date(data.ts).toLocaleString() : "—"}
            </Field>
            <Field label="Head hash">
              <span title={data.head_hash}>{shortHash(data.head_hash, 16, 8)}</span>
            </Field>
            <Field label="Signer key id">{data.signer_kid}</Field>
            <div className="sm:col-span-2">
              <dt className="text-caption text-text-muted">Signature</dt>
              <dd
                className="break-all font-mono text-caption text-text"
                title={data.signature}
              >
                {shortHash(data.signature, 32, 16)}
              </dd>
            </div>
          </dl>
        )}
      </CardContent>
    </Card>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-caption text-text-muted">{label}</dt>
      <dd className="font-mono text-body text-text">{children}</dd>
    </div>
  )
}
