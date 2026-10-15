"""Decode entirely in memory, cap duration while decoding, and keep forensic samples independent."""
import io
from pathlib import Path
from threading import Lock

import av
import numpy as np

from .errors import ModelUnavailable, SinyaraError

FORMATS = {"wav", "mp3", "m4a", "ogg", "opus"}


def decode_audio(data: bytes, name: str) -> tuple[np.ndarray, int]:
    if Path(name).suffix.lower().lstrip(".") not in FORMATS:
        raise SinyaraError("invalid_audio", "Gunakan WAV, MP3, M4A, OGG, atau OPUS.")
    samples = []
    total = 0
    try:
        with av.open(io.BytesIO(data), mode="r") as container:
            if not container.streams.audio:
                raise ValueError("no stream")
            stream = container.streams.audio[0]
            # Treat header duration only as an early check; enforce decoded duration too.
            if stream.duration is not None and float(stream.duration * stream.time_base) > 60.05:
                raise SinyaraError("audio_too_long", "Durasi rekaman maksimal 60 detik.")
            resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
            for frame in container.decode(stream):
                for converted in resampler.resample(frame):
                    total += converted.samples
                    if total > 960_800:
                        raise SinyaraError("audio_too_long", "Durasi rekaman maksimal 60 detik.")
                    samples.append(converted.to_ndarray().reshape(-1).copy())
            for converted in resampler.resample(None):
                total += converted.samples
                samples.append(converted.to_ndarray().reshape(-1).copy())
        if total > 960_800:
            raise SinyaraError("audio_too_long", "Durasi rekaman maksimal 60 detik.")
        if not samples or total < 1600:
            raise ValueError("too short")
        waveform = np.concatenate(samples).astype(np.float32)
        if not np.isfinite(waveform).all():
            raise ValueError("nonfinite")
        return waveform, 16000
    except SinyaraError:
        raise
    except (av.FFmpegError, ValueError, IndexError, OverflowError) as exc:
        raise SinyaraError("invalid_audio", "Rekaman tidak dapat dibaca. File mungkin rusak atau bukan audio yang didukung.") from exc


class WhisperTranscriber:
    def __init__(self, model_name="small"):
        self.model_name, self.model = model_name, None
        self.version = f"faster-whisper/{model_name}/cpu-int8"

    def transcribe(self, audio: np.ndarray) -> list[dict]:
        try:
            if self.model is None:
                from faster_whisper import WhisperModel
                self.model = WhisperModel(self.model_name, device="cpu", compute_type="int8", cpu_threads=4)
            segments, _ = self.model.transcribe(audio.copy(), language="id", vad_filter=True,
                                               beam_size=3, condition_on_previous_text=False)
            return [{"text": s.text.strip(), "start": round(s.start, 2), "end": round(s.end, 2)}
                    for s in segments if s.text.strip() and s.no_speech_prob < 0.85]
        except Exception as exc:
            raise ModelUnavailable("Model transkripsi belum tersedia atau gagal memproses rekaman.") from exc


class QwenTranscriber:
    """Qwen ASR in an isolated service/process to avoid Transformers version conflicts.

    Instantiate with a preloaded Qwen3ASRModel inside the ASR worker. Segment boundaries,
    not word alignment: Indonesian is not covered by the optional forced aligner.
    """
    version = "Qwen/Qwen3-ASR-0.6B"

    def __init__(self, model):
        self.model = model

    def transcribe(self, audio: np.ndarray) -> list[dict]:
        result = []
        for start in range(0, len(audio), 15 * 16000):
            part = audio[start:start + 15 * 16000].copy()
            # Skip silence, not a speech/non-speech guarantee.
            if np.sqrt(np.mean(part ** 2)) < 0.0001:
                continue
            outputs = self.model.transcribe(audio=(part, 16000), language="Indonesian")
            text = outputs[0].text.strip()
            if text:
                result.append({"text": text, "start": start / 16000, "end": (start + len(part)) / 16000})
        return result


class AASISTDetector:
    """Official checkpoint, uncalibrated. No fraud or synthetic verdict is returned."""
    version = "clovaai/AASIST/ASVspoof2019LA/experimental"

    def __init__(self, directory: str):
        self.directory, self.model = Path(directory), None

    def score(self, waveform: np.ndarray) -> dict:
        import importlib.util
        import json
        import torch
        model_path = self.directory / "models/AASIST.py"
        weights = self.directory / "models/weights/AASIST.pth"
        config = self.directory / "config/AASIST.conf"
        if not all(p.is_file() for p in (model_path, weights, config)):
            raise ModelUnavailable("Bobot AASIST belum disiapkan. Jalankan skrip setup AASIST.")
        if self.model is None:
            spec = importlib.util.spec_from_file_location("sinyara_aasist", model_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.model = module.Model(json.loads(config.read_text())["model_config"]).to("cpu").eval()
            self.model.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
        # Follow original 64,600-sample padding, without denoising. Evaluate distinct windows.
        scores = []
        for start in range(0, len(waveform), 64600):
            part = waveform[start:start + 64600].copy()
            if len(part) < 64600:
                part = np.tile(part, 64600 // len(part) + 1)[:64600]
            with torch.inference_mode():
                _, logits = self.model(torch.from_numpy(part).unsqueeze(0))
            scores.append(float(logits[0, 1].item()))  # official evaluation uses class 1 bonafide score
        return {"raw_bonafide_score": float(np.mean(scores)), "windows": len(scores),
                "conclusion": "inconclusive", "calibrated": False}


class RemoteQwenTranscriber:
    """Separate Qwen-ASR Space: JSON only, never Gradio upload/file components."""
    version = "Qwen/Qwen3-ASR-0.6B/remote-isolated"

    def __init__(self, space: str):
        self.space = space

    def transcribe(self, audio: np.ndarray) -> list[dict]:
        import base64
        import json
        import wave
        if not self.space:
            raise ModelUnavailable("Space Qwen-ASR belum dikonfigurasi.")
        try:
            from gradio_client import Client
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
            client = Client(self.space, verbose=False)
            output = json.loads(client.predict(base64.b64encode(buffer.getvalue()).decode(), api_name="/transcribe"))
            if "error" in output:
                raise ValueError()
            segments = output["segments"]
            duration = len(audio) / 16000
            if any(not (0 <= s["start"] < s["end"] <= duration + .1) or not isinstance(s["text"], str) or len(s["text"]) > 3000 for s in segments):
                raise ValueError()
            return segments
        except Exception as exc:
            raise ModelUnavailable("Qwen-ASR publik belum tersedia, kuota habis, atau transkripsi gagal.") from exc
