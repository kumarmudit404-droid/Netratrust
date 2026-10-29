# When the model lands — mechanical checklist

For the moment `convnext_tiny_aptos.pt` and `quality_head_eyeq.pkl` come off
the Kaggle run (T-08 + T-09). Everything up to that point is built and green on
a **simulated** gate; this is the list that turns it real.

**This file is a checklist, not a script.** Nothing here has been run — there
are no artifacts yet. Work down it in order and stop at the first step that
does not do what it says.

Order matters, and this is the one part that is not mechanical taste:

```
drop  ->  fit_thresholds (CALIBRATION split only)  ->  conformalize
      ->  verify  ->  swap the UI seam  ->  re-run all gates
```

Thresholds before conformalisation, because the conformal step needs a gate
that already decides `usable / borderline / reject`. Verify before the swap,
because a UI pointed at a model nobody has checked is harder to debug than a
model on its own. And **never** re-fit a threshold after seeing test results —
`.claude/rules/ml.md` and `tracker.md`'s "evaluation drift" risk both say so,
and no hook catches it. Review the diff.

---

## 0. Before you touch anything

- [ ] `pytest -q` is green **now**, on the simulated gate. If it is not, fix
      that first — you will not be able to tell your change from the breakage.
- [ ] `git status` is clean except for Lane C's own work in flight.
- [ ] Note the current head: `curl -s localhost:8000/v1/ledger/checkpoint`.
      The ledger must still verify at the end; this is the number to compare.

---

## 1. Drop the artifacts

Neither loader has a default path — both are **env-var only** — and there is no
`artifacts/` directory in the repo yet. Create one:

```bash
mkdir -p artifacts
# from the Kaggle run's output
cp convnext_tiny_aptos.pt  artifacts/
cp quality_head_eyeq.pkl   artifacts/
```

- [ ] Add `artifacts/` to `.gitignore`. A `convnext_tiny` checkpoint is far too
      large for this repo, and a checkpoint in git history cannot be removed.
- [ ] Also commit the **grown splits** the notebook produced
      (`data/splits/*.json`). They are small, they are already tracked, and the
      calibration split is what step 2 fits on — a threshold fitted against a
      split nobody else has is not reproducible.

### The env vars

| variable | what reads it | what it points at |
|---|---|---|
| `NETRA_DR_CHECKPOINT` | `netra/models/dr.py` (`CHECKPOINT_ENV`) | `artifacts/convnext_tiny_aptos.pt` |
| `NETRA_QUICKQUAL_SVM` | `netra/models/quality.py` | `artifacts/quality_head_eyeq.pkl` |

```bash
export NETRA_DR_CHECKPOINT=artifacts/convnext_tiny_aptos.pt
export NETRA_QUICKQUAL_SVM=artifacts/quality_head_eyeq.pkl
```

For the deployed container these go in `fly.toml`'s `[env]` next to
`NETRA_DB`, and the artifacts have to reach the image — they are **not** copied
by the current `Dockerfile`, which deliberately omits `netra/models` and ships
no weights. Decide then whether they go in the image or on the volume; the
volume is the better answer, because a new checkpoint should not need a rebuild.

### Two failure modes that look like success

Both loaders **report** rather than raise, which is right for a screening app
and means a wrong path is quiet:

- `dr.py` sets `load_error = "no checkpoint at <path>"` and leaves `model =
  None`. `model_version` then reads `unloaded`.
- `quality.py` falls through to `state = "unavailable"`.

So after exporting the variables:

- [ ] Confirm **both** loaded. `model_version` must not be `unloaded`, and must
      not carry `:untrained` — `dr.py` honours a `trained: false` flag, which is
      what `train.py --smoke` writes after two steps. A checkpoint from a smoke
      run will load and must not be used.

---

## 2. Fit the thresholds — calibration split ONLY

```bash
python -m netra.models.fit_thresholds --images data/aptos/images/calib
```

- [ ] It reads the **`calib`** split (`CALIB_SPLIT = "calib"` in
      `fit_thresholds.py`; `dataset.collect` refuses anything else). If you
      find yourself passing a different `--images`, stop.
- [ ] It may **refuse to write**. It did on 2026-10-28, on one-sided scores,
      and that refusal is the tool working: a hand-picked threshold is exactly
      what `SPEC.md` says is not acceptable justification. If it refuses, read
      why and fix the input — do not write `config/thresholds.yaml` by hand.
- [ ] Review the diff to `config/thresholds.yaml` yourself. The keys it may
      move are `quality_gate.usable_min_p` and `quality_gate.reject_max_p`.
      `dr.conformal_confidence` is **0.90 by decision, not by fitting** — if
      the diff touches it, that is a bug.
- [ ] Commit `config/thresholds.yaml` in **its own commit**, with the fitter's
      output in the message. That file is an agreement-only file and its diff
      is the evaluation-drift review.

> The UI mirrors two of these values in `netra/ui/src/lib/clinical.ts`
> (`REFER_GRADES`, `CONFORMAL_CONFIDENCE`) because it cannot read the YAML at
> runtime. `tests/test_integration.py::test_lane_bs_refer_grades_match_config`
> fails if they drift — so if you change `dr.refer_grades`, that test will tell
> you to update the mirror. It is not an optional step.

---

## 3. Conformalize

