/**
 * SIMULATED gate + grader, for Lane B development only.
 *
 * The real quality gate (QuickQual) and DR classifier run ON-DEVICE and belong
 * to Lane C (netra/models). Neither is wired up yet, so the capture screen is
 * driven by an explicit operator-chosen scenario rather than a fake model: a
 * fake model would invite someone to mistake its output for a measurement.
 *
 * Nothing here produces a number that is ever reported. Delete this module as
 * soon as Lane C exposes a real on-device gate.
 */

import type { GateVerdict, Grade } from "./api/types"

export interface Scenario {
  key: string
  label: string
  verdict: GateVerdict
  cause: string | null
  scoreMilli: number
  /** Null for reject — a failed gate yields no grade at all. */
  predictionSet: Grade[] | null
}

/** Placeholder until Lane C pins a trained checkpoint. */
export const SIM_MODEL_VERSION = "simulated-gate@lane-b-dev"

export const SCENARIOS: Scenario[] = [
  {
    key: "usable-clear",
    label: "Usable — clearly grade 0",
    verdict: "usable",
    cause: null,
    scoreMilli: 912,
    predictionSet: [0],
  },
  {
    key: "usable-referable",
    label: "Usable — referable (grade 3)",
    verdict: "usable",
    cause: null,
    scoreMilli: 874,
    predictionSet: [3],
  },
  {
    key: "usable-abstain",
    label: "Usable — set spans an action boundary {1,2}",
    verdict: "usable",
    cause: null,
    scoreMilli: 806,
    predictionSet: [1, 2],
  },
  {
    key: "usable-wide-same-action",
    label: "Usable — wide set, one action {2,3,4}",
    verdict: "usable",
    cause: null,
    scoreMilli: 791,
    predictionSet: [2, 3, 4],
  },
  {
    key: "borderline",
    label: "Borderline — recapture advised",
    verdict: "borderline",
    cause: "exposure",
    scoreMilli: 512,
    predictionSet: [0, 1],
  },
  {
    key: "reject-focus",
    label: "Reject — out of focus",
    verdict: "reject",
    cause: "focus",
    scoreMilli: 212,
    predictionSet: null,
  },
  {
    key: "reject-fov",
    label: "Reject — field of view clipped",
    verdict: "reject",
    cause: "fov_mask",
    scoreMilli: 164,
    predictionSet: null,
  },
]
