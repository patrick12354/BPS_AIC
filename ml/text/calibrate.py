"""Fit suhu kalibrasi pada split validasi dan tulis ke bundle checkpoint (L1).

    python ml/text/calibrate.py

Prasyarat: `models/indobert-nlp01/model.pt` dan `data/processed/clauses_val.csv`. Keduanya
dihasilkan pipeline yang sudah ada (`download_checkpoint.py`, `build_dataset.py`); skrip ini
tidak melatih apa pun dan tidak menyentuh bobot model.

Yang dilakukannya:

  1. Menghitung logit kedua head pada split validasi - split yang SAMA dengan yang dipakai
     memilih epoch terbaik, dan itu memang tempatnya. Kalibrasi pada data latih akan mengukur
     hafalan; kalibrasi pada data uji membakar satu-satunya set yang masih bersih.
  2. Mencari satu suhu per head yang meminimalkan NLL.
  3. Melaporkan ECE sebelum dan sesudah, lalu menuliskan suhunya kembali ke bundle sebagai
     `sentiment_temperature` dan `aspect_temperature`.

Sesudah itu backend memuatnya sendiri dan mulai mengeluarkan keyakinan sungguhan; sebelum itu
ia tetap memakai penanda tetap dan tetap menyembunyikannya dari layar. Perpindahannya otomatis
dan bergantung pada isi bundle, bukan pada saklar yang bisa lupa dinyalakan.

Head aspek dikalibrasi terpisah karena ia multi-label (sigmoid per aspek), bukan multi-kelas.
Satu suhu tetap berlaku - ia menggeser seluruh sigmoid ke arah yang sama - tetapi NLL-nya
dihitung sebagai binary cross-entropy, dan ambang aspeknya IKUT digeser supaya keputusan
"aspek ini disebut atau tidak" tetap persis sama seperti sebelum kalibrasi.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from calibration import calibration_report, fit_temperature  # noqa: E402
from lexicon import ALL_ASPECTS  # noqa: E402

PROCESSED = REPO_ROOT / "data" / "processed"
CHECKPOINT = REPO_ROOT / "models" / "indobert-nlp01" / "model.pt"
EVAL_OUT = REPO_ROOT / "ml" / "evaluation"
SENTIMENTS = ["negatif", "netral", "positif"]
BATCH = 128
MAX_LEN = 32


def _bce_nll(logits: list[list[float]], targets: list[list[int]], temperature: float) -> float:
    """NLL untuk head multi-label: rata-rata binary cross-entropy atas seluruh (baris, aspek).

    Ditulis di sini, bukan di `calibration.py`, karena bentuk objektifnya berbeda dari kasus
    multi-kelas dan mencampur keduanya di satu fungsi akan menyembunyikan perbedaan yang justru
    penting: yang satu memilih satu dari tiga, yang lain memutuskan sebelas hal sekaligus.
    """
    total, n = 0.0, 0
    for row, tgt in zip(logits, targets):
        for x, y in zip(row, tgt):
            p = 1.0 / (1.0 + math.exp(-max(min(x / temperature, 30.0), -30.0)))
            total -= math.log(max(p if y else 1.0 - p, 1e-12))
            n += 1
    return total / n if n else 0.0


def _fit_aspect_temperature(logits, targets, lo=0.05, hi=10.0, iterations=60) -> float:
    for _ in range(iterations):
        a = lo + (hi - lo) / 3.0
        b = hi - (hi - lo) / 3.0
        if _bce_nll(logits, targets, a) < _bce_nll(logits, targets, b):
            hi = b
        else:
            lo = a
    return round((lo + hi) / 2.0, 4)


def collect_logits(model, tokenizer, texts, device, torch):
    """Logit kedua head untuk seluruh klausa validasi."""
    aspect_out, sentiment_out = [], []
    with torch.no_grad():
        for start in range(0, len(texts), BATCH):
            enc = tokenizer(
                texts[start : start + BATCH], truncation=True, max_length=MAX_LEN,
                padding=True, return_tensors="pt",
            ).to(device)
            a, s = model(enc["input_ids"], enc["attention_mask"])
            aspect_out.extend([[float(v) for v in row] for row in a.cpu().numpy()])
            sentiment_out.extend([[float(v) for v in row] for row in s.cpu().numpy()])
    return aspect_out, sentiment_out


def main() -> int:
    val_path = PROCESSED / "clauses_val.csv"
    if not CHECKPOINT.exists():
        print(f"checkpoint tidak ditemukan: {CHECKPOINT}", file=sys.stderr)
        print("jalankan scripts/download_checkpoint.py lebih dulu", file=sys.stderr)
        return 1
    if not val_path.exists():
        print(f"split validasi tidak ditemukan: {val_path}", file=sys.stderr)
        print("jalankan ml/text/build_dataset.py lebih dulu", file=sys.stderr)
        return 1

    import pandas as pd
    import torch
    from transformers import AutoTokenizer

    from model import DualHeadClassifier

    val = pd.read_csv(val_path)
    val["clause_text"] = val["clause_text"].fillna("").astype(str)
    texts = val["clause_text"].tolist()
    y_sentiment = val["sentiment"].map({s: i for i, s in enumerate(SENTIMENTS)}).tolist()
    y_aspect = val[list(ALL_ASPECTS)].values.astype(int).tolist()

    bundle = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = DualHeadClassifier(bundle["base_model"])
    model.load_state_dict(bundle["state_dict"])
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    tokenizer = AutoTokenizer.from_pretrained(str(CHECKPOINT.parent))

    print(f"menghitung logit pada {len(texts)} klausa validasi (device: {device})…", flush=True)
    aspect_logits, sentiment_logits = collect_logits(model, tokenizer, texts, device, torch)

    t_sentiment = fit_temperature(sentiment_logits, y_sentiment)
    laporan_sentimen = calibration_report(sentiment_logits, y_sentiment, t_sentiment)

    t_aspect = _fit_aspect_temperature(aspect_logits, y_aspect)
    ambang_lama = float(bundle.get("aspect_threshold", 0.5))
    # Ambang aspek ikut digeser supaya keputusan biner "aspek ini disebut atau tidak" tetap
    # identik. Tanpa ini, kalibrasi yang seharusnya hanya menyentuh angka keyakinan akan
    # diam-diam mengubah aspek mana yang terdeteksi - dan seluruh evaluasi aspek yang sudah
    # dilaporkan berhenti berlaku.
    logit_ambang = math.log(ambang_lama / (1.0 - ambang_lama))
    ambang_baru = 1.0 / (1.0 + math.exp(-logit_ambang / t_aspect))

    laporan = {
        "catatan": (
            "Temperature scaling (Guo et al., 2017), di-fit pada split validasi dengan NLL. "
            "Membagi logit dengan skalar positif tidak menggeser argmax, sehingga akurasi, "
            "F1, dan urutan Action Card tidak berubah - yang berubah hanya kejujuran angka "
            "keyakinannya."
        ),
        "sentimen": laporan_sentimen,
        "aspek": {
            "temperature": t_aspect,
            "ambang_sebelum": round(ambang_lama, 4),
            "ambang_sesudah": round(ambang_baru, 4),
            "nll_sebelum": round(_bce_nll(aspect_logits, y_aspect, 1.0), 4),
            "nll_sesudah": round(_bce_nll(aspect_logits, y_aspect, t_aspect), 4),
            "catatan": (
                "Ambang digeser bersama suhunya supaya keputusan aspek tetap identik dengan "
                "sebelum kalibrasi."
            ),
        },
    }

    print(json.dumps(laporan, indent=2, ensure_ascii=False))
    if not laporan_sentimen["keputusan_tidak_berubah"]:
        print(
            "\nBERHENTI: kalibrasi mengubah keputusan model. Itu tidak mungkin secara "
            "matematis untuk suhu positif, jadi yang terjadi adalah bug - suhu TIDAK ditulis "
            "ke bundle.",
            file=sys.stderr,
        )
        return 2

    bundle["sentiment_temperature"] = t_sentiment
    bundle["aspect_temperature"] = t_aspect
    bundle["aspect_threshold_calibrated"] = round(ambang_baru, 6)
    bundle["calibration"] = laporan
    torch.save(bundle, CHECKPOINT)

    EVAL_OUT.mkdir(parents=True, exist_ok=True)
    (EVAL_OUT / "calibration.json").write_text(
        json.dumps(laporan, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nsuhu ditulis ke {CHECKPOINT.relative_to(REPO_ROOT)}")
    print(f"laporan: {(EVAL_OUT / 'calibration.json').relative_to(REPO_ROOT)}")
    print(
        f"\nECE sentimen {laporan_sentimen['ece_sebelum']} -> "
        f"{laporan_sentimen['ece_sesudah']} (T={t_sentiment})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
