from datetime import datetime, timezone
from typing import Callable

import numpy as np

from .audio import AASISTDetector, RemoteQwenTranscriber, WhisperTranscriber, decode_audio
from .config import Settings
from .errors import InvalidEvidence, ModelUnavailable
from .llm import LanguageModel, OllamaModel, assess
from .schemas import CaseInput, Check, Evidence, Progress, Result, Risk
from .urls import inspect_urls

LABELS = {"secret_request": "Permintaan data rahasia", "payment_request": "Permintaan pembayaran",
          "urgency": "Tekanan untuk segera bertindak", "impersonation": "Klaim identitas belum terverifikasi",
          "secrecy": "Permintaan merahasiakan percakapan", "other": "Perlu verifikasi",
          "protective_context": "Konteks peringatan atau edukasi"}
SUMMARY = {
    Risk.HIGH: "Ada indikator risiko tinggi pada isi yang diberikan. Tunda tindakan dan verifikasi melalui jalur resmi.",
    Risk.VERIFY: "Ada hal yang perlu diverifikasi sebelum kamu melanjutkan.",
    Risk.LOW: "Belum ditemukan indikator kuat pada bagian yang berhasil diperiksa. Ini bukan jaminan aman.",
    Risk.INSUFFICIENT: "Bukti belum cukup untuk menyimpulkan risiko isi percakapan. Periksa keterbatasan di bawah."}
STEPS = ["Jangan membagikan OTP, PIN, kata sandi, atau data rekening.",
         "Hubungi pihak terkait melalui nomor atau aplikasi resmi yang kamu cari sendiri.",
         "Tunda pembayaran dan minta bantuan orang yang kamu percaya jika masih ragu."]