- [ ] Re-run the conformal step on the **real** probabilities. T-10 is built and
      tested against synthetic ones; `tracker.md` records that conformalising on
      real output waits for T-09.
- [ ] MAPIE v1 order is `fit` -> `conformalize` -> `predict_set`, and
      `predict_set` returns a 3-D `(n, n_classes, n_levels)` bool array even for
      one confidence level (CLAUDE.md). A 2-D assumption here fails silently.
- [ ] Sanity-check the abstention rule on real sets: abstain when the set spans
      more than one **clinical action**, not when it is merely large. `{2,3,4}`
      is wide and must NOT abstain; `{1,2}` is small and must.

---

## 4. Verify the model before any UI touches it

```bash
python -m netra.models.infer path/to/a/real/fundus.png
```

- [ ] A known-good image returns a `quality_verdict` and a `prediction_set`.
- [ ] A deliberately blurred image returns `reject`, with `prediction_set: null`
      and `grade: null`. **This is the clinical invariant**: a failed gate is
      "no result", never a negative result. `POST /v1/encounters` returns 422 if
      a reject arrives carrying a set, so getting this wrong shows up as a 422
      in the UI rather than as a bad grade — but check it here, where the error
      is readable.
- [ ] `model_version` is the real version, not `unloaded`, not `:untrained`.
- [ ] Expected QWK on a local APTOS split is **0.88–0.92**. Anything above
      **0.95 means a leaked split** (`SPEC.md` §2) — go back to the splits, do
      not celebrate.
- [ ] Never put a local split score next to a public leaderboard score
      (CLAUDE.md).

---

## 5. Swap the UI seam — ONE function

**`netra/ui/src/lib/qualityGate.ts`**, the body of `callQualityGate()`, below:

```ts
// TODO: swap for real infer.py — replace everything below this line.
```

That is the only place in `netra/ui` that knows how a verdict is produced.
Everything above the line — the on-device SHA-256, and `assertGateResult` on
the way out — stays.

`GateResult` is already field-for-field equivalent to
`netra.models.infer.InferenceResult`, so the swap is a rename:

| `InferenceResult` | `GateResult` |
|---|---|
| `image_sha256` | `imageSha256` |
| `quality_verdict` | `qualityVerdict` |
| `cause` | `cause` |
| `prediction_set` | `predictionSet` |
| `grade` | `grade` |
| `abstain` | `abstain` |
| `model_version` | `modelVersion` |
| `quality_score_milli` | `qualityScoreMilli` |
| `note` | `note` |

### The one real decision at this step

`infer.py` is Python and the gate runs **on the device**. It cannot be a
`fetch`: the nine endpoints in `SPEC.md` are frozen, none of them grades an
image, and `SPEC.md` forbids uploading the image at all. So the swap is either

- in-browser inference (ONNX/WASM), or
- a local sidecar on the capture device that `callQualityGate` calls.

Pick one and write it down. **Neither is built**, and neither is a small job —
this checklist stops being mechanical here, and that is the honest state of it.

### Then

- [ ] `assertGateResult` stays and keeps enforcing the invariants on the real
      model: reject carries no set and no grade, `[]` is refused rather than
      read as a graded empty set, and the score stays a scaled integer because
      it travels towards a ledger payload where floats are banned.
- [ ] Delete `netra/ui/src/lib/gateSim.ts` and the scenario `<fieldset>` in
      `Capture.tsx` (the one captioned "Simulated gate — Lane C model not wired
      yet"). Nothing else on that screen moves.
- [ ] `SIM_MODEL_VERSION` goes with it. Grep for `simulated` before you finish:
      `scripts/seed_dev.py` uses `simulated-gate@seed` for seeded rows, which is
      correct and stays — seeded data is synthetic and should say so.
- [ ] Remove the "the quality gate is SIMULATED" banner from
      `demo/RUNBOOK.md` §top — **and only then**.

---

## 6. Re-run every gate, as separate commands

```bash
pytest -q
cd netra/ui && npm run build
cd netra/ui && npm test
```

- [ ] All three green. A step is not done until all three pass.
- [ ] The live suite, against a running API:
      `VITE_NETRA_LIVE=1 VITE_API_BASE=http://127.0.0.1:8000 npx vitest run src/lib/api/live.test.ts`

      It already walks the whole path **through the seam**
      (`the full capture path: gate -> encounter -> ledger -> referral ->
      advance`), so it covers the real model the moment it is plugged in. No new
      test is needed for the swap itself.
- [ ] `GET /v1/ledger/verify` still returns `ok:true`, and the head is at or
      above the number you noted in step 0.
- [ ] Walk `demo/RUNBOOK.md` §3 once, end to end, with the real gate. The
      reject case is the one to check hardest: it is the screen the demo turns
      on.

---

## 7. If the artifacts do not arrive

`tracker.md` is explicit: T-09 may not finish by the freeze, and the answer is
**ship the checkpoint you have**. The simulated gate is labelled as simulated on
screen, the runbook says so out loud, and every other claim in the demo — the
ledger, the tamper evidence, the state machine, the per-site Wilson intervals
and the n<30 rule — is real and does not depend on the model.

Do not swap a half-verified model in on the morning of the demo. A labelled
simulation is honest; an unverified model presented as real is not.
