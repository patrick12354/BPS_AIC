"""Evaluasi aspek pada LABEL MANUSIA INDEPENDEN - penengah terakhir untuk klaim aspek NLP-01.

Masukan: dua berkas pelabel yang sudah diisi TERPISAH
    data/annotation/aspect_human_A_done.csv
    data/annotation/aspect_human_B_done.csv
(dibuat oleh scripts/build_aspect_human_pack.py, diisi lewat label_aspek.html)

Yang dilakukan, berurutan:

1. **Kesepakatan antar-pelabel** - Cohen's kappa per aspek dan gabungan. Ini dilaporkan LEBIH
   DULU karena menentukan seberapa jauh angka apa pun di bawahnya boleh dipercaya: kalau dua
   manusia sendiri hanya sepakat kappa 0,3 pada suatu aspek, F1 model pada aspek itu tidak
   dapat ditafsirkan, dan skrip ini menandainya demikian alih-alih melaporkannya rata.
2. **Label rujukan** - baris yang disepakati kedua pelabel dipakai apa adanya. Baris yang
   berbeda ditulis ke `aspect_human_adjudication.csv` untuk diputuskan orang KETIGA; bila berkas
   `aspect_human_adjudicated.csv` sudah ada, keputusannya ikut dipakai. Tanpa itu, evaluasi
   berjalan pada subset yang disepakati saja - dan jumlahnya dilaporkan.
3. **Empat pendekatan dibandingkan pada rujukan yang sama**: leksikon rule-based, TF-IDF+LR,
   IndoBERT fine-tuned, dan label gold-LLM (ADR-017) untuk klausa yang berasal dari gold.
   Baris terakhir itu yang menjawab pertanyaan inti: apakah gold lama yang bias, atau modelnya
   yang memang tidak unggul.

Hasil ditulis ke ml/evaluation/aspect_human_results.json dan dicetak sebagai tabel siap tempel ke
MODEL_CARD - apa pun arah angkanya.

Jalankan:
    python ml/text/evaluate_aspect_human.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lexicon import ALL_ASPECTS  # noqa: E402

ANNOT = REPO_ROOT / "data" / "annotation"
EVAL_OUT = REPO_ROOT / "ml" / "evaluation"
A_PATH = ANNOT / "aspect_human_A_done.csv"
B_PATH = ANNOT / "aspect_human_B_done.csv"
ADJ_TASK = ANNOT / "aspect_human_adjudication.csv"
ADJ_DONE = ANNOT / "aspect_human_adjudicated.csv"
GOLD = ANNOT / "gold_labels.csv"
MANIFEST = ANNOT / "aspect_human_manifest.json"

ASPECT_COLS = [f"asp_{a}" for a in ALL_ASPECTS]

# Ambang kappa di bawah mana F1 pada aspek itu ditandai "tidak dapat ditafsirkan". 0,4 adalah
# batas bawah "kesepakatan sedang" menurut skala Landis & Koch (1977) - konvensi yang lazim,
# bukan angka yang dipilih supaya hasilnya enak.
KAPPA_FLOOR = 0.40


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float | None:
    """Cohen's kappa untuk dua vektor biner. None bila tidak terdefinisi (semua label sama)."""
    a = np.asarray(a, dtype=int)
    b = np.asarray(b, dtype=int)
    n = len(a)
    if n == 0:
        return None
    po = float((a == b).mean())
    pa1, pb1 = a.mean(), b.mean()
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if pe >= 1.0:
        # Keduanya memberi label identik untuk seluruh baris - kesepakatan sempurna secara
        # observasi, tetapi kappa tak terdefinisi. Dilaporkan None, bukan 1.0 yang menyesatkan.
        return None
    return round((po - pe) / (1 - pe), 4)


