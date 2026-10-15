import base64
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Risk(StrEnum):
    HIGH = "high"
    VERIFY = "verify"
    LOW = "low"
    INSUFFICIENT = "insufficient"


class AudioInput(StrictModel):
    name: str = Field(max_length=150)
    base64: str = Field(max_length=13_981_016)

    def decode(self) -> bytes:
        try:
            data = base64.b64decode(self.base64, validate=True)
        except ValueError as exc:
            raise ValueError("Rekaman tidak memiliki encoding yang valid.") from exc
        if not data or len(data) > 10 * 1024 * 1024:
            raise ValueError("Ukuran rekaman harus antara 1 byte dan 10 MB.")
        return data


class CaseInput(StrictModel):
    message: str = Field(default="", max_length=3000)
    urls: list[str] = Field(default_factory=list, max_length=3)
    audio: AudioInput | None = None

    @model_validator(mode="after")
    def check_contents(self):
        self.message = self.message.strip()
        self.urls = list(dict.fromkeys(u.strip() for u in self.urls if u.strip()))
        if not self.message and not self.urls and not self.audio:
            raise ValueError("Tambahkan pesan, tautan, atau rekaman terlebih dahulu.")
        for url in self.urls:
            if len(url) > 2048:
                raise ValueError("Tautan maksimal 2.048 karakter.")
        if self.audio:
            self.audio.decode()
        return self


class Evidence(StrictModel):
    id: str
    source: Literal["message", "url", "audio", "context"]
    quote: str
    explanation: str
    indicator: str
    start: float | None = None
    end: float | None = None


class Check(StrictModel):
    key: str
    title: str
    status: Literal["done", "limited", "unavailable", "inconclusive", "skipped"]
    detail: str


class Result(StrictModel):
    case_id: str
    mode: Literal["real", "simulation"] = "real"
    risk: Risk
    summary: str
    evidence: list[Evidence]
    checks: list[Check]
    limitations: list[str]
    next_steps: list[str]
    models: dict[str, str]
    created_at: str
    revision: int = 1


class Progress(StrictModel):
    stage: str = "created"
    detail: str = "Kasus siap diperiksa."
    completed: int = 0
    total: int = 0
    queue_position: int | None = None


class Access(StrictModel):
    case_id: str
    token: str


class FollowupInput(StrictModel):
    question: str = Field(min_length=1, max_length=1000)
    context: str = Field(default="", max_length=2000)


class Answer(StrictModel):
    answer: str
    evidence_ids: list[str]
    remaining: int
    limited: bool = False


class Finding(StrictModel):
    source_id: str = Field(description="ID sumber, misalnya message atau audio-1. Bukan isi teks sumber.")
    quote: str = Field(min_length=1, max_length=600)
    indicator: Literal["secret_request", "payment_request", "urgency", "impersonation", "secrecy", "other", "protective_context"] = Field(description="secret_request=meminta OTP/PIN/password; payment_request=meminta uang; urgency=tekanan waktu; impersonation=klaim identitas; secrecy=merahasiakan; protective_context=HANYA edukasi atau larangan membagikan data, BUKAN pesan yang meminta rahasia.")
    explanation: str = Field(min_length=1, max_length=400)


class Assessment(StrictModel):
    risk: Risk
    findings: list[Finding] = Field(max_length=12)


class GroundedAnswer(StrictModel):
    # Each factual sentence must carry its own references; recommendations are rendered separately.
    claims: list["Claim"] = Field(min_length=1, max_length=5)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=700)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class SupportCheck(StrictModel):
    supported: bool
    reason: str = Field(min_length=1, max_length=400)
