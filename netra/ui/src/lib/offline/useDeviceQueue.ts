/**
 * React side of the device queue: when to drain, and what the strip shows.
 *
 * Draining is triggered three ways, because no single one is reliable:
 *  - on mount, so a page opened after a day offline starts catching up;
 *  - on the `online` event, which is the fast path and is NOT trustworthy on
 *    its own (a captive portal reports online with nothing reachable);
 *  - on an interval, which is what actually recovers from the captive-portal
 *    case and from a server that was down rather than a network that was.
 *
 * `navigator.onLine` is deliberately not used as the gate for sending. The
 * only honest test of connectivity is a request: `drain` tries, and the error
 * it gets back is what decides (see `classify`).
 */

import { useEffect, useState } from "react"
import { deviceQueue } from "./sync"
import { apiSender } from "./sync"
import type { QueuedMutation } from "./queue"

/** Long enough not to hammer a server that is down, short enough that a
 *  presenter who plugs the network back in does not wait for it. */
export const RETRY_MS = 15_000

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

    const drain = () => {
      void deviceQueue.drain(apiSender).finally(refresh)
    }

    drain()
    const timer = setInterval(drain, RETRY_MS)
    window.addEventListener("online", drain)

    return () => {
      unsubscribe()
      clearInterval(timer)
      window.removeEventListener("online", drain)
      // `drain` refuses re-entry, so an in-flight one finishing after unmount
      // completes harmlessly; `refresh` on a dead component is a no-op in
      // React 18+.
    }
  }, [])

  return state
}
