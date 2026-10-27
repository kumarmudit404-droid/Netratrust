# NetraTrust — Working Rules for Claude Code

> These rules are operational. The **contract** is `SPEC.md`; the **conventions** are
> `CLAUDE.md`; the path-scoped ML rules are `.claude/rules/ml.md`. This file says how to
> work on the repo without breaking any of them. Where this file and `SPEC.md` disagree,
> **`SPEC.md` wins** and this file is what gets fixed. Rules already enforced elsewhere
> are referenced here, not restated.

## Table of contents
1. [Dependencies](#1-dependencies)
2. [Do not break existing APIs](#2-do-not-break-existing-apis)
3. [Test after every change](#3-test-after-every-change)
4. [Clinical invariants](#4-clinical-invariants)
5. [Lane discipline](#5-lane-discipline)
6. [When to stop and ask](#6-when-to-stop-and-ask)

## 1. Dependencies
- **No unnecessary dependencies.** Use only what is pinned in `requirements.txt`.
- **Banned, with reason:** `alibi-detect`, `sdv` (BUSL-1.1 licence); `puncc`
  (needs numpy < 2); `pymerkle` (GPL-3); `aiosqlite` (async+SQLite is slower here, not
  faster).
- Adding any package requires a one-line justification appended to `memory.md` and a
  version pin added to `requirements.txt` in the same change.

## 2. Do not break existing APIs
- The nine endpoints and the referral state machine in `SPEC.md` are **frozen**. Do not
  rename, remove, or change the shape of a request or response.
- A genuine need to change the contract **stops work** and is raised with the team
  first (see §6). Changing `SPEC.md` is never a silent act.
- Changing an endpoint's behaviour without changing its signature still counts as
  breaking it if a caller's expectations change.

## 3. Test after every change
- Run `pytest -q` after every change. Never merge red.
- This is mechanical, not advisory: the **Stop hook** in `.claude/settings.json`
  (`pytest -q || exit 2`) blocks the turn from ending while tests fail.
- A new feature lands with the test that proves it. A bug fix lands with the test that
  would have caught it.
- Merge twice daily; run the full suite before each merge.

## 4. Clinical invariants
These are the lines that, if crossed, make the project unsafe or dishonest:
1. A failed quality gate is **not** a negative DR result.
2. Thresholds are fitted on the **calibration split only**; the test split is touched
   once.
3. Every decision is appended to the ledger **before** it is returned to the caller.
4. `rfc8785` canonicalisation on both write and verify; **no floats** in ledger
   payloads (use ints or strings).
5. Never report a bare % for **n < 30**; show per-site results as a distribution.
6. Splits are patient-level, frozen and committed.
7. All metrics come from `netra/eval/metrics.py`. The risk–coverage reference line is
   **horizontal**.
8. Real and synthetic results live in **separate tables**, never mixed.
9. No fundus image leaves the capture device.
10. No LLM/RAG in the clinical path.

## 5. Lane discipline
- **Lane A** — `netra/api`, `netra/ledger`, `netra/db`.
- **Lane B** — `netra/ui`.
- **Lane C** — `netra/models`, `netra/eval`, `notebooks`.
- Never edit another lane's files. If you need an interface changed, request the change;
  do not reach across.
- One working session per lane at a time, to avoid two agents editing one file.

## 6. When to stop and ask
Stop and raise it with the team rather than deciding alone when:
- a change would alter `SPEC.md` (an endpoint, a referral state, a dependency);
- test results would be used to re-pick a split, a threshold, or metric code
  (**evaluation drift** — the failure no hook catches);
- a model is still training at the **Thursday 21:00** freeze (ship the checkpoint you
  have — do not slip the freeze);
- a figure cannot be traced to a source file (mark it **TBD — verify**, never invent).
