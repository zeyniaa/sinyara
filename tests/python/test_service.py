import threading
import time

import pytest
from fastapi.testclient import TestClient

from sinyara.api import create_app
from sinyara.errors import SinyaraError
from sinyara.schemas import Access, CaseInput, FollowupInput
from sinyara.store import CaseService

SESSION = "test-session-0000000001"


def wait_done(service, access):
    for _ in range(200):
        snapshot = service.snapshot(access)
        if snapshot["status"] in {"done", "error"}:
            return snapshot
        time.sleep(0.005)
    raise AssertionError("Worker did not complete")


def test_access_isolation_delete_and_token_not_in_url(service):
    with TestClient(create_app(service)) as client:
        a = client.post("/v1/cases", json={"message": "Jangan berikan OTP"}, headers={"X-Sinyara-Session": SESSION}).json()
        b = client.post("/v1/cases", json={"message": "Pesan lain"}, headers={"X-Sinyara-Session": SESSION}).json()
        assert client.get(f"/v1/cases/{a['case_id']}").status_code == 401
        assert client.get(f"/v1/cases/{a['case_id']}", headers={"Authorization": "Bearer " + b["token"]}).status_code == 404
        assert client.delete(f"/v1/cases/{a['case_id']}", headers={"Authorization": "Bearer " + a["token"]}).status_code == 200
        assert client.get(f"/v1/cases/{a['case_id']}", headers={"Authorization": "Bearer " + a["token"]}).status_code == 404


def test_expiry_poll_does_not_extend(config, model):
    clock = [0.]
    from sinyara.pipeline import Pipeline
    service = CaseService(config, Pipeline(config, model=model), now=lambda: clock[0])
    try:
        a = service.create(CaseInput(message="Pesan"), SESSION)
        clock[0] = 899
        service.snapshot(a)
        clock[0] = 901
        with pytest.raises(SinyaraError) as exc:
            service.snapshot(a)
        assert exc.value.code == "expired"
        assert not service.cases
    finally:
        service.close()


def test_quota_is_reserved_and_idempotent(service):
    for i in range(3):
        a = service.create(CaseInput(message="Jangan bagikan OTP"), SESSION)
        service.analyze(a)
        service.analyze(a)
        assert wait_done(service, a)["status"] == "done"
    a = service.create(CaseInput(message="Pesan keempat"), SESSION)
    with pytest.raises(SinyaraError) as exc:
        service.analyze(a)
    assert exc.value.code == "quota"


def test_followup_limit_and_reanalysis(service):
    a = service.create(CaseInput(message="Jangan bagikan OTP"), SESSION)
    service.analyze(a)
    wait_done(service, a)
    for i in range(5):
        answer = service.followup(a, FollowupInput(question="Kenapa?", context="Ini dari keluarga saya" if i == 0 else ""))
        assert answer.remaining == 4 - i
        assert answer.evidence_ids
    assert service.snapshot(a)["result"]["revision"] == 2
    with pytest.raises(SinyaraError) as exc:
        service.followup(a, FollowupInput(question="Lagi?"))
    assert exc.value.code == "followup_quota"


def test_single_worker_bounded_queue_delete_cannot_resurrect(config, model):
    from sinyara.pipeline import Pipeline
    entered, release = threading.Event(), threading.Event()
    pipeline = Pipeline(config, model=model)
    original = pipeline.run
    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(4)
        return original(*args, **kwargs)
    pipeline.run = blocked
    service = CaseService(config, pipeline)
    try:
        a = service.create(CaseInput(message="Awal"), SESSION)
        service.analyze(a)
        assert entered.wait(2)
        for i in range(10):
            pending = service.create(CaseInput(message="Antre"), f"another-session-{i:04d}")
            service.analyze(pending)
        overflow = service.create(CaseInput(message="Penuh"), "overflow-session-000")
        with pytest.raises(SinyaraError) as exc:
            service.analyze(overflow)
        assert exc.value.code == "queue_full"
        assert not service.usage.get("overflow-session-000")
        service.delete(a)
        release.set()
        time.sleep(.05)
        assert a.case_id not in service.cases
    finally:
        release.set()
        service.close()


def test_validation_never_echoes_secrets(service):
    with TestClient(create_app(service)) as client:
        response = client.post("/v1/cases", json={"message": "SECRET" * 501}, headers={"X-Sinyara-Session": SESSION})
        assert response.status_code == 422
        assert "SECRET" not in response.text
        assert response.headers["Cache-Control"] == "no-store"
