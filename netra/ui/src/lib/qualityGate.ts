/**
 * THE SEAM. One function, `callQualityGate`, is the only place the real model
 * plugs into the front end. Nothing else in `netra/ui` knows how a verdict is
 * produced.
 *
 * It now calls the REAL model, through the local sidecar
 * (`netra/sidecar/server.py`). `MODEL_LANDING.md` section 5 framed the choice:
 * `infer.py` is Python, the gate runs on-device, and the nine `/v1` endpoints
 * are frozen with none of them grading an image - so it is either in-browser
 * ONNX/WASM or a local sidecar, and this is the sidecar. The image crosses
 * `localhost` and nothing else; `SPEC.md`'s rule that it never leaves the
 * device still holds.
 *
 * If the sidecar is not running, this falls back to the simulated gate and
 * says so in `modelVersion` and `note`. A demo must never hard-fail - but it
 * must never quietly claim a measurement either, so the fallback is labelled
 * everywhere it surfaces. `isSimulatedGate` is what the UI reads.
 *
 * `GateResult` is deliberately field-for-field equivalent to
 * `netra.models.infer.InferenceResult` (camelCase here, snake_case there):
 *
 *   image_sha256         -> imageSha256
 *   quality_verdict      -> qualityVerdict   (null when the gate could not run)
 *   cause                -> cause
 *   prediction_set       -> predictionSet    (null when there is no result)
 *   grade                -> grade
 *   abstain              -> abstain
 *   model_version        -> modelVersion     ("unloaded" when a model is gone)
 *   quality_score_milli  -> qualityScoreMilli
 *   note                 -> note
 *
 * Two invariants hold whatever the implementation is, and `assertGateResult`
 * below enforces them on the way out rather than trusting the caller. They
 * matter MORE now than they did against the simulation, because the thing on
 * the other side is a real model and can be wrong:
 *
 *  1. A `reject` carries NO prediction set and NO grade. A failed quality gate
 *     is "no result", never a negative DR result (BUILD_RULES.md invariant 1).
 *     Lane A returns 422 if a reject ever arrives carrying a set.
 *  2. A score is a scaled integer (per mille), never a float. Floats are
 *     banned from ledger payloads, and this value travels towards one.
 */

import { singleGrade, spansClinicalActions } from "./clinical"
import { SCENARIOS, SIM_MODEL_VERSION } from "./gateSim"
import type { GateVerdict, Grade } from "./api/types"
import { sha256Hex } from "./sha256"

/** Mirrors `netra.models.infer.InferenceResult`. See the module docstring. */
export interface GateResult {
  imageSha256: string
  /** usable | borderline | reject, or null when the gate could not run. */
  qualityVerdict: GateVerdict | null
  /** focus | exposure | fov_mask, or null. */
  cause: string | null
  /** The conformal set, or null when there is no result. NEVER `[]` — an empty
   *  array reads as a graded empty set. */
  predictionSet: Grade[] | null
  /** The single grade, or null whenever the set is not a singleton. */
  grade: Grade | null
  abstain: boolean
  /** `unloaded` when a model is missing; `simulated-*` on the fallback. */
  modelVersion: string
  /** P(usable) x 1000. A scaled integer — no floats near the ledger. */
  qualityScoreMilli: number | null
  /** Why this result looks the way it does, in one line. */
  note: string
}

/**
 * Where the sidecar listens. Loopback by default and in practice always: the
 * sidecar itself binds `127.0.0.1` and refuses a non-local `Origin`, so
 * pointing this elsewhere cannot send a fundus image off the device.
 */
const SIDECAR_BASE =
  import.meta.env.VITE_GATE_SIDECAR || "http://127.0.0.1:8731"

/** Long enough for a cold CPU forward pass, short enough to fall back during
 *  a demo rather than hang the capture screen. */
const GATE_TIMEOUT_MS = 20_000
const HEALTH_TIMEOUT_MS = 1_500

/** Simulation-only, and now only reachable via the fallback. Kept so a
 *  deliberate scenario can still be driven in tests and with no sidecar. */
export interface GateOptions {
  simScenarioKey?: string
  /** Skip the sidecar entirely. Tests use this; the capture screen does not. */
  forceSimulated?: boolean
}

