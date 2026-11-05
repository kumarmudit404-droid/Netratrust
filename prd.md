# NetraTrust — Product Requirements (PRD)

> **Source of truth:** `SPEC.md` (frozen 2026-10-27) and `BUILD_RULES.md`. Where this
> document and `SPEC.md` disagree, `SPEC.md` wins. Facts not present in those files
> are marked **TBD — verify**. Ownership is by lane, not by person.

## 1. Problem statement
Diabetic-retinopathy (DR) screening programs lose most of their value at two points
that automated accuracy metrics hide:

- **Ungradable images are silently treated as negative.** When a fundus photograph is
  too dark, blurred or off-centre to grade, a system that returns a grade anyway
  produces a false "no disease" result. Reported specificity collapses in the field
  (one program: 96.01% → 64.7%). Ungradable rates are high and rise with age
  (20.9% vs 13.1% overall; 32.5% in patients over 60).
- **The referral cascade leaks.** Of patients flagged for referral, only a fraction are
  reachable, fewer are contacted, and fewer still attend (one cascade: 64 referred →
  28 reachable → 9 attended, ≈14%). A screening result that is never acted on is
  clinically worthless.

NetraTrust addresses both: it refuses to grade what it cannot grade, abstains when it
is not confident, monitors each site's reliability, and tracks every referral to
outcome on a tamper-evident ledger.

## 2. Target users
- **Screening-camp operators** (primary): capture images, see an immediate
  Usable / Borderline / Reject verdict, and act on a referral decision offline.
- **Ophthalmologists / reviewers:** receive referrals with the model's confidence and
  the reason an image was rejected or abstained on.
- **Program administrators:** read per-site reliability dashboards and verify the
  referral ledger has not been altered.

## 3. The claim we prove
A screening front end that (a) gates image quality before grading, (b) abstains when a
conformal prediction set spans more than one clinical action, and (c) records every
decision immutably, produces **safer and more auditable** referrals than a
grade-everything pipeline — demonstrated on held-out public data, not claimed in prose.

This is **not** a diagnostic claim. See §7.

## 4. Core features
1. **Image-quality gate** — Usable / Borderline / Reject, on-device, before any grading.
2. **DR grading with abstention** — grades 0–4; abstains rather than guess when
   uncertain.
3. **Per-site reliability monitoring** — gradability and abstention rates per site, as
   distributions with confidence intervals, never bare percentages for small n.
4. **Referral tracking on a tamper-evident ledger** — SHA-256 hash chain + Ed25519
   signatures, append-only, verifiable.

## 5. Functional requirements
- FR-1 Capture or import a fundus image and return a quality verdict on-device.
- FR-2 A **Reject** verdict offers recapture; it is never recorded as a DR result.
- FR-3 Grade only Usable (and operator-confirmed Borderline) images.
- FR-4 Return a conformal prediction set at 90% confidence; abstain when the set spans
  more than one clinical action.
- FR-5 Issue a referral for grades in the refer set (moderate NPDR or worse).
- FR-6 Record every encounter and referral decision as a ledger entry.
- FR-7 Advance a referral through its state machine (see `architecture.md` §5).
- FR-8 Expose per-site status (gradability, abstention, drift flag).
- FR-9 Verify the ledger chain and serve a signed checkpoint.
- FR-10 Operate fully offline; sync when connectivity returns (at-least-once, server
  deduplicated by idempotency key).
- FR-11 Never transmit a fundus image off the device.
- FR-12 Show the reason for every Reject and every abstention.
- FR-13 Present per-site results as distributions; suppress any rate for n < 30.
- FR-14 Expose queue depth for pending sync.
- FR-15 Record a per-site audit result (model version, timestamp, pass/fail).

## 6. Non-functional requirements
- NFR-1 Quality verdict in **≤ 2 s** on commodity camp hardware. **TBD — verify** on
  target device.
- NFR-2 Fits the Fly.io footprint in `architecture.md` (256 MB + 1 GB volume).
- NFR-3 All thresholds fitted on the **calibration split only**; the test split is
  touched once.
- NFR-4 Ledger payloads contain **no floats** and canonicalise identically on write and
  verify (`rfc8785`).
- NFR-5 Reproducible: frozen, committed, patient-level splits (seed 20261027).
- NFR-6 Every clinical metric comes from `netra/eval/metrics.py`.
- NFR-7 No dependency outside the pinned set in `requirements.txt`.
- NFR-8 WCAG 2.1 AA contrast for all text (see `design.md`).

## 7. Non-goals
- **No diagnosis.** NetraTrust triages toward referral; it does not diagnose.
- **No image upload.** Images stay on the capture device.
- **No LLM / RAG in the clinical path.** General-purpose vision-language models grade
  fundus images poorly (reported ≈47.7% sensitivity) and are excluded.
- **No new endpoints or referral states** beyond the frozen `SPEC.md`.

## 8. Success metrics
- **Claim:** on the held-out test split, the gated+abstaining pipeline shows higher
  effective specificity among acted-upon referrals than grade-everything.
- **Model:** Brier and NLL (primary), ECE (secondary, binned), AUGRC for the
  risk–coverage trade-off.
- **Integrity:** `GET /v1/ledger/verify` passes; the signed checkpoint validates.
- **Visibility:** every site renders with Wilson intervals; no bare % for n < 30.

## 9. Open questions
- `NetraTrust build pipeline.pdf` may carry binding constraints — confirm nothing in it
  overrides this PRD. **TBD — verify.**
- The 42% cataract figure, the AIOS/VRSI 2021 statement, the RETFound gate-approval mode
  and T4 training times remain **unverified**.
