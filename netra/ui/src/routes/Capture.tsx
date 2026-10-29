/**
 * Capture — T-14.
 *
 * Flow: select an image -> hash it ON-DEVICE -> gate verdict -> either the
 * recapture screen (reject) or record the encounter (usable / borderline).
 *
 * The image bytes are never uploaded. Only the SHA-256, the decisions and the
 * metadata go to POST /v1/encounters.
 */

import { useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion, useReducedMotion } from "framer-motion"
import { Camera, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { VerdictPanel } from "@/components/VerdictPanel"
import { StatusBadge } from "@/components/StatusBadge"
import { SCENARIOS, type Scenario } from "@/lib/gateSim"
import { callQualityGate } from "@/lib/qualityGate"
import { shortHash } from "@/lib/sha256"
import { deviceQueue, submitEncounter } from "@/lib/offline/sync"
import { ApiError } from "@/lib/api/client"
import { useEncounter } from "@/state/encounter"
import { cn } from "@/lib/utils"

const SITE_ID = "site-07"

export default function Capture() {
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const reduce = useReducedMotion()
  const { current, setCurrent, patchCurrent } = useEncounter()

  const [hashing, setHashing] = useState(false)
  const [scenarioKey, setScenarioKey] = useState<string>(SCENARIOS[0].key)
  const [error, setError] = useState<string | null>(null)
  const [deviceSeq, setDeviceSeq] = useState(412)
  const [recording, setRecording] = useState(false)
  // True when this capture is on the device and has not reached the server.
  // NOT an error state: offline is the normal condition at a screening camp.
  const [queued, setQueued] = useState(false)

  async function onPick(file: File) {
    setError(null)
    setHashing(true)
    try {
      // The ONLY gate call in the front end. It hashes in the browser and the
      // file object is dropped immediately after; the bytes never leave.
      // Swapping in the real model is a change to callQualityGate, not here.
      const gate = await callQualityGate(file, { simScenarioKey: scenarioKey })
      if (gate.qualityVerdict === null) {
        // The gate could not run. That is not a verdict, so there is nothing
        // to record — POST /v1/encounters has no nullable gate_verdict.
        setError(`The quality gate did not run: ${gate.note}`)
        return
      }
      setCurrent({
        imageSha256: gate.imageSha256,
        verdict: gate.qualityVerdict,
        cause: gate.cause,
        scoreMilli: gate.qualityScoreMilli ?? 0,
        predictionSet: gate.predictionSet,
        modelVersion: gate.modelVersion,
      })
    } catch {
      setError("Could not read that file.")
    } finally {
      setHashing(false)
    }
  }

  async function record(recordAsNoResult: boolean) {
    if (!current) return
    setError(null)
    setRecording(true)
    try {
      // Through the device queue, always. The encounter is written to the
      // queue BEFORE it is sent, with its idempotency key, so a capture taken
      // with no signal is kept and replayed later with that same key (T-19).
      const { response, queued: stillQueued } = await submitEncounter(deviceQueue, {
        image_sha256: current.imageSha256,
        gate_verdict: current.verdict,
        cause: current.cause,
        // A rejected image carries no prediction set. The API rejects it with
        // 422 if we ever send one, and so does the mock.
        prediction_set: recordAsNoResult ? null : current.predictionSet,
        model_version: current.modelVersion,
        site_id: SITE_ID,
        device_seq: deviceSeq,
      })

      setQueued(stillQueued)
      if (response) {
        patchCurrent({
          encounterId: response.encounter_id,
          ledgerIdx: response.ledger_idx,
        })
      }
      // The device owns device_seq, so it advances whether or not the server
      // has seen this one yet.
      setDeviceSeq((n) => n + 1)
    } catch (e) {
      // Only a PERMANENT refusal lands here. submitEncounter queues anything
      // transient instead of throwing.
      setError(e instanceof ApiError ? `${e.status} — ${e.message}` : String(e))
    } finally {
      setRecording(false)
    }
  }

  function retake() {
    setCurrent(null)
    setError(null)
    setQueued(false)
    if (fileRef.current) fileRef.current.value = ""
    fileRef.current?.click()
  }

  const isReject = current?.verdict === "reject"
  // A queued capture IS recorded - on this device, with its key, waiting to
  // sync. Treating it as unrecorded would invite the operator to capture the
  // same patient again.
  const recorded = Boolean(current?.encounterId) || queued

  return (
    <section className="mx-auto max-w-6xl px-4 py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-display">Capture</h1>
        <p className="font-mono text-caption text-text-muted">
          site {SITE_ID} · device_seq {deviceSeq}
        </p>
      </header>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        {/* ------------------------------------------------ capture column */}
        <Card>
          <CardHeader>
            <CardTitle>1 · Take the image</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-body text-text-muted">
              The image is hashed on this device. The picture itself is never
              uploaded — only its hash, the decisions and the metadata.
            </p>

            {/* The visible Button is the control. sr-only alone would leave this
                input in the tab order with no visible focus ring, so a keyboard
                user would land on nothing. */}
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="sr-only"
              tabIndex={-1}
              aria-hidden="true"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void onPick(f)
              }}
            />

            <Button
              size="lg"
              onClick={() => fileRef.current?.click()}
              disabled={hashing}
              className="w-full"
            >
              <Camera aria-hidden="true" className="size-5" />
              {hashing ? "Hashing…" : "Select fundus image"}
            </Button>

            {current && (
              <p
                className="font-mono text-caption text-text-muted"
                title={current.imageSha256}
              >
                sha256 {shortHash(current.imageSha256)}
              </p>
            )}

            {/* Lane C's on-device gate is not wired up yet. Labelled plainly
                so no one mistakes this control for a model. */}
            <fieldset className="rounded-md border border-border-subtle p-3">
              <legend className="px-1 text-caption font-semibold text-borderline">
                Simulated gate — Lane C model not wired yet
              </legend>
              <label
                className="mt-1 block text-caption text-text-muted"
                htmlFor="scenario"
              >
                Scenario applied on the next capture
              </label>
              <select
                id="scenario"
                value={scenarioKey}
                onChange={(e) => setScenarioKey(e.target.value)}
                className="mt-1 h-11 w-full rounded-md border border-border-subtle bg-bg px-2 text-body"
              >
                {SCENARIOS.map((s: Scenario) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </fieldset>
          </CardContent>
        </Card>

        {/* ------------------------------------------------ verdict column */}
        <div className="space-y-6">
          {!current ? (
            <Card className="border-dashed">
              <CardContent className="py-10 text-center text-body text-text-muted">
                No image captured yet.
              </CardContent>
            </Card>
          ) : (
            <>
              <VerdictPanel
                verdict={current.verdict}
                cause={current.cause}
                scoreMilli={current.scoreMilli}
              />

              {/* ------------- REJECT: recapture. No grade. No referral. ---- */}
              {isReject ? (
                <motion.div
                  initial={reduce ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.18 }}
                  className="space-y-4"
                >
                  <Card>
                    <CardHeader>
                      <CardTitle>What to do</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <ol className="list-decimal space-y-1 pl-5 text-body">
                        <li>Re-steady the camera and refocus on the optic disc.</li>
                        <li>Check illumination, then take the image again.</li>
                      </ol>

                      <div className="flex flex-wrap gap-3">
                        {/* Primary action is always "take another". */}
                        <Button size="lg" onClick={retake}>
                          <RotateCcw aria-hidden="true" className="size-5" />
                          Take another image
                        </Button>
                        {/* Quieter, and it records "no result" — never a grade. */}
                        <Button
                          variant="secondary"
                          size="lg"
                          onClick={() => void record(true)}
                          disabled={recording || recorded}
                        >
                          {recorded
                            ? "Recorded as no result"
                            : "Cannot retake — record as no result"}
                        </Button>
                      </div>

                      <p className="max-w-prose text-caption text-text-muted">
                        Recording this does not produce a grade or a referral. It
                        counts only towards this site's gradability denominator.
                      </p>
                    </CardContent>
                  </Card>
                </motion.div>
              ) : (
                /* ------------- USABLE / BORDERLINE: record, then grade ----- */
                <Card>
                  <CardHeader>
                    <CardTitle>2 · Record the encounter</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-body text-text-muted">
                      The decision is appended to the tamper-evident ledger before
                      it comes back to you.
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        size="lg"
                        onClick={() => void record(false)}
                        disabled={recording || recorded}
                      >
                        {recording
                          ? "Recording…"
                          : recorded
                            ? "Recorded"
                            : "Record encounter"}
                      </Button>
                      {recorded && (
                        <Button variant="secondary" size="lg" onClick={() => navigate("/grade")}>
                          View grade
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              )}

              {recorded && queued && (
                <div
                  className="rounded-md border border-border-subtle bg-surface p-3"
                  role="status"
                >
                  <StatusBadge status="pending-sync" label="Saved on this device" />
                  <p className="mt-2 max-w-prose text-caption text-text-muted">
                    No signal, so this capture is queued here and will sync by
                    itself. It carries its own idempotency key, so a retry
                    cannot record it twice. There is no ledger index yet — the
                    server assigns one when it arrives.
                  </p>
                </div>
              )}

              {recorded && !queued && current.encounterId && (
                <p className="font-mono text-caption text-text-muted tabular">
                  encounter {current.encounterId} · ledger idx {current.ledgerIdx}
                </p>
              )}
            </>
          )}

          {error && (
            <div
              className={cn(
                "rounded-md border border-reject bg-surface p-3",
                "flex items-start gap-2",
              )}
              role="alert"
            >
              <StatusBadge status="error" label="Could not record" />
              <p className="text-body text-text">{error}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  )
}
