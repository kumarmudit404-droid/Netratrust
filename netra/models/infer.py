"""The single entrypoint the API will call. Replaces Lane B's simulated gate.

    python -m netra.models.infer path/to/fundus.png

    from netra.models.infer import InferenceEngine
    engine = InferenceEngine()
    result = engine.run("fundus.png")

Returns the model-side fields of `POST /v1/encounters`:
`{quality_verdict, cause, prediction_set | grade, model_version}` plus the
image hash, so the caller never needs to touch the pixels.

**Nothing here invents a clinical output.** Three distinct not-available states
exist, and each is reported as itself rather than collapsed into a guess:

| situation                       | quality_verdict | prediction_set | model_version |
|---------------------------------|-----------------|----------------|---------------|
| gate head missing               | `null`          | `null`         | `unloaded`    |
| gate says reject                | `reject`        | `null`         | gate's own    |
| gate admits, DR checkpoint gone | `usable`        | `null`         | `unloaded`    |

A rejected image is "no result" (BUILD_RULES.md invariant 1): it carries no grade
and no prediction set, and it is NOT an abstention, because nothing was graded.
That matches what Lane A's `POST /v1/encounters` enforces server-side - it
returns 422 if a reject arrives carrying a prediction set.

The image bytes never leave the device; only the SHA-256 and the decisions do
(SPEC.md). `image_sha256` is computed here so the caller does not have to.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import asdict, dataclass

from netra.models.abstain import AbstainDecision, decide
from netra.models.dr import UNLOADED, DRClassifier, ModelNotLoaded
from netra.models.preprocess import load_image
from netra.models.quality import QualityGate, QuickQualFeatures
from netra.models.thresholds import refer_grades


@dataclass(frozen=True)
class InferenceResult:
    """Exactly the model-side fields of the frozen encounters request."""

    image_sha256: str
    #: usable | borderline | reject, or None when the gate could not run.
    quality_verdict: str | None
    #: focus | exposure | fov_mask, or None.
    cause: str | None
    #: The conformal set, or None when there is no result to report. NEVER an
    #: empty list for "no result" - that reads as a graded empty set.
    prediction_set: list[int] | None
    #: The single grade, or None. None whenever the set is not a singleton.
    grade: int | None
    abstain: bool
    #: `unloaded` when either model is missing. Carries `:untrained` for
    #: weights that were never really trained.
    model_version: str
    #: P(usable) x 1000, or None. Scaled integer: no floats near the ledger.
    quality_score_milli: int | None
    #: Why this result looks the way it does, in one line.
    note: str

    def as_dict(self) -> dict:
        return asdict(self)

    def as_encounter_body(self, site_id: str, device_seq: int) -> dict:
        """The POST /v1/encounters body, minus the Idempotency-Key header.

        Shaped to Lane A's `EncounterRequest`: `image_sha256, gate_verdict,
        cause, prediction_set, model_version, site_id, device_seq`. It raises
        rather than posting a half-formed encounter when the gate never ran -
        there is no verdict to send, and the field is not nullable there.
        """
        if self.quality_verdict is None:
            raise ModelNotLoaded(
                "the quality gate did not run, so there is no gate_verdict to "
                f"post ({self.note})"
            )
        return {
            "image_sha256": self.image_sha256,
            "gate_verdict": self.quality_verdict,
            "cause": self.cause,
            "prediction_set": self.prediction_set,
            "model_version": self.model_version,
            "site_id": site_id,
            "device_seq": device_seq,
        }


def sha256_file(path: str | pathlib.Path) -> str:
    """SHA-256 of the file on disk, streamed."""
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class InferenceEngine:
    """Quality gate, then DR + conformal abstention. Fails loudly, never quietly."""

    def __init__(
        self,
        gate: QualityGate | None = None,
        classifier: DRClassifier | None = None,
        abstention=None,
        pretrained: bool = True,
        refer: tuple[int, ...] | None = None,
    ) -> None:
        # Both are constructed with their own not-available handling, so an
        # engine always builds even with nothing on disk.
        self.gate = gate or QualityGate(
            features=QuickQualFeatures(pretrained=pretrained)
        )
        self.classifier = classifier or DRClassifier()
        #: A conformalized AbstentionWrapper, or None. Without one there is no
        #: valid prediction SET - only an argmax, which is not what this
        #: project reports - so the result abstains and says why.
        self.abstention = abstention
        self.refer = refer_grades() if refer is None else refer

    @property
    def model_version(self) -> str:
        """Both halves, or `unloaded` if either is missing.

        Deliberately not a partial string: a caller writing this into a ledger
        needs to know the whole pipeline was real, not half of it.
        """
        if not self.gate.available or not self.classifier.available:
            return UNLOADED
        return f"{self.gate.model_version}|{self.classifier.model_version}"

    def run(self, image_path: str | pathlib.Path) -> InferenceResult:
        path = pathlib.Path(image_path)
        image_sha256 = sha256_file(path)
        image = load_image(path)

        gate_result = self.gate(image)

        # 1. The gate could not run. No verdict, no grade, nothing invented.
        if gate_result.verdict is None:
            return InferenceResult(
                image_sha256=image_sha256,
                quality_verdict=None,
                cause=gate_result.cause,
                prediction_set=None,
                grade=None,
                abstain=False,
                model_version=UNLOADED,
                quality_score_milli=None,
                note=(
                    "quality gate unavailable: "
                    f"{self.gate.load_error or 'no head loaded'}"
                ),
            )

        # 2. A reject is "no result". Not a grade, and not an abstention -
        #    nothing was graded, so there was nothing to abstain from.
        if gate_result.verdict == "reject":
            return InferenceResult(
                image_sha256=image_sha256,
                quality_verdict="reject",
                cause=gate_result.cause,
                prediction_set=None,
                grade=None,
                abstain=False,
                model_version=self.gate.model_version,
                quality_score_milli=gate_result.score_milli,
                note="image rejected by the quality gate; no grade was computed",
            )

        # 3. Admitted, but there is no DR model to grade with.
        if not self.classifier.available:
            return InferenceResult(
                image_sha256=image_sha256,
                quality_verdict=gate_result.verdict,
                cause=gate_result.cause,
                prediction_set=None,
                grade=None,
                abstain=False,
                model_version=UNLOADED,
                quality_score_milli=gate_result.score_milli,
                note=(
                    "image admitted, but no DR checkpoint is loaded: "
                    f"{self.classifier.load_error or 'no path supplied'}"
                ),
            )

        proba = self.classifier.predict_proba(image)

        # 4. Admitted and graded, but with no conformal calibration there is
        #    no prediction SET - and an argmax is not what this project
        #    reports. Abstain and say so.
        if self.abstention is None or not getattr(
            self.abstention, "conformalized", False
        ):
            return InferenceResult(
                image_sha256=image_sha256,
                quality_verdict=gate_result.verdict,
                cause=gate_result.cause,
                prediction_set=None,
                grade=None,
                abstain=True,
                model_version=self.model_version,
                quality_score_milli=gate_result.score_milli,
                note=(
                    "no conformal calibration, so no prediction set; an argmax "
                    "grade is not reportable"
                ),
            )

        prediction_set = self.abstention.prediction_sets(proba.reshape(1, -1))[0]
        decision: AbstainDecision = decide(prediction_set, self.refer)
        return InferenceResult(
            image_sha256=image_sha256,
            quality_verdict=gate_result.verdict,
            cause=gate_result.cause,
            prediction_set=list(decision.prediction_set),
            grade=decision.grade,
            abstain=decision.abstain,
            model_version=self.model_version,
            quality_score_milli=gate_result.score_milli,
            note=decision.reason,
        )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("image", type=pathlib.Path)
    ap.add_argument("--svm", type=pathlib.Path, default=None)
    ap.add_argument("--checkpoint", type=pathlib.Path, default=None)
    ap.add_argument("--random-init", action="store_true")
    args = ap.parse_args(argv)

    engine = InferenceEngine(
        gate=QualityGate(
            features=QuickQualFeatures(pretrained=not args.random_init),
            svm_path=args.svm,
        ),
        classifier=DRClassifier(checkpoint=args.checkpoint),
    )
    result = engine.run(args.image)
    print(json.dumps(result.as_dict(), indent=2))
    if result.model_version == UNLOADED:
        print(
            "\nmodel_version is 'unloaded': no grade was produced and none was "
            "invented. Supply --svm and --checkpoint."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
