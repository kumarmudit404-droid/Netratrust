# NetraTrust — 3-minute demo runbook

One presenter, one browser, one terminal. Read §1 the day before, §2 ten
minutes before, §3 on stage.

The claim being demonstrated, from `SPEC.md`: **gating a DR classifier on
learned image admissibility recovers specificity on admitted images, at a
measurable and reported coverage cost.** Everything below exists to make that
auditable. What the demo must never imply: better vision outcomes, or
superiority to any commercial algorithm.

> **The quality gate is the real model, through a local sidecar.** Start
> `python -m netra.sidecar` before the demo (§2). If it is not reachable when
> Capture runs, the screen falls back to a labelled simulated verdict rather
> than failing the demo — say so out loud if that banner appears. See §6.

---

## 1. Before the demo

### Reset the data

The seed is idempotent: run twice and the second run writes nothing. But a
rehearsal, the test suites and the live API all APPEND to the ledger, so by
demo time `site-07` will not match the table in §4. Reset deliberately:

```bash
# from the repo root
.venv/Scripts/python scripts/seed_dev.py --force     # Windows
python scripts/seed_dev.py --force                   # Linux / macOS
```

Expected tail:

```
  site-03  n= 34  admitted= 29  abstained= 3
  site-07  n= 40  admitted= 33  abstained= 4
  site-12  n= 12  admitted= 10  abstained= 1  n < 30, rate suppressed
  site-21  n= 31  admitted= 20  abstained= 5  drift flagged
ledger       124 entries, head ...
verify       ok
```

`--force` empties every table and seeds again. It does **not** delete the
file, so it is safe to run with the API already up — a running uvicorn sees
the reset immediately. Without `--force` the script refuses to touch a
populated database, which is the behaviour you want on the deployed volume and
not the one you want on a rehearsal machine.

### Start it

Three terminals, all from the repo root:

```bash
# 1 — API
.venv/Scripts/python -m uvicorn netra.api.main:app --port 8000

# 2 — UI
cd netra/ui && npm run dev

# 3 — gate sidecar (the real model; NOT part of the API, NOT a /v1 endpoint)
export NETRA_DR_CHECKPOINT=artifacts/convnext_tiny_aptos.pt      # bash
export NETRA_QUICKQUAL_SVM=artifacts/quality_head_eyeq.pkl
.venv/Scripts/python -m netra.sidecar --calibrate data/aptos/images/calib
```

```powershell
# terminal 3, PowerShell
$env:NETRA_DR_CHECKPOINT = "artifacts\convnext_tiny_aptos.pt"
$env:NETRA_QUICKQUAL_SVM = "artifacts\quality_head_eyeq.pkl"
.venv\Scripts\python -m netra.sidecar --calibrate data\aptos\images\calib
```

`--calibrate` is what turns an abstention into a real prediction set — it
conformalizes on the calibration split, which is the only split it will ever
read (`MODEL_LANDING.md` §3). Leave it off and the sidecar still gates and
grades; it will abstain and say why on every usable image, which is a less
satisfying demo but not a wrong one. It takes a few seconds; watch for
`conformalized  True` in terminal 3's own startup log before moving on.

Open **http://localhost:5173**. The Vite dev server proxies `/v1` to
`127.0.0.1:8000`, so the browser is same-origin and CORS is not in the path.
The sidecar is a separate origin (`127.0.0.1:8731`) that Capture calls
directly — see `netra/ui/src/lib/qualityGate.ts`.

### Check it, before anyone is watching

```bash
curl -s http://localhost:5173/v1/ledger/verify     # {"ok":true,"first_bad_index":null}
curl -s http://localhost:5173/v1/ledger/checkpoint # idx + head_hash + signature
curl -s http://127.0.0.1:8731/health               # gate_loaded, classifier_loaded, conformalized all true
```

Have a fundus image on the desktop ready to pick — a real one, and a
deliberately blurred copy of it. Any JPEG or PNG works for the usable case;
for the reject case the image needs to actually be out of focus, because the
gate is real now and is not reading a dropdown. The image is hashed in the
browser and **never uploaded** either way — say that while you pick it.

---

## 2. Ten minutes before

- [ ] `--force` re-seed done, `verify` returns `ok:true`
- [ ] All three terminals running; `http://localhost:5173` loads;
      `curl http://127.0.0.1:8731/health` shows `conformalized: true`
- [ ] A fourth terminal open at the repo root, for the tamper command
- [ ] A real fundus image on the desktop, and a deliberately blurred copy of it
- [ ] Browser zoom at 100%, one tab only
- [ ] The recorded fallback video is on this machine, not in the cloud (§5)
- [ ] You know that the tamper step is not undone until the next `--force`
      reset, so a second run needs one (and that it does not need the API
      stopped)

---

## 3. The path, in order

Times are cumulative. Rehearse once with a timer; the tamper step is the one
that always runs long.

### 0:00 — Capture, and a gate that refuses (0:35)

Go to **Capture**.

