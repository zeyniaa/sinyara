"""Transport preview only. Real local LLM/ASR configuration comes from .env."""
from sinyara.config import settings
from sinyara.gradio_api import build_app
from sinyara.store import CaseService

demo = build_app(CaseService(settings))
demo.launch(server_name="127.0.0.1", server_port=7861, show_error=False, strict_cors=True, run_history=False)
