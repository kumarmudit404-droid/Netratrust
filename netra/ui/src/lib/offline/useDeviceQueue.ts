/**
 * React side of the device queue: what the status strip shows.
 *
 * WHEN to drain lives in `triggers.ts`, as a plain function, because that
 * decision is not React's and was otherwise reachable only through a DOM
 * renderer that Lane B's stack does not have. This file is the glue: subscribe,
 * snapshot, re-render.
 */

import { useEffect, useState } from "react"
import { apiSender, deviceQueue } from "./sync"
import { startSyncTriggers } from "./triggers"
import type { QueuedMutation } from "./queue"

export { RETRY_MS } from "./triggers"

export interface DeviceQueueState {
  pending: QueuedMutation[]
  failed: { entry: QueuedMutation; reason: string }[]
  /** Convenience for the strip. */
  depth: number
}

function snapshot(): DeviceQueueState {
  const pending = deviceQueue.pending()
  return { pending, failed: deviceQueue.failed(), depth: pending.length }
}

export function useDeviceQueue(): DeviceQueueState {
  const [state, setState] = useState<DeviceQueueState>(snapshot)

  useEffect(() => {
    const refresh = () => setState(snapshot())
    const unsubscribe = deviceQueue.subscribe(refresh)

    const stopTriggers = startSyncTriggers(() => {
      void deviceQueue.drain(apiSender).finally(refresh)
    })

    return () => {
      unsubscribe()
      stopTriggers()
      // `drain` refuses re-entry, so one already in flight finishes
      // harmlessly; `refresh` on an unmounted component is a no-op in React 18+.
    }
  }, [])

  return state
}
