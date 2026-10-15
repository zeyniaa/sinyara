"""Generated non-speech smoke check, not an Indonesian ASR accuracy benchmark."""
import json
import time
from pathlib import Path

import numpy as np

from sinyara.audio import AASISTDetector, WhisperTranscriber

waveform = np.random.default_rng(42).normal(0, .00001, 16000).astype(np.float32)
started = time.perf_counter()
transcriber = WhisperTranscriber()
segments = transcriber.transcribe(waveform.copy())
forensic = AASISTDetector(".cache/aasist").score(waveform.copy())
report = {"synthetic_input": "1s near-silence, seed 42; no human recording", "asr_model": transcriber.version,
          "segments": segments, "forensic": forensic, "elapsed_seconds": time.perf_counter() - started,
          "limitations": "Loading/inference smoke only. No WER, EER, voice identity or fraud accuracy claim."}
Path("artifacts/audio-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
