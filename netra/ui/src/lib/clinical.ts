/**
 * Clinical decision rules the UI needs in order to RENDER correctly.
 *
 * These mirror config/thresholds.yaml. They are declared once here, never
 * inline in a screen.
 *   dr.refer_grades: [2, 3, 4]        -> REFER_GRADES
 *   dr.conformal_confidence: 0.90     -> CONFORMAL_CONFIDENCE
 *
 * TODO(Lane A): serve these from the API (or the site status payload) so the
 * front end stops mirroring a config file it cannot read at runtime. Until
 * then a change to config/thresholds.yaml must be mirrored here.
 */

import type { Grade } from "./api/types"

/** Moderate NPDR or worse. */
export const REFER_GRADES: readonly Grade[] = [2, 3, 4]

/** Conformal prediction-set confidence level. Display only. */
export const CONFORMAL_CONFIDENCE = 0.9

export function isReferable(g: Grade): boolean {
  return REFER_GRADES.includes(g)
}

/**
 * The abstention rule from SPEC.md section 3.
 *
 * Abstain when the prediction set spans more than one CLINICAL ACTION class —
 * refer vs do-not-refer — NOT when the set is merely large. {0,1} and {0,3}
 * are both size 2 and only the second is alarming.
 */
export function spansClinicalActions(set: readonly Grade[]): boolean {
  if (set.length < 2) return false
  return set.some(isReferable) && set.some((g) => !isReferable(g))
}

/** The single grade to display, or null when the set does not justify one. */
export function singleGrade(set: readonly Grade[]): Grade | null {
  return set.length === 1 ? set[0] : null
}
