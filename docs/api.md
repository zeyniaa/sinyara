# Kontrak API

Jalankan satu instance `uvicorn sinyara.api:app --port 8010 --no-access-log`. Jangan menambahkan `--workers` lebih dari satu selama penyimpanan kasus masih di memori. Skema lengkap di `/docs`.

```python
import secrets
import time
import httpx

base = "http://127.0.0.1:8010"
session = secrets.token_urlsafe(24)

with httpx.Client(timeout=600) as client:
    response = client.post(f"{base}/v1/cases", headers={"X-Sinyara-Session": session},
                           json={"message": "Jangan pernah membagikan OTP.", "urls": []})
    response.raise_for_status()
    access = response.json()
    headers = {"Authorization": f"Bearer {access['token']}"}
    path = f"{base}/v1/cases/{access['case_id']}"
    client.post(f"{path}/analyze", headers=headers).raise_for_status()

    while True:
        response = client.get(path, headers=headers)
        response.raise_for_status()
        snapshot = response.json()
        if snapshot["status"] in {"done", "error"}:
            break
        time.sleep(1)

    if snapshot["status"] == "done":
        # Avoid printing personal evidence in operational logs.
        print(snapshot["result"]["risk"])
        answer = client.post(f"{path}/followups", headers=headers,
                             json={"question": "Kenapa pesan ini dinilai begitu?", "context": ""})
        answer.raise_for_status()

    client.delete(path, headers=headers).raise_for_status()
```

`CaseInput`:

```json
{
  "message": "Pesan yang ingin diperiksa",
  "urls": ["https://example.com/path"],
  "audio": { "name": "rekaman.wav", "base64": "<base64 byte audio asli>" }
}
```

`audio` opsional. Satu kasus memerlukan setidaknya satu jenis bukti. Jangan menambahkan awalan `data:audio/...;base64,` pada base64. Isi harus dapat didecode, maksimal 10 MB dan 60 detik. Validasi decoder dilakukan pada tahap pemrosesan.

Snapshot berisi `status`, `progress`, `result`, `error`. Progres:

```json
{
  "stage": "language",
  "detail": "Memeriksa konteks dan permintaan.",
  "completed": 1,
  "total": 3,
  "queue_position": null
}
```

Hasil memiliki `case_id`, `mode`, `risk`, `summary`, `evidence`, `checks`, `limitations`, `next_steps`, `models`, `created_at`, dan `revision`. Temuan audio menyertakan `start`/`end` dalam detik; temuan teks/URL tidak memiliki rentang audio.

| Error | Makna |
| --- | --- |
| `invalid_input`, `invalid_audio`, `audio_too_long` | Perbaiki input atau format |
| `unauthorized` | Header token tidak diberikan |
| `expired` (404) | Token salah, kasus tidak ada, dihapus, atau kedaluwarsa; detailnya tidak dibedakan |
| `quota`, `followup_quota` | Batas demo sudah tercapai |
| `queue_full`, `capacity` | Antrean atau kapasitas sementara penuh |
| `busy`, `not_ready` | Tunggu operasi yang sedang berlangsung |
| `model_error`, `timeout` | Pemrosesan gagal atau melebihi batas tunggu |

Model tidak tersedia pada satu pemeriksaan dapat muncul sebagai `checks[].status=unavailable` dalam hasil parsial, bukan selalu error HTTP seluruh kasus. Jangan menampilkan hasil tersebut seolah semua input telah diperiksa.

Gradio menggunakan `POST /dispatch` melalui SDK resmi, dua parameter `operation` dan `payload` (JSON string). Nama operasi mengikuti `CaseClient` TypeScript. Respons JSON memiliki bentuk identik; error diletakkan pada `error.code`/`error.message` karena transport Gradio memakai status HTTP sendiri. Lihat `tests/python/test_metrics_and_gradio.py` untuk kesetaraan kontrak.
