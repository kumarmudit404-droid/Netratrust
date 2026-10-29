/**
 * The two triggers that were previously untested.
 *
 * `queue.test.ts` covers what a drain DOES. These cover when one is attempted
 * and — the part that actually bites — whether teardown stops it. A leaked
 * interval or a leaked `online` listener goes on draining against an unmounted
 * screen for as long as the tab is open, and nothing in the app would say so.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { RETRY_MS, startSyncTriggers, type TriggerHost } from "./triggers"

/** A stand-in for `window`, so these run in Vitest's node environment. */
function fakeHost() {
  const listeners = new Map<string, Set<() => void>>()
  const host: TriggerHost = {
    addEventListener(type, listener) {
      const set = listeners.get(type) ?? new Set()
      set.add(listener)
      listeners.set(type, set)
    },
    removeEventListener(type, listener) {
      listeners.get(type)?.delete(listener)
    },
  }
  return {
    host,
    /** Fire the event the browser would fire when a network comes back. */
    goOnline: () => listeners.get("online")?.forEach((fn) => fn()),
    count: () => listeners.get("online")?.size ?? 0,
  }
}

describe("startSyncTriggers", () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it("drains once immediately, before any event or tick", () => {
    const drain = vi.fn()
    startSyncTriggers(drain, { host: fakeHost().host })

    // A device opened after a morning offline must start catching up without
    // the operator doing anything.
    expect(drain).toHaveBeenCalledTimes(1)
  })

  // ------------------------------------------------------- the online event

  it("drains when the network comes back", () => {
    const drain = vi.fn()
    const { host, goOnline } = fakeHost()
    startSyncTriggers(drain, { host })
    drain.mockClear()

    goOnline()

    expect(drain).toHaveBeenCalledTimes(1)
  })

  it("drains again on every online event, not just the first", () => {
    const drain = vi.fn()
    const { host, goOnline } = fakeHost()
    startSyncTriggers(drain, { host })
    drain.mockClear()

    // A device at the edge of coverage flaps. Each recovery is a chance to
    // deliver, so each one must try.
    goOnline()
    goOnline()
    goOnline()

    expect(drain).toHaveBeenCalledTimes(3)
  })

  it("registers exactly one online listener", () => {
    const { host, count } = fakeHost()
    startSyncTriggers(vi.fn(), { host })
    expect(count()).toBe(1)
  })

  it("stops draining on online once torn down", () => {
    const drain = vi.fn()
    const { host, goOnline, count } = fakeHost()
    const stop = startSyncTriggers(drain, { host })

    stop()
    drain.mockClear()
    goOnline()

    expect(drain).not.toHaveBeenCalled()
    // Removed, not merely ignored: a listener left on `window` outlives the
    // component for the life of the tab.
    expect(count()).toBe(0)
  })

  // ---------------------------------------------------------- the interval

  it("drains on every interval tick", () => {
    const drain = vi.fn()
    startSyncTriggers(drain, { host: fakeHost().host, intervalMs: 1000 })
    drain.mockClear()

    vi.advanceTimersByTime(3000)

    expect(drain).toHaveBeenCalledTimes(3)
  })

  it("does not tick before the interval has elapsed", () => {
    const drain = vi.fn()
    startSyncTriggers(drain, { host: fakeHost().host, intervalMs: 1000 })
    drain.mockClear()

    vi.advanceTimersByTime(999)

    expect(drain).not.toHaveBeenCalled()
  })

  it("uses RETRY_MS when no interval is given", () => {
    const drain = vi.fn()
    startSyncTriggers(drain, { host: fakeHost().host })
    drain.mockClear()

    vi.advanceTimersByTime(RETRY_MS - 1)
    expect(drain).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(drain).toHaveBeenCalledTimes(1)
  })

  it("stops ticking once torn down", () => {
    const drain = vi.fn()
    const stop = startSyncTriggers(drain, {
      host: fakeHost().host,
      intervalMs: 1000,
    })

    stop()
    drain.mockClear()
    vi.advanceTimersByTime(10_000)

    expect(drain).not.toHaveBeenCalled()
  })

  it("the interval covers the case online never fires for", () => {
    // A captive portal fires `online` with nothing reachable; a server that
    // was down fires nothing at all. The interval is the only trigger that
    // recovers from either, which is why it exists alongside the event.
    const drain = vi.fn()
    const { host } = fakeHost()
    startSyncTriggers(drain, { host, intervalMs: 1000 })
    drain.mockClear()

    // No online event, ever.
    vi.advanceTimersByTime(5000)

    expect(drain).toHaveBeenCalledTimes(5)
  })

  // ------------------------------------------------------------ no window

  it("works with no host at all, and still ticks", () => {
    // Vitest's environment is `node`: there is no window. Throwing here would
    // take down any non-browser import of the module.
    const drain = vi.fn()
    const stop = startSyncTriggers(drain, { host: null, intervalMs: 1000 })

    expect(drain).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(2000)
    expect(drain).toHaveBeenCalledTimes(3)

    expect(() => stop()).not.toThrow()
  })

  it("teardown is safe to call twice", () => {
    const stop = startSyncTriggers(vi.fn(), { host: fakeHost().host })
    stop()
    expect(() => stop()).not.toThrow()
  })

  // -------------------------------------------- it does not swallow a drain

  it("passes the same function to both triggers, so teardown removes it", () => {
    // If the event got a different closure from the one `removeEventListener`
    // is later given, teardown would silently leak. Checked by identity.
    const drain = vi.fn()
    const registered: (() => void)[] = []
    const host: TriggerHost = {
      addEventListener: (_t, listener) => registered.push(listener),
      removeEventListener: (_t, listener) => {
        expect(registered[0]).toBe(listener)
      },
    }

    startSyncTriggers(drain, { host })()
    expect(registered).toHaveLength(1)
  })
})
