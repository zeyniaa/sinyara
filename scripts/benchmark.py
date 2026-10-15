"""Small synthetic regression benchmark. This is not an estimate of real-world accuracy."""
import argparse
import json
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from sinyara.config import Settings
from sinyara.pipeline import Pipeline
from sinyara.schemas import CaseInput

parser = argparse.ArgumentParser()
parser.add_argument("--input", default="eval/messages.jsonl")
parser.add_argument("--output", default="artifacts/benchmark-local.json")
parser.add_argument("--mlflow", action="store_true", help="Store only synthetic fixture metrics in a local MLflow run")
parser.add_argument("--limit", type=int, default=0)
args = parser.parse_args()
config = Settings()
pipeline = Pipeline(config)
examples = [json.loads(line) for line in Path(args.input).read_text(encoding="utf-8").splitlines() if line.strip()]
if args.limit:
    examples = examples[:args.limit]
records = []
try:
    import psutil
    process = psutil.Process()
except ImportError:
    process = None
for item in examples:
    started = time.perf_counter()
    result = pipeline.run(item["id"], CaseInput(message=item["message"], urls=item.get("urls", [])), lambda _: None)
    record = {"id": item["id"], "category": item["category"], "expected": item["expected"],
              "predicted": result.risk.value, "latency_seconds": round(time.perf_counter() - started, 3),
              "content_completed": any(c.key == "content" and c.status == "done" for c in result.checks),
              "evidence_count": len(result.evidence), "checks": [c.model_dump() for c in result.checks],
              "memory_rss_bytes": process.memory_info().rss if process else None}
    records.append(record)
    print(json.dumps({"id": item["id"], "predicted": record["predicted"], "latency": record["latency_seconds"]}), flush=True)
positive = {"high", "verify"}
tp = sum(r["predicted"] in positive and r["expected"] in positive for r in records)
fp = sum(r["predicted"] in positive and r["expected"] == "low" for r in records)
fn = sum(r["predicted"] not in positive and r["expected"] in positive for r in records)
negatives = sum(r["expected"] == "low" for r in records)
metrics = {"precision": tp / (tp + fp) if tp + fp else None,
           "recall": tp / (tp + fn) if tp + fn else None,
           "false_positive_rate": fp / negatives if negatives else None,
           "exact_risk_matches": sum(r["predicted"] == r["expected"] for r in records),
           "completed_content_rate": sum(r["content_completed"] for r in records) / len(records),
           "latency_median_seconds": statistics.median(r["latency_seconds"] for r in records)}
report = {"created_at": datetime.now(timezone.utc).isoformat(), "model": pipeline.model.version,
          "dataset": args.input, "synthetic_only": True, "sample_count": len(records),
          "python": platform.python_version(), "platform": platform.platform(), "metrics": metrics,
          "limitations": ["Tiny synthetic set; no population accuracy claim.", "Process RSS excludes Ollama's separate model process and GPU memory.", "Quote membership is validated; semantic evidence support requires human adjudication.", "WER and forensic EER not measured in this message-only benchmark."],
          "records": records}
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
if args.mlflow:
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
    os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
    import mlflow
    # Never send input data to a remote tracking URI implicitly.
    mlflow.set_tracking_uri((Path.cwd() / "mlruns").as_uri())
    mlflow.set_experiment("sinyara-synthetic-regression")
    with mlflow.start_run():
        mlflow.log_param("model", pipeline.model.version)
        mlflow.log_param("synthetic_only", True)
        mlflow.log_metrics({key: val for key, val in metrics.items() if val is not None})
print(json.dumps({"output": args.output, "metrics": metrics}))
