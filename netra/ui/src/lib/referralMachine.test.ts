/**
 * The client's copy of the frozen machine. The risk this guards is a button
 * that offers a transition the server will reject, or - worse - a view that
 * quietly invents a state.
 */

import { describe, expect, it } from "vitest"
import {
  HAPPY_PATH,
  TERMINAL,
  allowedTransitions,
  canSubmit,
  isTerminal,
  pathIndex,
  requiresChannel,
  requiresReason,
  stateLabel,
} from "./referralMachine"
import type { ReferralState } from "./api/types"

const ALL: ReferralState[] = [
  "issued",
  "contact_attempted",
  "contacted",
  "appointment_offered",
  "examined",
  "abandoned",
]

describe("the machine matches the frozen contract", () => {
  it("offers exactly the forward move plus abandoned from each live state", () => {
    expect(allowedTransitions("issued")).toEqual(["contact_attempted", "abandoned"])
    expect(allowedTransitions("contact_attempted")).toEqual([
      // Repeatable, so it appears as a target of itself.
      "contact_attempted",
      "contacted",
      "abandoned",
    ])
    expect(allowedTransitions("contacted")).toEqual([
      "appointment_offered",
      "abandoned",
    ])
    expect(allowedTransitions("appointment_offered")).toEqual([
      "examined",
      "abandoned",
    ])
  })

  it("offers nothing from a terminal state", () => {
    expect(allowedTransitions("examined")).toEqual([])
    expect(allowedTransitions("abandoned")).toEqual([])
    expect(TERMINAL).toEqual(["examined", "abandoned"])
    expect(isTerminal("examined")).toBe(true)
    expect(isTerminal("issued")).toBe(false)
  })

  it("never offers a state outside the frozen six", () => {
    for (const from of ALL) {
      for (const to of allowedTransitions(from)) {
        expect(ALL).toContain(to)
      }
    }
  })

  it("makes abandoned reachable from every non-terminal state", () => {
    for (const from of ALL) {
      if (isTerminal(from)) continue
      expect(allowedTransitions(from)).toContain("abandoned")
    }
  })

  it("never offers a skip, e.g. issued straight to examined", () => {
    expect(allowedTransitions("issued")).not.toContain("examined")
    expect(allowedTransitions("issued")).not.toContain("contacted")
    expect(allowedTransitions("contacted")).not.toContain("examined")
  })
})

describe("required fields gate the submit", () => {
  it("contact_attempted needs a channel", () => {
    expect(requiresChannel("contact_attempted")).toBe(true)
    expect(canSubmit("issued", "contact_attempted", "", "")).toBe(false)
    expect(canSubmit("issued", "contact_attempted", "  ", "")).toBe(false)
    expect(canSubmit("issued", "contact_attempted", "phone", "")).toBe(true)
  })

  it("abandoned needs a reason", () => {
    expect(requiresReason("abandoned")).toBe(true)
    expect(canSubmit("issued", "abandoned", "", "")).toBe(false)
    expect(canSubmit("issued", "abandoned", "", "moved away")).toBe(true)
  })

  it("a move the machine forbids can never submit, however well filled in", () => {
    expect(canSubmit("issued", "examined", "phone", "because")).toBe(false)
    expect(canSubmit("examined", "abandoned", "phone", "because")).toBe(false)
  })

  it("a move needing nothing submits straight away", () => {
    expect(canSubmit("contact_attempted", "contacted", "", "")).toBe(true)
    expect(requiresChannel("contacted")).toBe(false)
    expect(requiresReason("contacted")).toBe(false)
  })
})

describe("labels and progress", () => {
  it("every state has a human label", () => {
    for (const s of ALL) {
      expect(stateLabel(s).length).toBeGreaterThan(0)
      expect(stateLabel(s)).not.toContain("_")
    }
  })

  it("the happy path is the five success states, in order", () => {
    expect(HAPPY_PATH).toEqual([
      "issued",
      "contact_attempted",
      "contacted",
      "appointment_offered",
      "examined",
    ])
    expect(HAPPY_PATH).not.toContain("abandoned")
  })

  it("abandoned sits off the happy path rather than at the end of it", () => {
    // Showing it as step 5 of 5 would read as a successful outcome.
    expect(pathIndex("abandoned")).toBeNull()
    expect(pathIndex("issued")).toBe(0)
    expect(pathIndex("examined")).toBe(4)
  })
})