export class GateResultError extends Error {}

/** True for a `modelVersion` the simulation produced, not a model. Pulled out
 *  of `isSimulatedGate` so a screen holding only the model version string
 *  (e.g. from `CurrentCase`, after the full `GateResult` is gone) can still
 *  ask the same question without reconstructing one. */
export function isSimulatedModelVersion(modelVersion: string): boolean {
  return modelVersion.startsWith("simulated")
}

/** True when this result came from the simulation, not a model. The capture
 *  screen reads this to label the screen, so it can never go unsaid. */
export function isSimulatedGate(result: GateResult): boolean {
  return isSimulatedModelVersion(result.modelVersion)
}

/** What `GET /health` on the sidecar returns. Not a `/v1` schema. */
export interface GateHealth {
  reachable: boolean
  modelVersion: string | null
  gateLoaded: boolean
  classifierLoaded: boolean
  conformalized: boolean
  detail: string | null
}

const UNREACHABLE: GateHealth = {
  reachable: false,
  modelVersion: null,
  gateLoaded: false,
  classifierLoaded: false,
  conformalized: false,
  detail: "the gate sidecar is not running",
}

/**
 * Ask the sidecar what it has loaded, for display only.
 *
 * Never throws: an unreachable sidecar is a normal state (it is a separate
 * process an operator has to start), not an error.
 */
export async function probeGateSidecar(): Promise<GateHealth> {
  try {
    const res = await fetch(`${SIDECAR_BASE}/health`, {
      signal: AbortSignal.timeout(HEALTH_TIMEOUT_MS),
    })
    if (!res.ok) return { ...UNREACHABLE, detail: `sidecar returned ${res.status}` }
    const body = await res.json()
    return {
      reachable: true,
      modelVersion: body.model_version ?? null,
      gateLoaded: Boolean(body.gate_loaded),
      classifierLoaded: Boolean(body.classifier_loaded),
      conformalized: Boolean(body.conformalized),
      detail: body.gate_error ?? body.classifier_error ?? null,
    }
  } catch {
    return UNREACHABLE
  }
}

/** The sidecar's snake_case `InferenceResult` as it arrives over the wire. */
interface WireResult {
  image_sha256: string
  quality_verdict: GateVerdict | null
  cause: string | null
  prediction_set: number[] | null
  grade: number | null
  abstain: boolean
  model_version: string
  quality_score_milli: number | null
  note: string
}

/** snake_case -> camelCase, and nothing else. The shapes already match. */
function fromWire(wire: WireResult): GateResult {
  return {
    imageSha256: wire.image_sha256,
    qualityVerdict: wire.quality_verdict,
    cause: wire.cause,
    predictionSet: (wire.prediction_set as Grade[] | null) ?? null,
    grade: (wire.grade as Grade | null) ?? null,
    abstain: Boolean(wire.abstain),
    modelVersion: wire.model_version,
    qualityScoreMilli: wire.quality_score_milli,
    note: wire.note,
  }
}

/**
 * Run the quality gate on one captured image.
 *
 * The image bytes go to the local sidecar and nowhere else. The hash is
 * computed here as well as there, and the two are compared: they are hashes of
 * the same bytes, so a mismatch means something re-encoded the image on the
 * way, and the hash this app is about to write into a ledger would not be the
 * hash of what the model actually graded.
 */
