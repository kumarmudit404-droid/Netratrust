/** Top navigation + persistent status strip. Replaces what SPEC.md section 7
 *  previously specified as st.navigation(position="top"). */

import { NavLink } from "react-router-dom"
import { useQueueDepth } from "@/lib/api/queries"
import { usingMock } from "@/lib/api/client"
import { useDeviceQueue } from "@/lib/offline/useDeviceQueue"
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
  // Two different numbers, and conflating them would be a lie. `device` is
  // what this handset is holding and has not delivered; `data.queued` is the
  // SERVER's backlog of deliveries it accepted and has not applied. The server
  // cannot see the device's queue - that is the whole point of T-19.
  const device = useDeviceQueue()

  return (
    <header className="border-b border-accent/25 bg-bg">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <span className="font-serif text-subhead font-semibold tracking-wide text-text">
          NetraTrust
        </span>
        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {ROUTES.map((r) => (
            <NavLink
              key={r.to}
              to={r.to}
              className={({ isActive }) =>
                cn(
                  "rounded-md border-b-2 border-transparent px-3 py-2 text-body transition-colors",
                  isActive
                    ? "border-accent bg-surface font-semibold text-text"
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
          {/* A capture the server refused permanently is the one case here
              that IS an error: the record is not coming back by waiting. */}
          {device.failed.length > 0 && (
            <StatusBadge
              status="error"
              label={`${device.failed.length} not accepted`}
            />
          )}

          {/* Offline is normal for this app, so a queue is never an error.
              The device's own backlog is named first: it is the one the
              operator can do something about by finding signal. */}
          {device.depth > 0 ? (
            <StatusBadge
              status="pending-sync"
              label={`${device.depth} on this device`}
            />
          ) : isError ? (
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
