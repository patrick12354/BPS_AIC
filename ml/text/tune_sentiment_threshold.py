"""Fase 8 - penyetelan ambang kelas negatif (blueprint bagian 33).

**Masalah yang diselesaikan.** Kepala sentimen memakai `argmax` murni. Ketika model ragu
antara netral dan negatif, argmax selalu jatuh ke kelas yang probabilitasnya sedikit lebih
tinggi - dan karena netral adalah kelas terbanyak pada data latih, keraguan itu sistematis
berpihak ke netral. Akibatnya terukur pada evaluasi eksternal: **91 keluhan asli PRDECT
diprediksi netral.** Untuk produk yang seluruh gunanya adalah menemukan keluhan, kesalahan
ke arah ini jauh lebih merugikan daripada kebalikannya.

**Perbaikannya.** Satu ambang `tau`: prediksi `negatif` bila P(negatif) >= tau, meski netral
punya probabilitas lebih tinggi. `tau = 0.5` persis mengembalikan perilaku argmax lama pada
kasus dua kelas, sehingga perubahan ini dapat dibatalkan dengan satu angka.

**Kenapa disetel pada split tuning, bukan test.** Memilih tau pada data yang sama dengan yang
dilaporkan akan menghasilkan angka yang tampak membaik tanpa ada perbaikan nyata. Tau dipilih
pada NusaX split *train*, lalu dilaporkan pada NusaX *test* dan PRDECT *test* yang tidak
pernah dilihat saat memilih.

Jalankan:
    python ml/text/tune_sentiment_threshold.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import io
from urllib.request import urlopen

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ml" / "text"))

from aggregate import by_asymmetric, by_majority  # noqa: E402
from preprocess import normalize, split_clauses  # noqa: E402

CHECKPOINT = REPO / "models" / "indobert-nlp01" / "model.pt"
RAW = REPO / "data" / "raw"
OUT = REPO / "ml" / "evaluation" / "threshold_tuning.json"
SENTIMENTS = ["negatif", "netral", "positif"]
NEG = SENTIMENTS.index("negatif")

# Rentang sapuan. Di bawah 0,20 hampir semua klausa jadi negatif; di atas 0,55 ambangnya
# tidak lagi mengubah apa pun dibanding argmax.
TAU_GRID = np.round(np.arange(0.20, 0.56, 0.025), 3)


# Parquet ditarik langsung lewat URL, sama seperti evaluate_external.py - tanpa paket
# `datasets` yang menarik dependensi besar hanya untuk membaca satu berkas.
NUSAX_BASE = (
    "https://huggingface.co/datasets/indonlp/NusaX-senti/resolve/"
    "refs%2Fconvert%2Fparquet/{lang}/{split}/0000.parquet"
)


def load_nusax(split: str, lang: str = "ind") -> pd.DataFrame:
    cache = RAW / "nusax_senti" / f"{lang}_{split}.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        with urlopen(NUSAX_BASE.format(lang=lang, split=split), timeout=180) as resp:
            cache.write_bytes(resp.read())
    df = pd.read_parquet(io.BytesIO(cache.read_bytes()))
    df["gold"] = df["label"].map({0: "negatif", 1: "netral", 2: "positif"})
    return df[["text", "gold"]].dropna()


def load_prdect() -> pd.DataFrame:
    """Split test PRDECT - dipilih PER PRODUK, sama persis dengan evaluate_external.py.

    Memakai potongan indeks sederhana akan menaruh ulasan produk yang sama di kedua sisi,
    dan angka yang dihasilkan tidak lagi sebanding dengan evaluasi yang sudah dilaporkan.
    """
    src = pd.read_csv(RAW / "prdect_id" / "PRDECT-ID Dataset.csv")
    src["text"] = src["Customer Review"].astype(str)
    src["gold"] = src["Sentiment"].str.lower().map({"positive": "positif", "negative": "negatif"})
    src["product_key"] = "prdect::" + src["Product Name"].astype(str)

    test_products = set(pd.read_csv(REPO / "data" / "processed" / "clauses_test_silver.csv")["product_key"])
    held_out = src[src["product_key"].isin(test_products)]
    return held_out[["text", "gold"]].dropna().reset_index(drop=True)


def clause_probs(texts: list[str]) -> list[np.ndarray]:
    """Probabilitas sentimen per klausa untuk tiap dokumen - dihitung SEKALI.

    Sapuan ambang tidak boleh memuat ulang model setiap langkah: itu mengubah pekerjaan
    beberapa menit menjadi beberapa jam tanpa menambah informasi apa pun.
    """
    import torch
    from transformers import AutoTokenizer

    from model import DualHeadClassifier

    bundle = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = DualHeadClassifier(bundle["base_model"])
    model.load_state_dict(bundle["state_dict"])
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    tok = AutoTokenizer.from_pretrained(str(CHECKPOINT.parent))

    out: list[np.ndarray] = []
    with torch.no_grad():
        for i, text in enumerate(texts):
            clauses = split_clauses(normalize(text)) or [normalize(text)]
            enc = tok(clauses, truncation=True, max_length=32, padding=True,
                      return_tensors="pt").to(device)
            _, logits = model(enc["input_ids"], enc["attention_mask"])
            out.append(torch.softmax(logits, dim=-1).cpu().numpy())
            if (i + 1) % 200 == 0:
                print(f"    {i + 1}/{len(texts)}", flush=True)
    return out


def decide(probs: np.ndarray, tau: float, rule: str = "mayoritas_klausa") -> str:
    """Agregasi dokumen dari klausa, dengan ambang khusus kelas negatif.

    Aturan agregasinya diambil dari `aggregate.py`, sumber yang sama dengan
    `evaluate_external.py` dan dengan backend - sebelumnya ditulis ulang di sini dan diam-diam
    menyimpang. `rule` dibiarkan default ke aturan lama supaya pencarian ambang ini tetap
    membandingkan hal yang sama dengan yang dulu dicarinya; pertukaran antar-aturan diukur di
    `evaluate_external.py`, bukan di sini.
    """
    votes = []
    for row in probs:
        votes.append("negatif" if row[NEG] >= tau else SENTIMENTS[int(row.argmax())])
    if rule == "asimetris_negatif":
        return by_asymmetric(votes, [float(row[NEG]) for row in probs], threshold=tau)
    return by_majority(votes)


def macro_f1(gold: list[str], pred: list[str], classes: list[str]) -> tuple[float, dict]:
    per = {}
    for c in classes:
        tp = sum(g == c and p == c for g, p in zip(gold, pred))
        fp = sum(g != c and p == c for g, p in zip(gold, pred))
        fn = sum(g == c and p != c for g, p in zip(gold, pred))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        per[c] = {
            "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
        }
    return round(sum(v["f1"] for v in per.values()) / len(classes), 4), per


def main() -> int:
    if not CHECKPOINT.exists():
        print(f"Checkpoint tidak ada: {CHECKPOINT}", file=sys.stderr)
        return 1

    print("Memuat data…", flush=True)
    tune = load_nusax("train")
    tests = {"nusax_ind_test": load_nusax("test"), "prdect_test": load_prdect()}

    print(f"Menghitung probabilitas - tuning ({len(tune)} dokumen)…", flush=True)
    tune_probs = clause_probs(tune["text"].tolist())

    print("Menyapu ambang…", flush=True)
    sweep = []
    for tau in TAU_GRID:
        pred = [decide(p, tau) for p in tune_probs]
        f1, per = macro_f1(tune["gold"].tolist(), pred, SENTIMENTS)
        sweep.append({"tau": float(tau), "macro_f1": f1, "negatif": per["negatif"]})
        print(f"  tau={tau:.3f}  macroF1={f1:.4f}  negatif R={per['negatif']['recall']:.3f}", flush=True)

    best = max(sweep, key=lambda r: r["macro_f1"])
    tau = best["tau"]
    print(f"\nTerpilih tau={tau} (macro F1 tuning {best['macro_f1']})", flush=True)

    results = {}
    for name, df in tests.items():
        print(f"Mengevaluasi {name} ({len(df)} dokumen)…", flush=True)
        probs = clause_probs(df["text"].tolist())
        classes = sorted(set(df["gold"]))
        gold = df["gold"].tolist()
        f1_old, per_old = macro_f1(gold, [decide(p, 0.5) for p in probs], classes)
        f1_new, per_new = macro_f1(gold, [decide(p, tau) for p in probs], classes)
        results[name] = {
            "n": len(df),
            "kelas": classes,
            "argmax_lama": {"macro_f1": f1_old, "per_kelas": per_old},
            f"tau_{tau}": {"macro_f1": f1_new, "per_kelas": per_new},
        }
        print(f"  macro F1 {f1_old} -> {f1_new}", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "catatan": (
            "tau dipilih pada NusaX split TRAIN dan dilaporkan pada split test yang tidak "
            "pernah dilihat saat memilih. tau=0.5 setara perilaku argmax lama."
        ),
        "tau_terpilih": tau,
        "sapuan_pada_tuning": sweep,
        "hasil_pada_test": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDitulis ke {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
