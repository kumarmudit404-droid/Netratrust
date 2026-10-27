/**
 * The case currently on screen, shared between Capture and Grade.
 *
 * In-memory only and deliberately so: no image bytes, and no clinical state
 * cached anywhere a stale read could surface later. The ledger is the record
 * of what happened; this is just what the operator is looking at right now.
 */

import { createContext, useContext, useMemo, useState, type ReactNode } from "react"
import type { GateVerdict, Grade } from "@/lib/api/types"

export interface CurrentCase {
  /** SHA-256 of the captured image, computed on-device. The bytes never leave. */
  imageSha256: string
  verdict: GateVerdict
  cause: string | null
  /** Gate score as a scaled integer (x1000) — no floats near the ledger. */
  scoreMilli: number
  /** Null for a rejected image: a failed gate is "no result", never a grade. */
  predictionSet: Grade[] | null
  modelVersion: string
  /** Set once POST /v1/encounters has returned. */
  encounterId?: string
  ledgerIdx?: number
  /** Set once POST /v1/referrals has returned. */
  referralId?: string
}

interface Ctx {
  current: CurrentCase | null
  setCurrent: (c: CurrentCase | null) => void
  patchCurrent: (p: Partial<CurrentCase>) => void
}

const EncounterContext = createContext<Ctx | null>(null)

export function EncounterProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<CurrentCase | null>(null)

  const value = useMemo<Ctx>(
    () => ({
      current,
      setCurrent,
      patchCurrent: (p) => setCurrent((c) => (c ? { ...c, ...p } : c)),
    }),
    [current],
  )

  return <EncounterContext.Provider value={value}>{children}</EncounterContext.Provider>
}

export function useEncounter(): Ctx {
  const ctx = useContext(EncounterContext)
  if (!ctx) throw new Error("useEncounter must be used inside <EncounterProvider>")
  return ctx
}
