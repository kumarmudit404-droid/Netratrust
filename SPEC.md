# NetraTrust — build specification

Frozen 2026-10-27. Changes require team agreement and a separate commit.

## The claim we are proving

Gating a DR classifier on learned image admissibility recovers specificity on
admitted images, at a measurable and reported coverage cost, and a classical
baseline does not achieve the same.

Everything else in this build exists to make that claim demonstrable,
auditable, and honest about its limits.

## What we do not claim

- No improvement in vision outcomes.
- No superiority to ARDA or any commercial algorithm.
- The DR classifier is not our contribution. It is the thing the gate protects.

## Components

### 1. Quality gate  (owner: Lane C — ML & Evaluation)
Input: a fundus image. Output: `{usable | borderline | reject}` + cause +
score in [0,1].

- Primary: QuickQual — frozen `densenet121.tv_in1k` features at 512px
  (mean/std 0.5) + a small SVM head. Published EyeQ test accuracy 0.886,
  AUC 0.9687, kappa 0.811.
- Fallback A: QuickQual-MEME — 10 parameters printed in the paper, nothing to
  download. Use if the released pickle will not load under scikit-learn 1.9.1.
- Fallback B: EFIQA (MIT licence) — 87.55% on EyeQ, and produces a region
  overlay showing where the image is bad, which serves recapture routing.
- Parallel channel: classical OpenCV reason-codes (focus, exposure, FOV mask)
  used to explain WHY an image failed and what to retake. Not the gate itself —
  no published absolute Laplacian threshold for fundus images exists.

Thresholds for usable/borderline/reject are calibrated by sweeping synthetic
cataract degradation until the DR classifier's accuracy collapses. That sweep
is the justification; a hand-picked threshold is not.

### 2. DR classifier  (owner: Lane C — ML & Evaluation)
Input: an admitted image. Output: 5-class severity distribution.

- Backbone: `convnext_tiny.in12k_ft_in1k` at 512px, fine-tuned on APTOS.
- Alternative if time is short: RETFound's already-fine-tuned APTOS checkpoint
  from its `BENCHMARK.md` (Google Drive, no gate). It publishes no metrics, so
  we must re-measure before quoting anything.
- Preprocessing: background removal + resize ONLY. A controlled ablation found
  Ben Graham (0.8260) and CLAHE (0.8238) both BELOW plain background-removal
  + resize (0.8310). Resolution dominates: 128->512 buys +0.164 kappa,
  512->1024 buys +0.013 for 4x compute.
- Expected QWK on a local APTOS split: 0.88-0.92. Anything above 0.95 means a
  leaked split.

### 3. Abstention  (owner: Lane C — ML & Evaluation)
MAPIE 1.6.0, `SplitConformalClassifier` with `conformity_score="lac"`,
`prefit=True`.

Abstain when the prediction set spans more than one CLINICAL ACTION class, not
when the set is merely large. `{0,1}` and `{0,3}` are both size 2 and only the
second is alarming.

### 4. Ledger  (owner: Lane A — Backend & Ledger)
Append-only SQLite table. Each entry:
`idx, prev_hash, payload_hash, payload_json, signer_kid, signature`.

- `payload_hash = SHA-256(rfc8785.dumps(payload))`
- `entry_hash   = SHA-256(prev_hash || payload_hash)`
- Sign the 32-byte entry hash with Ed25519, not the payload.
- `signer_kid` column from day one, for the key-rotation question.
- Append-only enforced by SQLite triggers.
- `GET /ledger/checkpoint` returns a signed head (index + hash + timestamp +
  signature). This is the Certificate-Transparency idea without the tree: an
  external party holding yesterday's checkpoint can prove history was rewritten,
  which a bare chain cannot. ~30 minutes. Do this. Skip the Merkle tree (~1 day).

### 5. Offline sync  (owner: Lane A — Backend & Ledger)
At-least-once delivery with server-side idempotent dedup. Never claim
exactly-once.

- Client sends `Idempotency-Key` (UUID) per event.
- 409 if the same key is still in flight; 422 if the key is reused with a
  different payload.
- Device owns `device_seq`; server owns ledger `seq`.
- Connectivity flag lives SERVER-SIDE so the demo survives a page navigation
  and a second browser tab.
- We have no merge conflicts because screening events are immutable append-only
  facts. Say this; it is an architectural strength, not a dodge.

### 6. Site registry  (owner: Lane A — Backend & Ledger)
A site must pass a local audit before its grades count. Stores gradability rate,
gate-vs-human agreement, grade distribution, pinned model version, drift flag.

### 7. UI  (owner: Lane B — Frontend)
Custom front end in `netra/ui`: Vite + React + TypeScript PWA — Tailwind CSS,
shadcn/ui, TanStack Query, Recharts, vite-plugin-pwa, Framer Motion. Front-end
dependencies are pinned in `netra/ui/package.json`, not `requirements.txt`.
Amended 2026-10-27 by agreement; superseded Streamlit 1.66.1 + Plotly 7.1.0.
Five views: capture + gate verdict; abstention queue; performance dashboard;
ledger verification + tamper demo; offline queue indicator.

- Per-site view: forest plot of Wilson intervals against the pooled line.
  Doubles as the drift monitor. Avoid violins — KDE invents structure at
  realistic per-site n.
- Funnel: each stage labelled with its value and percent of the previous stage.
- Live panels: poll the API on an interval.

### 8. Explicitly excluded
No LLM. No RAG. No federated learning. No blockchain. No differential privacy.
No mTLS — uvicorn does not expose the client certificate to the application, so
it buys nothing we can check, and it cannot authenticate an event captured while
offline. Per-device Ed25519 payload signatures are strictly better here.

## API contract (frozen — build against this)

| Method | Path | Body / returns |
|---|---|---|
| POST | `/v1/encounters` | image hash, gate verdict, cause, prediction set, model version, site, device_seq, Idempotency-Key -> `{encounter_id, ledger_idx}` |
| POST | `/v1/referrals` | `{encounter_id}` -> `{referral_id, state:"issued"}` |
| PATCH | `/v1/referrals/{id}` | `{to_state, channel, reason}` -> `{referral_id, state, ledger_idx}` |
| GET | `/v1/ledger/verify` | `{ok:bool, first_bad_index:int|null}` |
| GET | `/v1/ledger/checkpoint` | `{idx, head_hash, ts, signature, signer_kid}` |
| GET | `/v1/sites/{id}/status` | model version, last audit, gradability rate, drift flag |
| POST | `/v1/sites/{id}/audit` | audit payload -> `{passed:bool, pinned_model_version}` |
| GET | `/v1/metrics/sites` | per-site distribution rows (never a mean) |
| GET | `/v1/queue/depth` | `{queued:int, synced:int, attempts:[...]}` |

Referral states: `issued -> contact_attempted(n,channel) -> contacted ->
appointment_offered -> examined` or `abandoned(reason)`.

Images are never uploaded. Only the hash, the decisions and the metadata.

## Definition of done per component
1. It has a test that fails if the behaviour regresses.
2. Its numbers come from `netra/eval/metrics.py`, not from inline computation.
3. It appears in the demo script or it is cut.
