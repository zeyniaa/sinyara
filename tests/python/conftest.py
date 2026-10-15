import pytest

from sinyara.config import Settings
from sinyara.pipeline import Pipeline
from sinyara.schemas import Assessment, Finding, GroundedAnswer, Claim, SupportCheck
from sinyara.store import CaseService


class StubModel:
    version = "test-double/not-a-real-model"

    def generate(self, task, data, schema, repair=""):
        if schema is SupportCheck:
            return SupportCheck(supported=True, reason="Klaim sesuai bukti uji.")
        if issubclass(schema, GroundedAnswer):
            return GroundedAnswer(claims=[Claim(text="Ada sumber yang perlu diperiksa.", evidence_ids=[data["evidence"][0]["id"]])])
        sid, text = next(iter(data["sources"].items()))
        return Assessment(risk="low", findings=[Finding(source_id=sid, quote=text,
                          indicator="protective_context", explanation="Konteks peringatan.")])


@pytest.fixture
def config():
    return Settings(_env_file=None)


@pytest.fixture
def model():
    return StubModel()


@pytest.fixture
def service(config, model):
    service = CaseService(config, Pipeline(config, model=model))
    yield service
    service.close()