class Pipeline:
    def __init__(self, config: Settings, model: LanguageModel | None = None, transcriber=None, forensic=None):
        self.config = config
        if config.llm_provider != "ollama" and model is None:
            raise ValueError("Non-Ollama providers require an explicitly preloaded model adapter.")
        self.model = model or OllamaModel(config)
        if config.asr_provider not in {"whisper", "qwen-remote"}:
            raise ValueError("SINYARA_ASR_PROVIDER must be whisper or qwen-remote")
        self.transcriber = transcriber or (RemoteQwenTranscriber(config.asr_space) if config.asr_provider == "qwen-remote" else WhisperTranscriber(config.whisper_model))
        self.forensic = forensic or (AASISTDetector(config.aasist_dir) if config.aasist_enabled else None)

    def run(self, case_id: str, data: CaseInput, progress: Callable[[Progress], None],
            context: str = "", revision: int = 1) -> Result:
        # Real progress counts completed stages, not elapsed-time predictions.
        total = 3 + (3 if data.audio else 0)
        completed = 0

        def stage(key, detail, done=False):
            nonlocal completed
            if done:
                completed += 1
            progress(Progress(stage=key, detail=detail, completed=completed, total=total))

        evidence, checks, limitations, models = [], [], [], {}
        sources = {}
        segment_sources = {}
        if data.message:
            sources["message"] = data.message
        if context:
            sources["context"] = context
        stage("urls", "Memeriksa struktur tautan tanpa membuka halaman tujuan.")
        url_evidence, url_checks = inspect_urls(data.urls)
        evidence.extend(url_evidence)
        checks.extend(url_checks)
        if data.urls:
            limitations.append("Halaman tujuan, kepemilikan domain, dan reputasi eksternal tautan belum diperiksa.")
        stage("urls", "Pemeriksaan struktur tautan selesai.", True)

        if data.audio:
            stage("decode", "Memvalidasi isi file dan durasi rekaman.")
            waveform, _ = decode_audio(data.audio.decode(), data.audio.name)
            stage("decode", "Rekaman berhasil dibaca.", True)
            stage("transcription", "Mengubah ucapan menjadi teks. Unduhan model pertama bisa memerlukan waktu.")
            if float(np.sqrt(np.mean(waveform ** 2))) < 0.0001:
                segments = []
                checks.append(Check(key="transcription", title="Transkripsi suara", status="inconclusive", detail="Rekaman senyap atau tidak memiliki ucapan yang dapat dikenali."))
            else:
                try:
                    segments = self.transcriber.transcribe(waveform.copy())
                    models["asr"] = self.transcriber.version
                    checks.append(Check(key="transcription", title="Transkripsi suara", status="done" if segments else "inconclusive",
                                        detail="Transkrip dapat mengandung kesalahan. Waktu menunjuk rentang segmen, bukan setiap kata." if segments else "Tidak ada ucapan yang dapat dikenali. Jangan menarik kesimpulan dari rekaman ini."))
                except ModelUnavailable as exc:
                    segments = []
                    checks.append(Check(key="transcription", title="Transkripsi suara", status="unavailable", detail=str(exc)))
            for i, segment in enumerate(segments):
                sid = f"audio-{i + 1}"
                sources[sid] = segment["text"]
                segment_sources[sid] = segment
            limitations.append("Transkripsi dapat keliru, terutama pada rekaman bising, dialek, atau kompresi. Cocokkan bukti dengan rekaman asli.")
            stage("transcription", "Tahap transkripsi selesai.", True)
            stage("forensic", "Memeriksa ketersediaan analisis suara sintetis.")
            if self.forensic:
                try:
                    self.forensic.score(waveform.copy())
                    models["forensic"] = self.forensic.version
                    detail = "AASIST dijalankan. Hasil eksperimental belum dapat disimpulkan: ambang untuk rekaman Indonesia dan audio terkompresi belum dikalibrasi."
                    status = "inconclusive"
                except (ModelUnavailable, RuntimeError, ImportError, OSError, ValueError):
                    detail, status = "Model forensik belum tersedia atau gagal memproses rekaman.", "unavailable"
            else:
                detail, status = "Model forensik belum diaktifkan. Keaslian suara belum diperiksa.", "unavailable"
            checks.append(Check(key="forensic", title="Indikasi suara sintetis · eksperimental", status=status, detail=detail))
            limitations.append("Suara sintetis tidak otomatis berarti penipuan; suara manusia juga dapat membawa permintaan berisiko.")
            stage("forensic", "Tahap forensik selesai; hasil ditampilkan terpisah.", True)
        else:
            checks.extend([Check(key="transcription", title="Transkripsi suara", status="skipped", detail="Tidak ada rekaman yang diberikan."),
                           Check(key="forensic", title="Indikasi suara sintetis", status="skipped", detail="Tidak ada rekaman yang diberikan.")])

        risk = Risk.INSUFFICIENT
        stage("language", "Memeriksa konteks, permintaan, dan tekanan dalam isi percakapan.")
        if sources:
            try:
                assessment = assess(self.model, sources)
                risk = assessment.risk
                models["llm"] = self.model.version
                for i, finding in enumerate(assessment.findings):
                    sid = finding.source_id
                    segment = segment_sources.get(sid, {})
                    evidence.append(Evidence(id=f"content-{i + 1}", source="audio" if sid in segment_sources else sid,
                        quote=finding.quote, explanation=finding.explanation, indicator=finding.indicator,
                        start=segment.get("start"), end=segment.get("end")))
                # Keep a source even when the model finds no indicators, for meaningful follow-up.
                if not assessment.findings:
                    sid = next(iter(sources))
                    segment = segment_sources.get(sid, {})
                    evidence.append(Evidence(id="content-source", source="audio" if sid in segment_sources else sid,
                        quote=sources[sid], explanation="Bagian isi yang diperiksa; model belum menemukan indikator kuat.",
                        indicator="source", start=segment.get("start"), end=segment.get("end")))
                checks.append(Check(key="content", title="Isi dan konteks", status="done", detail="Kutipan dan referensi sumber telah diperiksa. Penjelasan model tetap dapat keliru."))
            except (ModelUnavailable, InvalidEvidence) as exc:
                checks.append(Check(key="content", title="Isi dan konteks", status="unavailable" if isinstance(exc, ModelUnavailable) else "limited", detail=str(exc)))
                limitations.append(str(exc))
        else:
            checks.append(Check(key="content", title="Isi dan konteks", status="skipped", detail="Tidak ada isi pesan atau transkrip yang dapat dinilai."))
        # Structural URL warnings can warrant verification, never a fraud verdict by themselves.
        if risk in {Risk.LOW, Risk.INSUFFICIENT} and any(e.indicator in {"url_warning", "url_unknown"} for e in evidence):
            risk = Risk.VERIFY
        if any(c.key == "content" and c.status in {"limited", "unavailable"} for c in checks):
            limitations.append("Ringkasan hanya mencakup pemeriksaan yang selesai; analisis isi belum lengkap.")
        stage("language", "Pemeriksaan isi selesai.", True)
        stage("validation", "Memeriksa referensi bukti dan menyusun langkah verifikasi.")
        limitations.append("Sinyara memberi indikator, bukan kepastian identitas, keaslian, atau keamanan. Jangan gunakan hasil sebagai satu-satunya dasar keputusan.")
        result = Result(case_id=case_id, risk=risk, summary=SUMMARY[risk], evidence=evidence, checks=checks,
                        limitations=list(dict.fromkeys(limitations)), next_steps=STEPS, models=models,
                        created_at=datetime.now(timezone.utc).isoformat(), revision=revision)
        stage("done", "Pemeriksaan selesai.", True)
        return result
