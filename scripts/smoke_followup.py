"""Real local LLM conversation on synthetic input. No server or API key required."""
import json
import secrets
import time
from pathlib import Path

from sinyara.config import settings
from sinyara.schemas import CaseInput, FollowupInput
from sinyara.store import CaseService

service = CaseService(settings)
try:
    access = service.create(CaseInput(message="Saya petugas bank. Kirim kode OTP Anda sekarang agar rekening tidak diblokir.",
                                     urls=["https://bank.co.id@evil.example.com"]), secrets.token_urlsafe(24))
    service.analyze(access)
    deadline = time.monotonic() + 600
    while True:
        snapshot = service.snapshot(access)
        if snapshot["status"] in {"done", "error"}:
            break
        if time.monotonic() > deadline:
            raise TimeoutError()
        time.sleep(.25)
    assert snapshot["status"] == "done"
    started = time.perf_counter()
    first = service.followup(access, FollowupInput(question="Kenapa pesan dan tautannya perlu dicurigai?"))
    first_seconds = time.perf_counter() - started
    started = time.perf_counter()
    revised = service.followup(access, FollowupInput(question="Kalau begitu apa yang perlu saya lakukan?",
                    context="Pengirim baru mengaku dari bank. Identitasnya belum saya verifikasi."))
    revision = service.snapshot(access)["result"]["revision"]
    assert revision == 2
    report = {"synthetic_only": True, "model": service.pipeline.model.version,
              "first_answer": first.model_dump(), "first_seconds": first_seconds,
              "context_answer": revised.model_dump(), "context_seconds": time.perf_counter() - started,
              "revision": revision, "limitations": "Small integration smoke, not a semantic accuracy benchmark. Human review remains necessary."}
    Path("artifacts/followup-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    service.delete(access)
finally:
    service.close()