1. Pick the good fundus image. Point out the `sha256 ...` line: *"that is all
   that leaves the device — the gate runs locally, through a sidecar on this
   machine, and this screen never uploads the picture."*
2. Press **Take another image** and pick the blurred copy instead.

   **This is the most important screen in the demo.** Say the line:
   *"A failed quality gate is not a negative result. It is no result."* The
   screen shows the cause and offers **Take another image** as the primary
   action, and renders **no grade, no prediction set and no referral control**.
   There is nothing to click that would produce a diagnosis.
3. Pick the good image again, then press **Record encounter**.

   The confirmation line shows `encounter enc-… · ledger idx N`. Note the
   index: *"the ledger entry was written before that response came back."*
   If a yellow SIMULATED banner appears instead, the sidecar is not reachable
   — say so, and check terminal 3.

### 0:35 — Grade and abstention (0:30)

Press **View grade**, or go to **Grade**.

- Grade 3 → referable. Press **Issue referral**. It returns
  `referral ref-… · state issued`.

  **Do not skip this**: there is no list endpoint in the frozen nine, so the
  Referrals view can only show a referral raised in this session. Skip it and
  §2:10 has nothing to drive.
- Go back to Capture, choose **"Usable — set spans an action boundary {1,2}"**,
  record it, and open Grade again. It shows **ABSTAIN**, and the reason:
  the prediction set spans two different clinical actions.

  The line to say: *"`{2,3,4}` is a wider set than `{1,2}` and we do not
  abstain on it, because every member means refer. Set size is not the
  trigger — crossing the refer / do-not-refer boundary is."* An abstention
  routes to human review and **issues no referral**.

### 1:05 — Ledger verify (0:20)

Go to **Ledger**. Press **Verify**.

`ok: true`, `first_bad_index: null`, and the signed checkpoint: index, head
hash, timestamp, Ed25519 signature, `signer_kid`.

*"The checkpoint is the Certificate-Transparency idea without the tree:
anyone holding yesterday's checkpoint can prove history was rewritten."*

### 1:25 — The tamper demo (0:45) — **the one that convinces people**

This step is one-way within a run: the break is not undone until the next
`--force` reset (see below). That is why it comes after the capture and the
referral have been created, and why the restore is a between-runs step.

Leave the Ledger view open. In the third terminal:

```bash
.venv/Scripts/python -m netra.ledger.tamper --seq 60
```

Pick any index below the current head. 60 is mid-chain in a freshly seeded
database, which reads better than corrupting the last entry.

The command prints what it did. Press **Verify** again in the browser:

```
ok: false    first_bad_index: 60
```

Say why this is not a trick: *"that command had to DROP the append-only
trigger to make the edit, put it back, and it still cannot forge the chain —
it would need the device's Ed25519 private key. The triggers stop the
application from rewriting history. The hash chain and the signatures are what
survive someone with direct database access."*

There is deliberately **no endpoint** that corrupts the ledger. It is a
command-line module, not a route, because a "corrupt the ledger" route in a
deployed build would be a liability.

**Do NOT restore it here.** The only reset is `seed_dev.py --force`, which
deletes the database — including the encounter and the referral you just
created on stage, so the next two steps would break with a 404 on a referral
that no longer exists.

Leave the break in place. Nothing in the remaining 90 seconds reads the
chain's validity: Referrals works from the create and patch responses, and
Sites reads the encounters table. The only cost is that the Ledger view keeps
saying `ok:false` if you go back to it — which is the correct answer, and worth
saying out loud: *"that stays broken until someone deliberately resets it, and
that is the point."*

Reset afterwards, between runs: `python scripts/seed_dev.py --force`. You do
not need to stop the API to do it.

### 2:10 — Referral advances (0:25)

Go to **Referrals**. It shows the referral you issued at 0:35, at **issued**.

> The seeded referral (at `contacted`) is in the ledger but is deliberately
> **not** on this screen: SPEC.md freezes the nine endpoints and none of them
> lists referrals, so the view tracks the create and patch responses from this
> session only. That limitation is stated on the screen itself. If Referrals
> says "No referral in this session", you skipped **Issue referral** at 0:35.

Advance it: **issued → contact_attempted** (pick a channel, e.g. phone) **→
contacted → appointment_offered → examined**.

Each transition returns a new `ledger_idx` — point at one: *"every transition
is its own ledger entry. The referral row caches the current state; the
history is append-only and cannot be rewritten."*

At **examined** the controls are gone: it is terminal. *"The state machine is a
transition table on the server, not an `if` in a screen — a client cannot
invent a state, and cannot skip one either."* If you want to show the refusal,
the API answers **409** for a skipped or backwards move:

```bash
curl -s -X PATCH http://localhost:5173/v1/referrals/<id>   -H "Content-Type: application/json" -H "Idempotency-Key: $(uuidgen)"   -d '{"to_state":"contacted","channel":null,"reason":null}'
# {"detail":"'examined' is terminal; no further transition is possible"}
```

### 2:35 — Sites, and the n<30 rule (0:25)

Go to **Sites**. The forest plot, freshly seeded:

