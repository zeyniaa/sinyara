import json

import pytest

from sinyara.gradio_api import dispatch
from sinyara.metrics import eer_threshold, validate_group_split, word_error_rate


def test_gradio_contract_matches_rest_without_file_upload(service):
    a = list(dispatch(service, "createCase", json.dumps({"session": "test-session-gradio", "input": {"message": "Jangan bagikan OTP."}})))[0]
    snapshots = list(dispatch(service, "analyzeCase", json.dumps({"access": a})))
    assert snapshots[-1]["status"] == "done"
    assert snapshots[-1]["result"]["mode"] == "real"
    assert "base64" not in json.dumps(snapshots)
    answer = list(dispatch(service, "askFollowup", json.dumps({"access": a, "question": "Kenapa?"})))[0]
    assert answer["evidence_ids"]
    assert list(dispatch(service, "deleteCase", json.dumps({"access": a}))) == [{"deleted": True}]


def test_gradio_validation_does_not_echo_secrets(service):
    reply = list(dispatch(service, "createCase", json.dumps({"input": {"message": "SECRET" * 1000}, "session": "test-session"})))
    assert "SECRET" not in json.dumps(reply)
    assert reply[0]["error"]["code"] == "invalid_input"


def test_wer_and_empirical_eer():
    assert word_error_rate("Halo Ibu", "halo ibu") == 0
    assert word_error_rate("Saya tidak meminta uang", "Saya meminta uang") == .25
    assert eer_threshold([True, True, False, False], [3, 4, 1, 2])["empirical_eer"] == 0
    with pytest.raises(ValueError):
        eer_threshold([True], [1])


def test_rejects_audio_leakage_between_splits():
    rows = [{"split": split, "label": label, "speaker_id": "same-speaker", "generator_id": label, "origin_id": split + label}
            for split in ["dev", "test"] for label in ["human", "synthetic"]]
    with pytest.raises(ValueError, match="speaker_id"):
        validate_group_split(rows)
