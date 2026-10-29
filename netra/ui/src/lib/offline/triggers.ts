/**
 * WHEN to drain the device queue. Deliberately not React.
 *
 * `useDeviceQueue` used to wire these three triggers inline inside a
 * `useEffect`, which left the decision that actually matters — when a replay is
 * attempted, and whether teardown really stops it — reachable only through a
 * DOM renderer. Lane B's stack has no renderer and adding one would be a new
 * dependency, so the logic lives here instead, as a plain function over
 * injectable timers and an injectable event target. The hook is now glue.
 *
 * Three triggers, because no one of them is enough:
 *
 *  - **on start**, so a device opened after a morning offline begins catching
 *    up without the operator doing anything;
 *  - **on `online`**, the fast path, which is NOT trustworthy by itself: a
 *    captive portal fires `online` with nothing actually reachable;
 *  - **on an interval**, which is what recovers from the captive-portal case,
 *    and from a server that was down rather than a network that was. `online`
 *    never fires for either.
 *
 * `navigator.onLine` is not consulted anywhere. The only honest test of
 * connectivity is a request: `drain` tries, and the error decides (`classify`).
 */

/** The slice of `window` these triggers need. */
export interface TriggerHost {
  addEventListener(type: "online", listener: () => void): void
  removeEventListener(type: "online", listener: () => void): void
}

/** Whatever the host's `setInterval` hands back - a number in a browser, a
 *  `Timeout` object in Node. Named so the pair cannot drift apart. */
export type TimerHandle = ReturnType<typeof setInterval>

export interface TriggerOptions {
  /** Defaults to `window`, or nothing at all where there is no window. */
  host?: TriggerHost | null
  intervalMs?: number
  /** Injectable for tests; the real ones otherwise. */
  setInterval?: (handler: () => void, ms: number) => TimerHandle
  clearInterval?: (handle: TimerHandle) => void
}

/** Long enough not to hammer a server that is down, short enough that someone
 *  who plugs the network back in does not stand there waiting. */
export const RETRY_MS = 15_000

function defaultHost(): TriggerHost | null {
  return typeof window === "undefined" ? null : window
}

/**
 * Start the triggers. Returns the teardown.
 *
 * Teardown must be total: a timer or listener that outlives the component
 * keeps calling `drain` on an unmounted screen forever.
 */
export function startSyncTriggers(
  drain: () => void,
  options: TriggerOptions = {},
): () => void {
  const {
    host = defaultHost(),
    intervalMs = RETRY_MS,
    setInterval: setTimer = setInterval,
    clearInterval: clearTimer = clearInterval,
  } = options

  // Immediately, before any event or tick.
  drain()

  const timer = setTimer(drain, intervalMs)
  host?.addEventListener("online", drain)

  return () => {
    clearTimer(timer)
    host?.removeEventListener("online", drain)
  }
}