| site | gradability | 95% Wilson | note |
|---|---|---|---|
| site-03 | 29 / 34 | 0.70 – 0.94 | |
| site-07 | 33 / 40 | 0.69 – 0.91 | the demo site |
| site-12 | 10 / 12 | 0.55 – 0.95 | **n < 30 — no bare percentage** |
| site-21 | 20 / 31 | 0.47 – 0.79 | **drift flagged → unpinned** |
| pooled | 93 / 118 | 0.71 – 0.85 | summed counts, NOT a mean of rates |

Two things to land, and they are the whole point of this screen:

1. **site-12 shows counts and an interval, never a bare percentage.** Its n is
   12. *"83% from twelve images is not a number anyone should act on, so we do
   not print it."*
2. **site-21 is drift-flagged, so its audit failed and its model version reads
   "no audited model yet".** A site must pass a local audit before its grades
   count. Its interval is also visibly wider and lower than the others —
   *"this is the site you would go and look at."*

If asked why no violin plots: at realistic per-site n, a KDE invents structure
that is not in the data.

### 3:00 — Stop

Close on the claim, not on the UI: *"the gate's cost is coverage, and we report
it per site with its uncertainty rather than quoting one headline number."*

---

## 4. If something breaks on stage

All of these are fixable without stopping the API — `--force` resets in place.

| symptom | do this |
|---|---|
| `verify` returns `ok:false` unexpectedly | you left a tamper in place. `python scripts/seed_dev.py --force`, then Verify. |
| Capture returns **404 unknown site** | the database was never seeded, or was reset. Run the seed. The UI posts to `site-07`. |
| Sites view is empty | same cause. Seed it. |
| Status strip shows **"N on this device"** | the API is unreachable. The captures are queued on the device, not lost — this is T-19 working. Fix the API; the queue drains itself within 15s. |
| Status strip shows **"N not accepted"** | the server permanently refused a queued capture. Do not retry it on stage; move on. |
| A screen is stuck loading | the API process died. Restart terminal 1; the UI recovers on its next poll. |
| The whole thing is wedged | go to §5. |

---

## 5. Fallbacks, in order of preference

**1 — Deployed URL fails → run locally.** This is the primary fallback and it
is why §1 is written against localhost rather than the deployed URL. The local
path needs no network at all.

**2 — Local run fails → the API alone, in a terminal.** The ledger claims do
not need the UI:

```bash
.venv/Scripts/python scripts/seed_dev.py --force
.venv/Scripts/python -m netra.ledger.verify          # ok: 124 entries verified
.venv/Scripts/python -m netra.ledger.tamper --seq 60
.venv/Scripts/python -m netra.ledger.verify          # FAILED at index 60
```

That is the tamper demo in four commands, with no browser and no server.

**3 — Nothing runs → the recording.** Record a full rehearsal in advance and
keep the file **on the presenting machine**. A fallback that needs the network
is not a fallback. State plainly that it is a recording.

**Do not** improvise around a broken ledger. If `verify` is failing for a
reason you cannot explain in one sentence, go to the recording.

---

## 6. How the model is wired in

The swap happened in exactly one place, and it is done:
**`netra/ui/src/lib/qualityGate.ts`**, the body of `callQualityGate()`. It now
calls the local sidecar (`python -m netra.sidecar`), which wraps
`netra/models/infer.py` and runs on the capture device — the image never
leaves it, and the sidecar is not one of the frozen nine `/v1` endpoints.

Nothing else in `netra/ui` knows how a verdict is produced. `assertGateResult`
holds the real model to the same invariants it held the simulation to: a
reject carries no prediction set and no grade, an empty set is refused rather
than read as a graded empty set, and the score stays a scaled integer because
it travels towards a ledger payload where floats are banned.

If the sidecar is unreachable when Capture runs, the seam falls back to the
labelled simulation automatically — a demo must never hard-fail — and the
Capture screen says so in place of the scenario dropdown, which is gone.
`netra/ui/src/lib/api/live.test.ts` walks the whole path through the seam with
`forceSimulated`, so it is deterministic regardless of whether a sidecar
happens to be running on the machine the suite runs on.

---

## 7. Deploying it

Not required for the demo; §1 runs locally. If you are presenting from a
deployed URL:

```bash
fly deploy
```

First time only, and **read `fly.toml` first** — `app` and `primary_region`
are marked `SET THIS BEFORE LAUNCH` because they are guesses:

```bash
fly launch --no-deploy --copy-config
fly volumes create netra_data --size 1 --region <your region>
fly deploy
fly ssh console -C "python scripts/seed_dev.py"
```

That last command is safe to run more than once: the seed is idempotent and
will not append a second copy of the chain.

One machine, deliberately — a Fly volume attaches to one machine and SQLite has
a single writer. Two machines would each hold their own chain and **both would
pass verify** while having diverged.

`NETRA_DB` and `NETRA_KEYS_DIR` both live under `/data`. The database could be
re-seeded; the Ed25519 private keys could not. Lose them and every entry
already in the chain fails verification with `unknown signer_kid` — the demo's
one claim, broken permanently.
