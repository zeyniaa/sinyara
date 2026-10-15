"""Copy this template plus backend/ to an eligible Gradio ZeroGPU Space."""
import os
import sys

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
sys.path.insert(0, "backend")

import spaces

from sinyara.config import Settings
from sinyara.gradio_api import build_app
from sinyara.llm import TransformersModel
from sinyara.pipeline import Pipeline
from sinyara.store import CaseService

# Preload on startup, as required by ZeroGPU's CUDA emulation. This can take time.
llm = TransformersModel()
original_generate = llm.generate

@spaces.GPU(duration=90)
def generate(task, data, schema, repair=""):
    return original_generate(task, data, schema, repair)

llm.generate = generate
config = Settings(llm_provider="transformers", llm_model="Qwen/Qwen3.5-4B")
service = CaseService(config, Pipeline(config, model=llm))
demo = build_app(service)
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", show_error=False, max_file_size="10mb", strict_cors=True, run_history=False)
