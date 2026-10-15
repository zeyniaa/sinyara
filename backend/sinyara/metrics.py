"""Evaluation utilities: no thresholds are activated in the public product."""
import re

import numpy as np


def word_error_rate(reference: str, hypothesis: str) -> float:
    def tokens(text):
        return re.findall(r"\w+", text.casefold())
    ref, hyp = tokens(reference), tokens(hypothesis)
    if not ref:
        raise ValueError("Reference transcript must not be empty")
    previous = list(range(len(hyp) + 1))
    for i, a in enumerate(ref, 1):
        current = [i]
        for j, b in enumerate(hyp, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1] / len(ref)


def eer_threshold(labels, scores) -> dict:
    """Positive label = bona fide, matching official AASIST class 1 score direction.

    Empirical nearest crossing. Not the interpolated official ASVspoof metric implementation.
    """
    labels, scores = np.asarray(labels, dtype=bool), np.asarray(scores, dtype=float)
    if not len(scores) or not labels.any() or labels.all() or not np.isfinite(scores).all():
        raise ValueError("Need finite scores with human and synthetic examples")
    thresholds = np.concatenate(([-np.inf], np.unique(scores), [np.inf]))
    options = []
    for threshold in thresholds:
        accepted = scores >= threshold
        far = float(accepted[~labels].mean())
        frr = float((~accepted[labels]).mean())
        options.append((abs(far - frr), (far + frr) / 2, float(threshold), far, frr))
    _, eer, threshold, far, frr = min(options)
    return {"empirical_eer": eer, "threshold": threshold, "far": far, "frr": frr,
            "method": "nearest-empirical-crossing"}


def validate_group_split(rows: list[dict]):
    for key in ("speaker_id", "generator_id", "origin_id"):
        dev = {r[key] for r in rows if r["split"] == "dev" and r.get(key) and r[key] != "human"}
        test = {r[key] for r in rows if r["split"] == "test" and r.get(key) and r[key] != "human"}
        if dev & test:
            raise ValueError(f"Leakage across development and test in {key}")
    if {r["split"] for r in rows} != {"dev", "test"}:
        raise ValueError("Both dev and test splits are required")
    for split in ("dev", "test"):
        if {r["label"] for r in rows if r["split"] == split} != {"human", "synthetic"}:
            raise ValueError("Both labels are required per split")
