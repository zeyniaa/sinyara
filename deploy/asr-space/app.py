"""Isolated Qwen-ASR dependency environment. No file components or public audio URL."""
import base64
import io
import json
import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import av
import gradio as gr
import numpy as np
import spaces
import torch
from qwen_asr import Qwen3ASRModel

model = Qwen3ASRModel.from_pretrained("Qwen/Qwen3-ASR-0.6B", dtype=torch.bfloat16,
                                      device_map="cuda:0", max_inference_batch_size=1,
                                      max_new_tokens=256)

@spaces.GPU(duration=60)
def transcribe(payload):
    try:
        if not isinstance(payload, str) or len(payload) > 2_600_000:
            raise ValueError()
        data = base64.b64decode(payload, validate=True)
        if len(data) > 1_930_000:
            raise ValueError()
        with av.open(io.BytesIO(data)) as container:
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(format="fltp", layout="mono", rate=16000)
            chunks, count = [], 0
            for frame in container.decode(stream):
                for part in resampler.resample(frame):
                    count += part.samples
                    if count > 960_800:
                        raise ValueError()
                    chunks.append(part.to_ndarray().reshape(-1).copy())
            for part in resampler.resample(None):
                count += part.samples
                if count > 960_800:
                    raise ValueError()
                chunks.append(part.to_ndarray().reshape(-1).copy())
        audio = np.concatenate(chunks).astype(np.float32)
        segments = []
        for start in range(0, len(audio), 240000):
            part = audio[start:start + 240000]
            if float(np.sqrt(np.mean(part ** 2))) < .0001:
                continue
            text = model.transcribe(audio=(part.copy(), 16000), language="Indonesian")[0].text.strip()
            if text:
                segments.append({"text": text, "start": start / 16000, "end": (start + len(part)) / 16000})
        return json.dumps({"segments": segments, "timestamp_type": "chunk-boundary-not-word-alignment"})
    except Exception:
        return json.dumps({"error": "Transkripsi gagal atau rekaman tidak valid."})

with gr.Blocks(analytics_enabled=False, delete_cache=(60, 60)) as demo:
    gr.Markdown("# Sinyara ASR\nWorker JSON. Tidak menyimpan rekaman sebagai file unduhan.")
    payload = gr.Textbox(type="password", label="payload")
    response = gr.Textbox(type="password", label="response")
    gr.Button("Transcribe").click(transcribe, inputs=payload, outputs=response, api_name="transcribe", concurrency_limit=1)

if __name__ == "__main__":
    demo.queue(max_size=10).launch(show_error=False, max_file_size="10mb", strict_cors=True, run_history=False)
