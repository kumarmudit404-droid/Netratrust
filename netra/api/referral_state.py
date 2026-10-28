"""The referral state machine, exactly as frozen at the end of SPEC.md.

    issued
      -> contact_attempted (attempt_n, channel)   [repeatable]
      -> contacted
      -> appointment_offered
      -> examined        (terminal, success)
      |  abandoned(reason)   (terminal, from any non-terminal state)

Nothing here adds a state. The transition table is data, not branching, so a
new state cannot be introduced by an `if` somewhere in a route handler.
"""

from __future__ import annotations

ISSUED = "issued"
CONTACT_ATTEMPTED = "contact_attempted"
CONTACTED = "contacted"
APPOINTMENT_OFFERED = "appointment_offered"
EXAMINED = "examined"
ABANDONED = "abandoned"

TERMINAL = frozenset({EXAMINED, ABANDONED})

#: Allowed forward transitions. `abandoned` is added to every non-terminal
#: state below rather than repeated here.
_FORWARD: dict[str, frozenset[str]] = {
    ISSUED: frozenset({CONTACT_ATTEMPTED}),
    # Repeatable: a second attempt is a transition from contact_attempted to
    # itself, with attempt_n incremented.
    CONTACT_ATTEMPTED: frozenset({CONTACT_ATTEMPTED, CONTACTED}),
    CONTACTED: frozenset({APPOINTMENT_OFFERED}),
    APPOINTMENT_OFFERED: frozenset({EXAMINED}),
    EXAMINED: frozenset(),
    ABANDONED: frozenset(),
}

TRANSITIONS: dict[str, frozenset[str]] = {
    state: (targets | {ABANDONED} if state not in TERMINAL else targets)
    for state, targets in _FORWARD.items()
}

STATES = tuple(_FORWARD)


class TransitionError(Exception):
    """A transition the machine does not allow -> 409."""


class TransitionDataError(Exception):
    """A transition missing data it requires -> 422."""


def check(
    from_state: str, to_state: str, channel: str | None, reason: str | None
) -> None:
    """Raise unless `from_state -> to_state` is allowed and fully specified.

    The two error classes map to different statuses on purpose:
    - a structurally impossible move is a **409** (the resource is not in a
      state where this makes sense);
    - a permitted move with missing data is a **422** (the request is wrong).
    """
    if to_state not in STATES:
        raise TransitionDataError(f"unknown state {to_state!r}")
    if from_state in TERMINAL:
        raise TransitionError(
            f"{from_state!r} is terminal; no further transition is possible"
        )
    if to_state not in TRANSITIONS[from_state]:
        allowed = ", ".join(sorted(TRANSITIONS[from_state]))
        raise TransitionError(
            f"cannot go from {from_state!r} to {to_state!r}; allowed: {allowed}"
        )
    if to_state == CONTACT_ATTEMPTED and not channel:
        raise TransitionDataError("contact_attempted requires a channel")
    if to_state == ABANDONED and not reason:
        raise TransitionDataError("abandoned requires a reason")
