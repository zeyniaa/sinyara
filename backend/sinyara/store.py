"""Bounded in-memory cases and a single FIFO worker shared by analysis and follow-up."""
import hmac
import contextvars
import secrets
import threading
import time
from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass, field
from typing import Callable

from .config import Settings
from .errors import InvalidEvidence, ModelUnavailable, SinyaraError
from .llm import answer_grounded
from .pipeline import Pipeline
from .schemas import Access, Answer, CaseInput, Evidence, FollowupInput, Progress, Result
from .urls import parse_url


@dataclass
class Case:
    id: str
    token: str
    session: str
    data: CaseInput
    touched: float
    status: str = "created"
    progress: Progress = field(default_factory=Progress)
    result: Result | None = None
    error: dict | None = None
    followups: int = 0
    busy: bool = False
    context: str = ""
    history: list[dict] = field(default_factory=list)


class CaseService:
    def __init__(self, config: Settings, pipeline: Pipeline | None = None, now=time.monotonic):
        self.config, self.pipeline, self.now = config, pipeline or Pipeline(config), now
        self.cases: dict[str, Case] = {}
        self.usage: dict[str, deque] = {}
        self.jobs = deque()
        self.lock = threading.Condition(threading.RLock())
        self.closed = False
        self.active = False
        self.worker = threading.Thread(target=self._work, daemon=True, name="sinyara-model-worker")
        self.worker.start()

    def close(self):
        with self.lock:
            self.closed = True
            for _, _, future in self.jobs:
                future.set_exception(SinyaraError("unavailable", "Server sedang dihentikan.", 503))
            self.jobs.clear()
            self.cases.clear()
            self.lock.notify_all()

    def _purge(self):
        now = self.now()
        expired = {cid for cid, case in self.cases.items() if now - case.touched > self.config.ttl_seconds}
        for cid in expired:
            del self.cases[cid]
        if expired:
            retained = deque()
            for cid, action, future in self.jobs:
                if cid in expired:
                    future.set_exception(SinyaraError("expired", "Kasus kedaluwarsa sebelum diproses.", 404))
                else:
                    retained.append((cid, action, future))
            self.jobs = retained
        for sid in list(self.usage):
            while self.usage[sid] and now - self.usage[sid][0] >= 86400:
                self.usage[sid].popleft()
            if not self.usage[sid]:
                del self.usage[sid]

    def _get(self, access: Access, touch=True) -> Case:
        self._purge()
        case = self.cases.get(access.case_id)
        if case is None or not hmac.compare_digest(case.token, access.token):
            raise SinyaraError("expired", "Kasus tidak ditemukan atau sudah kedaluwarsa. Mulai pemeriksaan baru.", 404)
        if touch:
            case.touched = self.now()
        return case

    def create(self, data: CaseInput, session: str) -> Access:
        if len(session) < 16 or len(session) > 128:
            raise SinyaraError("invalid_session", "Sesi tidak valid. Muat ulang halaman.")
        for url in data.urls:
            parse_url(url)
        if data.audio:
            from .audio import FORMATS
            from pathlib import Path
            if Path(data.audio.name).suffix.lower().lstrip(".") not in FORMATS:
                raise SinyaraError("invalid_audio", "Format rekaman tidak didukung.")
        with self.lock:
            self._purge()
            # Bound total resident payload, not just number of uploads.
            memory = sum(len(c.data.audio.base64) for c in self.cases.values() if c.data.audio)
            if data.audio:
                memory += len(data.audio.base64)
            if len(self.cases) >= self.config.max_cases or memory > self.config.max_audio_memory_mb * 1024 * 1024:
                raise SinyaraError("capacity", "Demo sedang penuh. Coba lagi setelah beberapa kasus kedaluwarsa.", 503)
            if sum(c.session == session for c in self.cases.values()) >= 6:
                raise SinyaraError("capacity", "Terlalu banyak kasus aktif. Hapus kasus lama atau tunggu sampai kedaluwarsa.", 429)
            access = Access(case_id=secrets.token_urlsafe(18), token=secrets.token_urlsafe(32))
            self.cases[access.case_id] = Case(access.case_id, access.token, session, data, self.now())
            return access

    def _enqueue(self, cid, action: Callable):
        if len(self.jobs) >= self.config.max_queue:
            raise SinyaraError("queue_full", "Antrean penuh. Maksimal 10 kasus menunggu. Coba lagi sebentar.", 429)
        future = Future()
        context = contextvars.copy_context()
        self.jobs.append((cid, lambda: context.run(action), future))
        self.lock.notify()
        return future

    def analyze(self, access: Access):
        with self.lock:
            case = self._get(access)
            if case.status in {"queued", "running", "done"}:
                return self.snapshot(access)
            if case.busy:
                raise SinyaraError("busy", "Kasus ini sedang diproses.", 409)
            times = self.usage.setdefault(case.session, deque())
            if len(times) >= self.config.analyses_per_day:
                raise SinyaraError("quota", "Kuota 3 pemeriksaan per sesi dalam 24 jam sudah habis.", 429)
            # Reserve queue before consuming quota; retries while running are idempotent.
            self._enqueue(case.id, lambda: self._analyze_job(access))
            times.append(self.now())
            case.status, case.busy, case.error = "queued", True, None
            case.progress = Progress(stage="queued", detail="Menunggu giliran pemeriksaan.")
            return self.snapshot(access)

    def _analyze_job(self, access):
        with self.lock:
            case = self._get(access, touch=False)
            data, context = case.data, case.context
            case.status = "running"

        def update(progress):
            with self.lock:
                self._get(access, touch=False).progress = progress

        try:
            result = self.pipeline.run(case.id, data, update, context)
            with self.lock:
                current = self._get(access, touch=False)
                current.result, current.status, current.busy = result, "done", False
        except Exception as exc:
            with self.lock:
                if access.case_id in self.cases:
                    current = self._get(access, touch=False)
                    current.status, current.busy = "error", False
                    current.error = {"code": exc.code if isinstance(exc, SinyaraError) else "model_error",
                                     "message": exc.message if isinstance(exc, SinyaraError) else "Pemeriksaan gagal. Coba lagi atau gunakan contoh simulasi."}

    def snapshot(self, access: Access):
        with self.lock:
            # Polling is not user activity: a forgotten tab must still expire.
            case = self._get(access, touch=False)
            progress = case.progress.model_copy()
            if case.status == "queued":
                progress.queue_position = next((i + 1 for i, (cid, _, _) in enumerate(self.jobs) if cid == case.id), 1)
            return {"status": case.status, "progress": progress.model_dump(),
                    "result": case.result.model_dump(mode="json") if case.result else None, "error": case.error}

    def followup(self, access: Access, data: FollowupInput) -> Answer:
        with self.lock:
            case = self._get(access)
            if case.status != "done" or not case.result:
                raise SinyaraError("not_ready", "Tunggu sampai pemeriksaan selesai.", 409)
            if case.busy:
                raise SinyaraError("busy", "Pertanyaan sebelumnya masih diproses.", 409)
            if case.followups >= self.config.followups_per_case:
                raise SinyaraError("followup_quota", "Batas 5 pertanyaan lanjutan untuk kasus ini sudah tercapai.", 429)
            if len(case.context) + len(data.context) > 4000:
                raise SinyaraError("invalid_input", "Total konteks tambahan maksimal 4.000 karakter.")
            future = self._enqueue(case.id, lambda: self._followup_job(access, data))
            case.busy = True
            case.followups += 1
        try:
            return future.result(timeout=self.config.llm_timeout * 4 + 180)
        except TimeoutError as exc:
            raise SinyaraError("timeout", "Pertanyaan masih menunggu model. Coba kembali sebentar.", 503) from exc

    def _followup_job(self, access, data):
        try:
            with self.lock:
                case = self._get(access, touch=False)
                context = (case.context + "\n" + data.context).strip()
                source_input, old_result, history = case.data, case.result, list(case.history)
                remaining = self.config.followups_per_case - case.followups
            if data.context.strip():
                revised = self.pipeline.run(case.id, source_input, lambda _: None, context, old_result.revision + 1)
                with self.lock:
                    current = self._get(access, touch=False)
                    current.context, current.result = context, revised
                old_result = revised
            evidence = [e.model_dump(exclude_none=True) for e in old_result.evidence]
            if context:
                evidence.append(Evidence(id="user-context", source="context", quote=context,
                                         indicator="user_claim", explanation="Keterangan tambahan pengguna; belum diverifikasi secara independen.").model_dump())
            if not evidence:
                return Answer(answer="Bukti yang dapat dirujuk belum tersedia. Model belum bisa menjawab pertanyaan ini dengan dukungan sumber.", evidence_ids=[], remaining=remaining, limited=True)
            try:
                result = answer_grounded(self.pipeline.model, data.question, evidence, context, history)
                answer = Answer(answer="\n\n".join(c.text + " [" + ", ".join(c.evidence_ids) + "]" for c in result.claims),
                                evidence_ids=list(dict.fromkeys(eid for c in result.claims for eid in c.evidence_ids)), remaining=remaining)
            except (InvalidEvidence, ModelUnavailable) as exc:
                answer = Answer(answer=str(exc) + " Jawaban belum dapat disimpulkan dari bukti yang tersedia.", evidence_ids=[], remaining=remaining, limited=True)
            with self.lock:
                current = self._get(access, touch=False)
                current.history.extend([{"role": "user", "content": data.question}, {"role": "assistant", "content": answer.answer}])
            return answer
        finally:
            with self.lock:
                if access.case_id in self.cases:
                    self.cases[access.case_id].busy = False

    def delete(self, access: Access):
        with self.lock:
            case = self._get(access, touch=False)
            del self.cases[case.id]
            # Removed jobs cannot retain the uploaded data through closures.
            retained = deque()
            for cid, action, future in self.jobs:
                if cid == case.id:
                    future.set_exception(SinyaraError("expired", "Kasus telah dihapus.", 404))
                else:
                    retained.append((cid, action, future))
            self.jobs = retained

    def _work(self):
        while True:
            with self.lock:
                self._purge()
                if self.closed:
                    return
                if not self.jobs:
                    self.lock.wait(timeout=min(30, self.config.ttl_seconds))
                    continue
                cid, action, future = self.jobs.popleft()
                self.active = True
            try:
                if cid not in self.cases:
                    raise SinyaraError("expired", "Kasus kedaluwarsa sebelum diproses.", 404)
                future.set_result(action())
            except BaseException as exc:
                future.set_exception(exc)
            finally:
                with self.lock:
                    self.active = False
                # Do not retain the previous follow-up's question/context through this loop local.
                action = None
                future = None
