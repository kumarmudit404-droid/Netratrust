/**
 * The conformal prediction set, as five grade chips.
 *
 * Grades inside the set are filled; grades outside are outlined. The chips
 * carry the set's SHAPE, which is the thing a clinician needs: {0,1} and {0,3}
 * are both size two and only the second spans a clinical action boundary.
 */

import type { Grade } from "@/lib/api/types"
import { CONFORMAL_CONFIDENCE, isReferable } from "@/lib/clinical"
import { cn } from "@/lib/utils"

const ALL_GRADES: Grade[] = [0, 1, 2, 3, 4]

const GRADE_LABEL: Record<Grade, string> = {
  0: "No DR",
  1: "Mild",
  2: "Moderate",
  3: "Severe",
  4: "Proliferative",
}

export function PredictionSet({
  set,
  className,
}: {
  set: readonly Grade[]
  className?: string
}) {
  const pct = Math.round(CONFORMAL_CONFIDENCE * 100)

  return (
    <div className={className}>
      <h3 className="text-subhead">
        Prediction set{" "}
        <span className="font-normal text-text-muted">({pct}% confidence)</span>
      </h3>

      <ul className="mt-3 flex flex-wrap gap-2" aria-label="Conformal prediction set">
        {ALL_GRADES.map((g) => {
          const inSet = set.includes(g)
          return (
            <li key={g}>
              <span
                className={cn(
                  "flex min-w-[7.5rem] flex-col rounded-md border px-3 py-2",
                  inSet
                    ? // Referable members get the reject token: this is the
                      // "action" half of the set, not merely a bigger number.
                      isReferable(g)
                      ? "border-reject bg-surface text-reject"
                      : "border-usable bg-surface text-usable"
                    : "border-border-subtle text-text-muted opacity-60",
                )}
              >
                <span className="text-subhead tabular">
                  {g}
                  {/* Membership is stated in text, never by colour alone. */}
                  <span className="ml-2 text-caption font-normal">
                    {inSet ? "in set" : "excluded"}
                  </span>
                </span>
                <span className="text-caption">{GRADE_LABEL[g]}</span>
              </span>
            </li>
          )
        })}
      </ul>

      <p className="mt-3 max-w-prose text-caption text-text-muted">
        Grades 2–4 are referable (moderate NPDR or worse). A set holding both
        referable and non-referable grades spans two clinical actions, which is
        why it is sent for review rather than graded.
      </p>
    </div>
  )
}
