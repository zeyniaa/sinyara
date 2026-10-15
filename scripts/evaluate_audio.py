"""Evaluate consented, labelled recordings. Never bundles personal audio in the repository."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from sinyara.audio import AASISTDetector, WhisperTranscriber, decode_audio
from sinyara.metrics import eer_threshold, validate_group_split, word_error_rate

parser = argparse.ArgumentParser()
parser.add_argument("manifest", help="CSV: path,split,label,speaker_id,generator_id,origin_id,codec,reference,consent")
parser.add_argument("--output", default="artifacts/private/audio-evaluation.json")
parser.add_argument("--aasist-dir", default=".cache/aasist")
args = parser.parse_args()
manifest = Path(args.manifest).resolve()
rows = list(csv.DictReader(manifest.open(encoding="utf-8")))
validate_group_split(rows)
if any(r.get("consent") != "yes" for r in rows):
    raise ValueError("All recordings require consent=yes; confirm the dataset license separately")
if not any(r["codec"].lower() in {"mp3", "m4a", "opus", "ogg"} for r in rows if r["split"] == "test"):
    raise ValueError("Include compressed audio in the holdout")
asr, detector = WhisperTranscriber(), AASISTDetector(args.aasist_dir)
records = []
for i, row in enumerate(rows):
    path = (manifest.parent / row["path"]).resolve()
    audio, _ = decode_audio(path.read_bytes(), path.name)
    score = detector.score(audio)["raw_bonafide_score"]
    segments = asr.transcribe(audio.copy())
    hypothesis = " ".join(s["text"] for s in segments)
    records.append({"id": i, "split": row["split"], "label": row["label"], "codec": row["codec"],
                    "score": score, "wer": word_error_rate(row["reference"], hypothesis) if row["reference"] else None})
dev = [r for r in records if r["split"] == "dev"]
holdout = [r for r in records if r["split"] == "test"]
selection = eer_threshold([r["label"] == "human" for r in dev], [r["score"] for r in dev])
threshold = selection["threshold"]
human = [r for r in holdout if r["label"] == "human"]
synthetic = [r for r in holdout if r["label"] == "synthetic"]
report = {"dev_selection": selection, "test_far": float(np.mean([r["score"] >= threshold for r in synthetic])),
          "test_frr": float(np.mean([r["score"] < threshold for r in human])),
          "test_empirical_eer": eer_threshold([r["label"] == "human" for r in holdout], [r["score"] for r in holdout])["empirical_eer"],
          "records": records, "public_threshold_activated": False,
          "limitations": "Nearest empirical EER, not the official interpolated ASVspoof evaluation. Report per codec and dialect, sample size and confidence intervals before release."}
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"output": args.output, "samples": len(records), "public_threshold_activated": False}))
