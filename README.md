<p align="center"><img src="docs/logo.svg" width="160" alt="NetraTrust"></p>

# NetraTrust

**Offline-first diabetic retinopathy screening that knows when *not* to answer.**

Built by Team RUSH, October 2026, for a healthcare hackathon (AI + cloud +
cybersecurity track).

---

## The problem

Diabetic retinopathy (DR) is a leading cause of preventable blindness, and
screening camps in underserved areas often run with no reliable internet, by
health workers who are not ophthalmologists. A model that confidently returns
a wrong grade in that setting is dangerous, and accuracy on a clean public
split does not predict it: the failures come from ungradable images, from
referrals nobody follows up, and from results nobody can audit afterwards.
Those are the three things this build is about.

## What it actually does

Four parts. Each one exists because a grade-everything pipeline fails in a
specific way, and each is listed with the failure it is there to stop.

### 1. Image quality gate
Every fundus photo is scored for gradability — `usable` / `borderline` /
`reject`, with a reason code (e.g. `focus`). A failed gate returns **no
result**, never a false negative. A bad photograph is not a diagnosis.

- Primary: QuickQual — frozen DenseNet-121 (`densenet121.tv_in1k`) features
  at 512px + a calibrated SVM head.

### 2. Conformal abstention
The DR classifier (ConvNeXt-Tiny @512px, fine-tuned on APTOS) doesn't
return one guessed grade — it returns a **prediction set**: every grade still
plausible at 90% confidence (split-conformal prediction, via MAPIE). Grades
2–4 mean "refer." If the set spans both referable and non-referable grades,
the system **abstains** and routes the case to a clinician instead of
guessing.

- QWK 0.886 · coverage 0.939 · abstains on 6.1% of cases · mean set size 1.18

### 3. Per-site reliability
Accuracy is reported as a *distribution across sites*, not one headline
number. Every site gets a Wilson 95% confidence interval; below `n=30`
cases the UI shows raw counts instead of a misleading percentage. Sites with
flagged drift are surfaced for review before their grades are acted on.

### 4. Tamper-evident ledger
Every clinical decision is appended to a SHA-256 hash chain, signed with
Ed25519 over RFC-8785 canonical JSON, before the result is ever shown to
the operator. The database enforces append-only with SQL triggers.
Verification re-walks and recomputes the *entire* chain — it never trusts a
stored flag — and a signed checkpoint lets an outside party prove history was
rewritten, even against someone with raw database access.

### Offline is the normal case, not an error
No network required, and the UI never presents a missing one as a fault. Each
encounter is queued on the capture device under its own idempotency key and
replayed in order once connectivity returns, so a retry cannot double-count a
patient. Delivery is at-least-once with server-side dedup — never
exactly-once, which is not a thing we can promise.

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────────┐
│   Browser    │◄────►│  FastAPI API │◄────►│  SQLite + hash-chain │
│  (React/Vite)│ /v1  │  (9 frozen   │      │  ledger (Ed25519     │
│              │      │   endpoints) │      │  signed)             │
└──────┬───────┘      └──────────────┘      └─────────────────────┘
       │ localhost only — the image never leaves the device
       ▼
┌──────────────────────┐
│  Inference sidecar    │   ConvNeXt-Tiny (DR grade) +
│  (netra/sidecar)      │   QuickQual (quality gate) +
│                        │   conformal wrapper (MAPIE)
└──────────────────────┘
```

The sidecar is deliberately **not** a tenth API endpoint: the spec forbids
uploading the fundus image at all, so grading happens in a separate local
process on `127.0.0.1`, and the nine `/v1` endpoints stay frozen.

## Tech stack

| Layer | Technology |
|---|---|
| DR classifier | ConvNeXt-Tiny @512px (`timm`), fine-tuned on APTOS |
| Quality gate | DenseNet-121 features + calibrated SVM (QuickQual) |
| Uncertainty | Split-conformal prediction (MAPIE) |
| Backend | FastAPI, SQLModel, SQLite |
| Ledger | SHA-256 hash chain, Ed25519 (`cryptography`), RFC-8785 canonical JSON |
| Frontend | React 18 + TypeScript + Vite, TanStack Query, Recharts, Tailwind |
| Inference | Local sidecar process (stdlib HTTP, loopback-only) |
| Tests | pytest (backend/ML), Vitest (frontend) — 480+ passing |

## Repository layout

```
netra/
  api/        FastAPI app — the nine frozen /v1 endpoints
  ledger/     hash chain, canonical JSON, Ed25519 keys, verify, tamper demo
  db/         SQLModel tables + append-only triggers
  models/     DR classifier, quality gate, conformal wrapper, inference engine
  sidecar/    the on-device inference process (not an API endpoint)
  eval/       QWK, Brier score, Wilson intervals
  ui/
    src/routes/     Capture, Grade, Referrals, Sites, Ledger, Landing
    src/lib/        the real/sim seam, state machines, offline queue
data/         APTOS splits (calibration images only — not redistributed)
docs/, SPEC.md, demo/RUNBOOK.md
```

## Running it locally

Three processes, from the repo root:

```bash
# 1 — API
python -m uvicorn netra.api.main:app --port 8000

# 2 — inference sidecar (the real model; NOT a /v1 endpoint)
export NETRA_DR_CHECKPOINT=artifacts/convnext_tiny_aptos.pt
export NETRA_QUICKQUAL_SVM=artifacts/quality_head_eyeq.pkl
python -m netra.sidecar --calibrate data/aptos/images/calib

# 3 — UI
cd netra/ui && npm run dev
```

Open `http://localhost:5173`.

## Tests

```bash
pytest -q                 # backend + ML
cd netra/ui && npm test    # frontend
npm run build              # production build check
```

## License

See [LICENSE](LICENSE).
