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

export function useLedgerVerify(enabled = false) {
  return useQuery({
    queryKey: keys.ledgerVerify,
    queryFn: () => api.verifyLedger(),
    enabled,
  })
}

export function useCheckpoint() {
  return useQuery({ queryKey: keys.checkpoint, queryFn: () => api.ledgerCheckpoint() })
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