def f1_binary(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=int)
    tp = int(((y == 1) & (p == 1)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum())
    if tp == 0:
        return 0.0
    prec = tp / (tp + fp)
    rec = tp / (tp + fn)
    return round(2 * prec * rec / (prec + rec), 4)


def _read(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig") as fh:
        return {r["clause_id"]: r for r in csv.DictReader(fh)}


def _labels(row: dict) -> np.ndarray:
    return np.array([1 if str(row.get(c, "")).strip() == "1" else 0 for c in ASPECT_COLS], dtype=int)


def agreement(a_rows: dict[str, dict], b_rows: dict[str, dict]) -> dict:
    """Kappa per aspek + gabungan, hanya pada klausa yang diisi KEDUA pelabel."""
    ids = [i for i in a_rows if i in b_rows and a_rows[i].get("sentimen") and b_rows[i].get("sentimen")]
    A = np.array([_labels(a_rows[i]) for i in ids]) if ids else np.zeros((0, len(ASPECT_COLS)), int)
    B = np.array([_labels(b_rows[i]) for i in ids]) if ids else np.zeros((0, len(ASPECT_COLS)), int)
    per_aspect = {}
    for j, a in enumerate(ALL_ASPECTS):
        k = cohen_kappa(A[:, j], B[:, j]) if len(ids) else None
        per_aspect[a] = {
            "kappa": k,
            "support_A": int(A[:, j].sum()) if len(ids) else 0,
            "support_B": int(B[:, j].sum()) if len(ids) else 0,
            "interpretable": (k is not None and k >= KAPPA_FLOOR),
        }
    pooled = cohen_kappa(A.reshape(-1), B.reshape(-1)) if len(ids) else None
    exact = float((A == B).all(axis=1).mean()) if len(ids) else None
    return {"n_both": len(ids), "ids": ids, "per_aspect": per_aspect,
            "pooled_kappa": pooled, "exact_row_agreement": None if exact is None else round(exact, 4)}


def reference_labels(a_rows, b_rows, ids, adjudicated: dict[str, dict] | None):
    """Label rujukan: sepakat -> pakai; beda -> adjudikasi bila ada, kalau tidak dilewati."""
    ref: dict[str, np.ndarray] = {}
    pending: list[dict] = []
    for i in ids:
        la, lb = _labels(a_rows[i]), _labels(b_rows[i])
        if (la == lb).all():
            ref[i] = la
        elif adjudicated and i in adjudicated and adjudicated[i].get("sentimen"):
            ref[i] = _labels(adjudicated[i])
        else:
            pending.append({
                "clause_id": i, "clause_text": a_rows[i]["clause_text"],
                "label_A": ",".join(a for a, v in zip(ALL_ASPECTS, la) if v) or "-",
                "label_B": ",".join(a for a, v in zip(ALL_ASPECTS, lb) if v) or "-",
                **{c: "" for c in ASPECT_COLS}, "sentimen": "", "catatan_adjudikator": "",
            })
    return ref, pending


def evaluate(ref: dict[str, np.ndarray], texts: dict[str, str], sources: dict[str, str]) -> dict:
    ids = list(ref)
    Y = np.array([ref[i] for i in ids])
    T = [texts[i] for i in ids]
    out: dict = {"n_reference": len(ids), "models": {}}

    def pack(P: np.ndarray, subset_ids: list[str] | None = None) -> dict:
        if subset_ids is not None:
            idx = [ids.index(i) for i in subset_ids]
            Yy, Pp = Y[idx], P[idx]
        else:
            Yy, Pp = Y, P
        per = {a: {"f1": f1_binary(Yy[:, j], Pp[:, j]), "support": int(Yy[:, j].sum())}
               for j, a in enumerate(ALL_ASPECTS)}
        macro = round(float(np.mean([v["f1"] for v in per.values()])), 4)
        micro = f1_binary(Yy.reshape(-1), Pp.reshape(-1))
        return {"aspect_macro_f1": macro, "aspect_micro_f1": micro, "per_class": per, "n": int(len(Yy))}

    # Pembanding dipinjam dari evaluate_gold.py supaya definisinya identik di kedua evaluasi.
    from evaluate_gold import predict_lexicon, predict_tfidf, predict_indobert  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    a, _ = predict_lexicon(T)
    out["models"]["lexicon_rule_based"] = pack(a)

    train_path = REPO_ROOT / "data" / "processed" / "clauses_train.csv"
    if train_path.exists():
        train = pd.read_csv(train_path)
        train["clause_text"] = train["clause_text"].fillna("").astype(str)
        a, _ = predict_tfidf(train, T)
        out["models"]["tfidf_logreg"] = pack(a)
    else:
        out["models"]["tfidf_logreg"] = {"skipped": "clauses_train.csv tidak ada"}

    res = predict_indobert(T)
    out["models"]["indobert_finetuned"] = pack(res[0]) if res is not None else {"skipped": "checkpoint tidak ada"}

    # Label gold-LLM sebagai "pendekatan" keempat - hanya pada klausa yang berasal dari gold.
    gold_ids = [i for i in ids if sources.get(i) == "gold"]
    if gold_ids and GOLD.exists():
        gold = _read(GOLD)
        P = np.array([_labels(gold[i]) if i in gold else np.zeros(len(ASPECT_COLS), int) for i in ids])
        out["models"]["gold_llm_labels_adr017"] = pack(P, gold_ids)
    return out


def main() -> int:
    if not (A_PATH.exists() and B_PATH.exists()):
        print("Belum ada berkas pelabel yang selesai. Diharapkan:")
        print(f"  {A_PATH}\n  {B_PATH}")
        print("Buat paketnya dulu: python scripts/build_aspect_human_pack.py")
        return 1
    a_rows, b_rows = _read(A_PATH), _read(B_PATH)
    agree = agreement(a_rows, b_rows)
    adjudicated = _read(ADJ_DONE) if ADJ_DONE.exists() else None
    ref, pending = reference_labels(a_rows, b_rows, agree["ids"], adjudicated)

    if pending:
        with ADJ_TASK.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(pending[0].keys()))
            w.writeheader()
            w.writerows(pending)

    sources = {}
    if MANIFEST.exists():
        sources = json.loads(MANIFEST.read_text(encoding="utf-8")).get("sumber", {})
    texts = {i: a_rows[i]["clause_text"] for i in agree["ids"]}
    results = {
        "provenance": "Dua pelabel manusia independen (A, B) dari paket scripts/build_aspect_human_pack.py; "
                      "rujukan = baris yang disepakati keduanya + keputusan adjudikator ketiga bila ada.",
        "kappa_floor": KAPPA_FLOOR,
        "agreement": {k: v for k, v in agree.items() if k != "ids"},
        "n_pending_adjudication": len(pending),
        "evaluation": evaluate(ref, texts, sources) if ref else {"n_reference": 0, "models": {}},
    }
    EVAL_OUT.mkdir(parents=True, exist_ok=True)
    (EVAL_OUT / "aspect_human_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"klausa diisi kedua pelabel : {agree['n_both']}")
    print(f"kesepakatan baris persis    : {agree['exact_row_agreement']}")
    print(f"kappa gabungan              : {agree['pooled_kappa']}")
    print(f"rujukan tersedia            : {len(ref)}  (menunggu adjudikasi: {len(pending)})")
    print("\nkappa per aspek:")
    for a, v in agree["per_aspect"].items():
        flag = "" if v["interpretable"] else "   <- di bawah ambang, F1 aspek ini TIDAK ditafsirkan"
        print(f"  {a:24s} {str(v['kappa']):>7s}  (A={v['support_A']}, B={v['support_B']}){flag}")
    ev = results["evaluation"]
    if ev.get("models"):
        print(f"\n{'pendekatan':28s} {'aspek macro':>12s} {'aspek micro':>12s} {'n':>5s}")
        for name, m in ev["models"].items():
            if "skipped" in m:
                print(f"{name:28s} {'-':>12s} {'-':>12s}   ({m['skipped']})")
            else:
                print(f"{name:28s} {m['aspect_macro_f1']:>12.3f} {m['aspect_micro_f1']:>12.3f} {m['n']:>5d}")
    if pending:
        print(f"\n{len(pending)} baris berbeda antar-pelabel ditulis ke {ADJ_TASK.name} - putuskan oleh orang ketiga,")
        print(f"simpan sebagai {ADJ_DONE.name}, lalu jalankan ulang skrip ini.")
    print(f"\nHasil: {EVAL_OUT / 'aspect_human_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
