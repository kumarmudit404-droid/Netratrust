/** Top navigation + persistent status strip. Replaces what SPEC.md section 7
 *  previously specified as st.navigation(position="top"). */

import { NavLink } from "react-router-dom"
import { useQueueDepth } from "@/lib/api/queries"
import { usingMock } from "@/lib/api/client"
import { StatusBadge } from "./StatusBadge"
import { cn } from "@/lib/utils"

const ROUTES = [
  { to: "/capture", label: "Capture" },
  { to: "/grade", label: "Grade" },
  { to: "/referrals", label: "Referrals" },
  { to: "/sites", label: "Sites" },
  { to: "/ledger", label: "Ledger" },
]

export function TopNav() {
  const { data, isError } = useQueueDepth()

  return (
    <header className="border-b border-border-subtle bg-bg">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <span className="text-subhead">NetraTrust</span>
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {ROUTES.map((r) => (
            <NavLink
              key={r.to}
              to={r.to}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-body transition-colors",
                  isActive
                    ? "bg-surface font-semibold text-text"
                    : "text-text-muted hover:bg-surface hover:text-text",
                )
              }
            >
              {r.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {usingMock && (
            <span className="rounded-md border border-border-subtle px-2 py-1 text-caption text-text-muted">
              mock data
            </span>
          )}
          {/* Offline is normal for this app, so a queue is never an error. */}
          {isError ? (
            <StatusBadge status="pending-sync" label="Offline" />
          ) : data && data.queued > 0 ? (
            <StatusBadge status="pending-sync" label={`Queued — ${data.queued} waiting`} />
          ) : (
            <StatusBadge status="usable" label="Synced" />
          )}
        </div>
      </div>
    </header>
  )
}
