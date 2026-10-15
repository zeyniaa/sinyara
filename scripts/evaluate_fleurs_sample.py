"""One public, attributed FLEURS Indonesian sample: ASR integration smoke, not a benchmark.

Downloads only the first WAV from the streaming archive, not the full 451 MB archive.
The archive path is fixed to the official CC BY 4.0 dataset; uploads never use this path.
"""
import csv
import hashlib
import io
import json
import tarfile
import time
from pathlib import Path
from urllib.request import urlopen

import av
import numpy as np

from sinyara.audio import AASISTDetector, WhisperTranscriber, decode_audio
from sinyara.metrics import word_error_rate

BASE = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/id_id/"
with urlopen(BASE + "test.tsv", timeout=60) as response:
    rows = list(csv.reader(io.StringIO(response.read().decode("utf-8")), delimiter="\t"))
with urlopen(BASE + "audio/test.tar.gz", timeout=90) as response:
    with tarfile.open(fileobj=response, mode="r|gz") as archive:
        for member in archive:
            if member.isfile() and member.name.endswith(".wav"):
                if member.size > 10 * 1024 * 1024:
                    raise ValueError("Unexpected large sample")
                name = Path(member.name).name
                data = archive.extractfile(member).read()
                break
        else:
            raise ValueError("No sample found")
row = next(row for row in rows if name in row)
reference = row[2]
directory = Path(".cache/fleurs")
directory.mkdir(parents=True, exist_ok=True)
(directory / name).write_bytes(data)
audio, rate = decode_audio(data, name)
rng = np.random.default_rng(42)
noise = rng.normal(0, 1, len(audio)).astype(np.float32)
noise *= np.sqrt(np.mean(audio ** 2)) / (np.sqrt(np.mean(noise ** 2)) * 10 ** (10 / 20))
noisy = np.clip(audio + noise, -1, 1).astype(np.float32)
buffer = io.BytesIO()
with av.open(buffer, mode="w", format="mp3") as output:
    stream = output.add_stream("libmp3lame", rate=16000)
    stream.layout = "mono"
    stream.bit_rate = 64000
    frame = av.AudioFrame.from_ndarray(audio.reshape(1, -1), format="fltp", layout="mono")
    frame.sample_rate = 16000
    for packet in stream.encode(frame):
        output.mux(packet)
    for packet in stream.encode(None):
        output.mux(packet)
compressed, _ = decode_audio(buffer.getvalue(), "sample.mp3")
transcriber = WhisperTranscriber()
detector = AASISTDetector(".cache/aasist")
records = []
for variant, waveform in [("clean-wav", audio), ("noise-10dB-seed42", noisy), ("mp3-64kbps", compressed)]:
    started = time.perf_counter()
    segments = transcriber.transcribe(waveform.copy())
    transcript = " ".join(s["text"] for s in segments)
    forensic = detector.score(waveform.copy())
    record = {"variant": variant, "transcript": transcript, "wer": word_error_rate(reference, transcript),
              "segments": segments, "forensic": forensic, "latency_seconds": time.perf_counter() - started}
    records.append(record)
    print(json.dumps({"variant": variant, "wer": record["wer"], "latency": record["latency_seconds"]}), flush=True)
report = {"dataset": "google/fleurs", "subset": "id_id", "split": "test", "filename": name,
          "source": "https://huggingface.co/datasets/google/fleurs", "license": "CC BY 4.0",
          "attribution": "FLEURS, Conneau et al., Google, 2022; no audio bundled in repository",
          "sha256": hashlib.sha256(data).hexdigest(), "duration_seconds": len(audio) / rate,
          "reference": reference, "asr_model": transcriber.version, "records": records,
          "limitations": ["One recording, three transformations of the same speaker. Not a representative WER estimate.",
                          "No human/synthetic labels for EER; AASIST raw scores are uncalibrated and inconclusive.",
                          "This sample must not be reused as an independent holdout after development on it."]}
Path("artifacts/fleurs-sample-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"source_file": name, "output": "artifacts/fleurs-sample-smoke.json"}))
