import base64
import io
import wave

import numpy as np
import pytest

from sinyara.audio import decode_audio
from sinyara.errors import SinyaraError
from sinyara.pipeline import Pipeline
from sinyara.schemas import AudioInput, CaseInput


def wav(seconds=1, rate=16000, silent=True):
    samples = np.zeros(int(seconds * rate), dtype=np.int16)
    if not silent:
        samples = (np.sin(np.arange(len(samples)) * 440 * 2 * np.pi / rate) * 5000).astype(np.int16)
    out = io.BytesIO()
    with wave.open(out, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(samples.tobytes())
    return out.getvalue()


def test_decodes_verified_bytes_resamples():
    audio, rate = decode_audio(wav(1, 48000), "recording.wav")
    assert rate == 16000
    assert abs(len(audio) - 16000) < 10


@pytest.mark.parametrize("data,name,code", [(b"not audio", "fraud.mp3", "invalid_audio"), (wav(61), "recording.wav", "audio_too_long"), (wav(), "file.exe", "invalid_audio")], ids=["corrupt", "over-duration", "wrong-extension"])
def test_reject_bad_audio(data, name, code):
    with pytest.raises(SinyaraError) as exc:
        decode_audio(data, name)
    assert exc.value.code == code


def test_silence_not_hallucinated(config, model):
    class NoTranscribe:
        def transcribe(self, audio):
            raise AssertionError("Silent samples should not enter ASR")
    result = Pipeline(config, model=model, transcriber=NoTranscribe()).run("c", CaseInput(audio=AudioInput(name="silence.wav", base64=base64.b64encode(wav()).decode())), lambda _: None)
    assert result.risk == "insufficient"
    assert not result.evidence
    assert any(c.key == "transcription" and c.status == "inconclusive" for c in result.checks)


def test_asr_and_forensic_receive_independent_samples(config, model):
    class ASR:
        version = "fake-ASR"
        def transcribe(self, audio):
            audio[:] = 0
            return [{"text": "Jangan bagikan OTP.", "start": 0, "end": 1}]
    class Forensic:
        version = "fake-forensic"
        def score(self, audio):
            assert np.any(audio != 0)
            return {"conclusion": "inconclusive"}
    result = Pipeline(config, model=model, transcriber=ASR(), forensic=Forensic()).run("c", CaseInput(audio=AudioInput(name="tone.wav", base64=base64.b64encode(wav(silent=False)).decode())), lambda _: None)
    assert result.risk == "low"  # Forensic must not upgrade/lower content risk.
    assert result.evidence[0].start == 0
    assert any(c.key == "forensic" and c.status == "inconclusive" for c in result.checks)
