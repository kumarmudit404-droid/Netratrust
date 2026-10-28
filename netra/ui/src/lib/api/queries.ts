/** TanStack Query hooks over the typed client. Live panels poll on an
 *  interval here rather than in a component, so the cadence is in one place. */

import { useMutation, useQuery } from "@tanstack/react-query"
import { api } from "./client"
import type { EncounterRequest, ReferralPatchRequest } from "./types"

/** Poll cadence for the live panels (queue depth, connectivity badge). */
const LIVE_MS = 5000

export const keys = {
  queueDepth: ["queue", "depth"] as const,
  ledgerVerify: ["ledger", "verify"] as const,
  checkpoint: ["ledger", "checkpoint"] as const,
  siteStatus: (id: string) => ["sites", id, "status"] as const,
  siteMetrics: ["metrics", "sites"] as const,
}

export function useQueueDepth() {
  return useQuery({
    queryKey: keys.queueDepth,
    queryFn: () => api.queueDepth(),
    refetchInterval: LIVE_MS,
  })
}

/** Verification is OPERATOR-TRIGGERED: it stays disabled until the Ledger view
 *  says it has run, so the screen cannot show a stale `ok:true` that nobody
 *  asked for. `pollMs` drives the optional re-check loop that makes the tamper
 *  demo's ok:true -> ok:false flip happen on screen. */
export function useLedgerVerify(
  opts: { enabled?: boolean; pollMs?: number | false } = {},
) {
  return useQuery({
    queryKey: keys.ledgerVerify,
    queryFn: () => api.verifyLedger(),
    enabled: opts.enabled ?? false,
    refetchInterval: opts.pollMs ?? false,
    // The point of this screen is the CURRENT state of the chain, so a cached
    // answer is never good enough.
    staleTime: 0,
    gcTime: 0,
  })
}

export function useCheckpoint() {
  return useQuery({
    queryKey: keys.checkpoint,
    queryFn: () => api.ledgerCheckpoint(),
    refetchInterval: LIVE_MS,
  })
}

export function useSiteStatus(siteId: string) {
  return useQuery({
    queryKey: keys.siteStatus(siteId),
    queryFn: () => api.siteStatus(siteId),
    refetchInterval: LIVE_MS,
  })
}

export function useSiteMetrics() {
  return useQuery({
    queryKey: keys.siteMetrics,
    queryFn: () => api.siteMetrics(),
    refetchInterval: LIVE_MS,
  })
}

export function useCreateEncounter() {
  return useMutation({
    mutationFn: (body: EncounterRequest) => api.createEncounter(body),
  })
}

export function useCreateReferral() {
  return useMutation({ mutationFn: (encounterId: string) => api.createReferral(encounterId) })
}

export function usePatchReferral(id: string) {
  return useMutation({
    mutationFn: (body: ReferralPatchRequest) => api.patchReferral(id, body),
  })
}
