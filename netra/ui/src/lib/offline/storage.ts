/**
 * Where the device's pending queue lives.
 *
 * `localStorage`, because the queue has to survive a page navigation, a tab
 * close and a flat battery: a camp device may capture all morning with no
 * signal. This is the one piece of state that is deliberately NOT server-side —
 * SPEC.md section 5 puts the connectivity FLAG on the server so the demo
 * survives a second tab, and `GET /v1/queue/depth` says in as many words that
 * the server cannot see the device's local queue. This is that queue.
 *
 * Behind an interface for two reasons. Every read and write is wrapped because
 * `localStorage` throws in a private window and with site data blocked, and a
 * screening app must keep working when its queue cannot persist — it just
 * loses the queue on reload. And the tests run in Vitest's `node` environment,
 * where there is no `localStorage` at all.
 */

/** The smallest surface the queue needs. */
export interface QueueStorage {
  read(): string | null
  write(value: string): void
}

export const QUEUE_STORAGE_KEY = "netra.pendingQueue.v1"

/** In-memory, for the node test environment and as the fallback. */
export function memoryStorage(initial: string | null = null): QueueStorage {
  let value = initial
  return {
    read: () => value,
    write: (next) => {
      value = next
    },
  }
}

/**
 * `localStorage` when it is usable, memory when it is not.
 *
 * Probed with a real write, not a `typeof` check: Safari in private browsing
 * exposes the object and throws on `setItem`, so a presence test reports a
 * working store that is not one.
 */
export function browserStorage(key: string = QUEUE_STORAGE_KEY): QueueStorage {
  try {
    const probe = `${key}.probe`
    localStorage.setItem(probe, "1")
    localStorage.removeItem(probe)
  } catch {
    return memoryStorage()
  }

  return {
    read: () => {
      try {
        return localStorage.getItem(key)
      } catch {
        return null
      }
    },
    write: (value) => {
      try {
        localStorage.setItem(key, value)
      } catch {
        // Out of quota, or site data blocked mid-session. The queue stays in
        // memory for this page: losing it on reload is bad, refusing to
        // capture would be worse.
      }
    },
  }
}

/** `browserStorage` where there is a browser, memory otherwise. */
export function defaultStorage(key: string = QUEUE_STORAGE_KEY): QueueStorage {
  return typeof localStorage === "undefined" ? memoryStorage() : browserStorage(key)
}
