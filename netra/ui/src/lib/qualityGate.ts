/**
 * THE SEAM. One function, `callQualityGate`, is the only place the real model
 * plugs into the front end. Nothing else in `netra/ui` knows how a verdict is
 * produced.
 *
 * Today it returns an operator-chosen scenario from `gateSim.ts`. When Lane C's
 * artifacts land, the body of `callQualityGate` is replaced and every screen
 * keeps working unchanged — that is the whole point of routing it through here
 * instead of letting `Capture.tsx` reach into `SCENARIOS` directly.
 *
 * `GateResult` is deliberately field-for-field equivalent to
 * `netra.models.infer.InferenceResult` (camelCase here, snake_case there), so
 * the swap is a mapping and not a redesign:
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
 * below enforces them on the way out rather than trusting the caller:
 *
 *  1. A `reject` carries NO prediction set and NO grade. A failed quality gate
 *     is "no result", never a negative DR result (CLAUDE.md invariant 1).
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
  /** `unloaded` when a model is missing; `simulated-*` while this is a sim. */
  modelVersion: string
  /** P(usable) x 1000. A scaled integer — no floats near the ledger. */
  qualityScoreMilli: number | null
  /** Why this result looks the way it does, in one line. */
  note: string
}

/** Simulation-only. The real gate reads the image, not a dropdown, and ignores
 *  this argument — drop it at the call site when the swap happens. */
export interface GateOptions {
  simScenarioKey?: string
}

export class GateResultError extends Error {}

/**
 * Run the quality gate on one captured image.
 *
 * The image bytes never leave the device: the hash is computed here, exactly
 * as `infer.py` computes `image_sha256` so its caller never touches pixels.
 */
export async function callQualityGate(
  file: File,
  options: GateOptions = {},
): Promise<GateResult> {
  const imageSha256 = await sha256Hex(file)

  // TODO: swap for real infer.py — replace everything below this line.
  //
  // `netra/models/infer.py` already returns exactly `GateResult`, so the real
  // implementation is a call plus a snake_case -> camelCase rename. It cannot
  // be a `fetch` to the API: the nine endpoints in SPEC.md are frozen and none
  // of them grades an image, and SPEC.md forbids uploading the image at all.
  // The gate runs ON-DEVICE — in-browser via ONNX/WASM, or against a local
  // sidecar on the capture device. Until an artifact exists there is nothing
  // to load, so this returns an operator-chosen scenario rather than a fake
  // model: a fake model invites someone to mistake its output for a
  // measurement. Nothing below produces a number that is ever reported.
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
    note: `simulated scenario ${sc.key}; no model is loaded`,
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
