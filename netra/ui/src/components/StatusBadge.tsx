/**
 * The seven component states from design.md section 6, in one place.
 *
 * Every status pairs a colour token with an ICON and a TEXT LABEL — colour is
 * never the sole carrier of meaning (colour-blind safe). No screen re-decides
 * a status treatment; it imports this.
 */

import {
  CircleDot,
  CircleX,
  Contrast,
  Diamond,
  Minus,
  RefreshCw,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

export type Status =
  | "usable"
  | "borderline"
  | "reject"
  | "grade"
  | "abstain"
  | "pending-sync"
  | "error"

interface StatusSpec {
  label: string
  Icon: LucideIcon
  /** Text/icon colour class — all measured AA on --bg. */
  fg: string
  /** Border class for panels. Never the only signal. */
  border: string
}

export const STATUS: Record<Status, StatusSpec> = {
  usable: {
    label: "Usable",
    Icon: CircleDot,
    fg: "text-usable",
    border: "border-usable",
  },
  borderline: {
    label: "Borderline — recapture advised",
    Icon: Contrast,
    fg: "text-borderline",
    border: "border-borderline",
  },
  reject: {
    // A reject is "no result". It is never shown as healthy.
    label: "No result — take again",
    Icon: CircleX,
    fg: "text-reject",
    border: "border-reject",
  },
  grade: { label: "Grade", Icon: Minus, fg: "text-text", border: "border-text" },
  abstain: {
    label: "A doctor should check this",
    Icon: Diamond,
    fg: "text-abstain",
    border: "border-abstain",
  },
  "pending-sync": {
    // Offline is normal for this app. This is NOT an error state.
    label: "Queued",
    Icon: RefreshCw,
    fg: "text-text-muted",
    border: "border-border-subtle",
  },
  error: {
    label: "Error",
    Icon: TriangleAlert,
    fg: "text-reject",
    border: "border-reject",
  },
}

export function StatusBadge({
  status,
  label,
  className,
}: {
  status: Status
  /** Overrides the default label, e.g. "Grade 2" or a queue count. */
  label?: string
  className?: string
}) {
  const spec = STATUS[status]
  const Icon = spec.Icon
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-md border px-2 py-1 text-caption font-semibold",
        spec.fg,
        spec.border,
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {label ?? spec.label}
    </span>
  )
}
