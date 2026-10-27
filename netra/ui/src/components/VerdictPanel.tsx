/**
 * The quality-gate verdict, shown large and unambiguously.
 *
 * The one rule this component exists to enforce: a REJECT is "no result".
 * It gets its own colour, icon, headline and next action, and it never renders
 * a grade, a prediction set or a referral control — there is nothing to refer.
 * It must never read as a clean bill of health.
 */

import { motion, useReducedMotion } from "framer-motion"
import type { GateVerdict } from "@/lib/api/types"
import { STATUS, type Status } from "./StatusBadge"
import { cn } from "@/lib/utils"

const VERDICT_STATUS: Record<GateVerdict, Status> = {
  usable: "usable",
  borderline: "borderline",
  reject: "reject",
}

const HEADLINE: Record<GateVerdict, string> = {
  usable: "Usable",
  borderline: "Borderline — recapture advised",
  reject: "No result — take again",
}

const EXPLAINER: Record<GateVerdict, string> = {
  usable: "This image can be graded.",
  borderline:
    "This image can be graded, but quality is marginal. Retake it if you can — the grade below is provisional.",
  // Said in words, not implied by colour. This is the sentence that stops a
  // rejected image being read as a negative result.
  reject:
    "This image could not be graded. This is NOT a negative result — the patient has not been screened yet.",
}

/** Human-readable text for the classical OpenCV reason-codes. The codes
 *  explain WHY an image failed and what to retake; they are not the gate. */
const CAUSE_TEXT: Record<string, string> = {
  focus: "Out of focus — re-steady the camera and refocus on the optic disc.",
  exposure: "Exposure is off — adjust illumination and take it again.",
  fov_mask: "Field of view is clipped — centre the retina in the frame.",
}

export function VerdictPanel({
  verdict,
  cause,
  scoreMilli,
  className,
}: {
  verdict: GateVerdict
  cause?: string | null
  /** Gate score as a scaled integer (x1000). No floats near the ledger. */
  scoreMilli?: number
  className?: string
}) {
  const reduce = useReducedMotion()
  const spec = STATUS[VERDICT_STATUS[verdict]]
  const Icon = spec.Icon

  return (
    <motion.section
      // State transition only, never decoration; <= 200ms; honours
      // prefers-reduced-motion.
      initial={reduce ? false : { opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      aria-live="polite"
      className={cn(
        "rounded-lg border-l-4 border border-border-subtle bg-surface p-5",
        spec.border,
        className,
      )}
    >
      <h2 className={cn("flex items-center gap-3 text-display", spec.fg)}>
        <Icon aria-hidden="true" className="size-8 shrink-0" />
        {HEADLINE[verdict]}
      </h2>

      <p className="mt-3 max-w-prose text-[18px] leading-relaxed text-text">
        {EXPLAINER[verdict]}
      </p>

      {cause && (
        <p className="mt-3 max-w-prose text-body text-text-muted">
          <span className="font-semibold text-text">Why: </span>
          {CAUSE_TEXT[cause] ?? cause}
          <span className="ml-2 font-mono text-caption">({cause})</span>
        </p>
      )}

      {scoreMilli !== undefined && (
        <p className="mt-2 font-mono text-caption text-text-muted tabular">
          quality score {scoreMilli}/1000
        </p>
      )}
    </motion.section>
  )
}
