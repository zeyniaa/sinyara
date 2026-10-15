"""JSON transport adapter, deliberately no Gradio file or audio components."""
import json
import time

from pydantic import ValidationError

from .errors import SinyaraError
from .schemas import Access, CaseInput, FollowupInput
from .store import CaseService


def dispatch(service: CaseService, operation: str, payload: str):
    try:
        if len(payload.encode("utf-8")) > 14_100_000:
            raise SinyaraError("too_large", "Unggahan terlalu besar.", 413)
        data = json.loads(payload)
        if operation == "createCase":
            yield service.create(CaseInput.model_validate(data["input"]), data["session"]).model_dump()
            return
        access = Access.model_validate(data["access"])
        if operation == "analyzeCase":
            service.analyze(access)
            while True:
                snapshot = service.snapshot(access)
                yield snapshot
                if snapshot["status"] in {"done", "error"}:
                    return
                time.sleep(.5)
        elif operation == "getCase":
            yield service.snapshot(access)
        elif operation == "askFollowup":
            yield service.followup(access, FollowupInput(question=data["question"], context=data.get("context", ""))).model_dump()
        elif operation == "deleteCase":
            service.delete(access)
            yield {"deleted": True}
        else:
            raise SinyaraError("invalid_operation", "Operasi tidak dikenali.")
    except SinyaraError as exc:
        yield {"error": {"code": exc.code, "message": exc.message}}
    except (ValidationError, KeyError, ValueError, TypeError):
        yield {"error": {"code": "invalid_input", "message": "Input tidak valid. Periksa batas dan format data."}}


def build_app(service: CaseService):
    import gradio as gr

    def api(operation, payload):
        for output in dispatch(service, operation, payload):
            yield json.dumps(output, ensure_ascii=False)

    with gr.Blocks(analytics_enabled=False, delete_cache=(60, 60)) as demo:
        gr.Markdown("# Sinyara API\nAntarmuka pengguna tersedia di frontend HTML. Rekaman tidak memiliki URL unduhan publik.")
        operation = gr.Textbox(label="operation")
        payload = gr.Textbox(label="payload", type="password")
        output = gr.Textbox(label="response", type="password")
        button = gr.Button("API")
        button.click(api, inputs=[operation, payload], outputs=output, api_name="dispatch", concurrency_limit=12)
    # Bounded queue; service has its own FIFO 10-job cap and one heavy worker.
    return demo.queue(max_size=10, default_concurrency_limit=12)