export async function callQualityGate(
  file: File,
  options: GateOptions = {},
): Promise<GateResult> {
  const imageSha256 = await sha256Hex(file)

  if (options.forceSimulated) {
    return simulatedGate(imageSha256, options, "simulation requested")
  }

  try {
    const res = await fetch(`${SIDECAR_BASE}/gate`, {
      method: "POST",
      // The raw bytes, not a multipart form: the sidecar's whole parse is
      // `read(Content-Length)`.
      body: file,
      headers: { "Content-Type": file.type || "application/octet-stream" },
      signal: AbortSignal.timeout(GATE_TIMEOUT_MS),
    })

    if (!res.ok) {
      // The sidecar is there but could not grade this image (a decode
      // failure, say). That is "the gate did not run" - a real answer, and
      // NOT a reason to substitute a simulated verdict for it.
      let detail = `sidecar returned ${res.status}`
      try {
        const body = await res.json()
        if (body?.error) detail = String(body.error)
      } catch {
        /* a non-JSON body; the status is all there is to say */
      }
      return assertGateResult({
        imageSha256,
        qualityVerdict: null,
        cause: null,
        predictionSet: null,
        grade: null,
        abstain: false,
        modelVersion: "unloaded",
        qualityScoreMilli: null,
        note: `the gate could not grade this image: ${detail}`,
      })
    }

    const result = fromWire((await res.json()) as WireResult)

    if (result.imageSha256 !== imageSha256) {
      throw new GateResultError(
        "the gate hashed different bytes than this device did " +
          `(${result.imageSha256.slice(0, 12)} vs ${imageSha256.slice(0, 12)}): ` +
          "the hash bound to this encounter would not be the image that was graded",
      )
    }

    return assertGateResult(result)
  } catch (err) {
    // A broken invariant is NOT a connectivity problem, and must not be
    // swallowed into a fallback - that is the one failure the seam exists to
    // make loud.
    if (err instanceof GateResultError) throw err
    return simulatedGate(
      imageSha256,
      options,
      `the gate sidecar is unreachable (${describe(err)})`,
    )
  }
}

function describe(err: unknown): string {
  if (err instanceof DOMException && err.name === "TimeoutError") {
    return `no answer in ${GATE_TIMEOUT_MS / 1000}s`
  }
  return err instanceof Error ? err.message : String(err)
}

/**
 * The labelled fallback. Returns an operator-chosen scenario rather than a
 * fake model: a fake model invites someone to mistake its output for a
 * measurement. Nothing here produces a number that is ever reported, and
 * `modelVersion` says `simulated-*` so `isSimulatedGate` can surface it.
 */
function simulatedGate(
  imageSha256: string,
  options: GateOptions,
  why: string,
): GateResult {
  const sc =
    SCENARIOS.find((s) => s.key === options.simScenarioKey) ?? SCENARIOS[0]

  return assertGateResult({
    imageSha256,
    qualityVerdict: sc.verdict,
    cause: sc.cause,
    predictionSet: sc.predictionSet,
    grade: sc.predictionSet === null ? null : singleGrade(sc.predictionSet),
    abstain:
      sc.predictionSet !== null && spansClinicalActions(sc.predictionSet),
    modelVersion: SIM_MODEL_VERSION,
    qualityScoreMilli: sc.scoreMilli,
    note: `SIMULATED scenario ${sc.key} — ${why}; this is not a measurement`,
  })
}

/**
 * Enforce the two invariants on the way out of the seam.
 *
 * This guards the REAL implementation as much as the simulation: a misbehaving
 * on-device model must fail here, loudly, rather than send a graded reject to
 * `POST /v1/encounters` and be turned into a 422 the operator cannot read.
 */
export function assertGateResult(result: GateResult): GateResult {
  const { qualityVerdict, predictionSet, grade, qualityScoreMilli } = result

  if (qualityVerdict === "reject" && predictionSet !== null) {
    throw new GateResultError(
      "a rejected image carries no prediction set: a failed quality gate is " +
        '"no result", never a negative DR result',
    )
  }
  if (qualityVerdict === "reject" && grade !== null) {
    throw new GateResultError("a rejected image carries no grade")
  }
  if (qualityVerdict === null && (predictionSet !== null || grade !== null)) {
    throw new GateResultError(
      "the gate did not run, so there is no result to report",
    )
  }
  if (predictionSet !== null && predictionSet.length === 0) {
    throw new GateResultError(
      "an empty prediction set reads as a graded empty set; use null for " +
        '"no result"',
    )
  }
  if (qualityScoreMilli !== null && !Number.isInteger(qualityScoreMilli)) {
    throw new GateResultError(
      `quality score must be a scaled integer (per mille), got ${qualityScoreMilli}`,
    )
  }
  return result
}

/** True when there is no result to show: the gate rejected, or never ran. */
export function isNoResult(result: GateResult): boolean {
  return result.qualityVerdict === "reject" || result.qualityVerdict === null
}
