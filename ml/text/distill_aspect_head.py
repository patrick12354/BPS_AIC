"""L0' - latih ulang KEPALA ASPEK di atas encoder beku, dari label semantik alih-alih leksikon.

Kenapa hanya kepalanya. Temuan L0 (MODEL_CARD §3.3b): kepala aspek yang dilatih dari label
leksikon memang hanya memulihkan leksikon (0,579 vs 0,581 pada label manusia), sedangkan
pembacaan semantik - gold ADR-017 (0,704) dan LLM zero-shot (0,660) - jauh lebih dekat ke
manusia. Encoder IndoBERT yang sudah di-fine-tune tidak diubah: representasinya sudah belajar
bahasa marketplace (bukti: sentimen LULUS pada label manusia). Yang diganti hanya pemetaan
representasi -> aspek, dan sumber labelnya.

Protokol - ditulis sebelum angka dilihat, supaya tidak ada yang menyesuaikan protokol ke angka:

1. TEST = 120 klausa berlabel manusia (aspect_human_B_sisa_done.csv). TIDAK PERNAH ikut latih,
   tidak dipakai memilih hyperparameter, dilihat SATU KALI di akhir.
2. TRAIN = gold ADR-017 (500) DIKURANGI klausa yang ada di TEST -> 411 klausa. Label LLM
   "yakin" yang tidak diperiksa manusia TIDAK dipakai - L0 membuktikan hanya 53% cocok persis.
3. Embedding: mean-pooling encoder beku (mode eval, tanpa dropout), dihitung sekali.
4. Hyperparameter (epoch, weight decay, pos_weight, ambang) dipilih dengan 5-fold CV di TRAIN
   - macro F1 rata-rata lintas fold, tanpa melihat TEST.
5. Latih ulang pada seluruh TRAIN dengan hyperparameter terpilih; evaluasi SEKALI di TEST;
   bandingkan dengan kepala lama pada TEST yang sama, dan dengan leksikon.
6. Artefak baru hanya DITULIS ke ml/text/artifacts/aspect_head_v2.pt bila macro F1-nya di TEST
   melampaui kepala lama. Kalau tidak, hasilnya tetap ditulis ke ml/evaluation/ dan artefak
   TIDAK dibuat - sistem tetap memakai kepala lama. Gagal pun informasi.

Artefaknya kecil (11x768 bobot + bias + ambang, ~35 KB) dan DILACAK git di ml/text/artifacts/,
bukan di models/ (yang tidak dilacak dan dipasang sebagai volume). TextModelAdapter memuatnya
sebagai lapisan di atas checkpoint bila ada - lihat adapter untuk aturannya.

Jalankan:
    python ml/text/distill_aspect_head.py
    python ml/text/distill_aspect_head.py --dry-run   # protokol + CV saja, tanpa menulis artefak
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lexicon import ALL_ASPECTS  # noqa: E402

ANNOT = REPO_ROOT / "data" / "annotation"
GOLD = ANNOT / "gold_labels.csv"
HUMAN = ANNOT / "aspect_human_B_sisa_done.csv"
HUMAN_FULL = ANNOT / "aspect_human_B_done.csv"
CHECKPOINT = REPO_ROOT / "models" / "indobert-nlp01" / "model.pt"
ARTIFACT_DIR = REPO_ROOT / "ml" / "text" / "artifacts"
ARTIFACT = ARTIFACT_DIR / "aspect_head_v2.pt"
EVAL_OUT = REPO_ROOT / "ml" / "evaluation" / "aspect_head_v2_results.json"

ASPECT_COLS = [f"asp_{a}" for a in ALL_ASPECTS]
SEED = 42
N_FOLDS = 5

# Kisi hyperparameter kecil dan dinyatakan di muka. Kisi besar pada 411 contoh = memancing
# kebetulan; yang dicari bukan angka CV tertinggi, melainkan konfigurasi yang stabil.
GRID = {
    "epochs": [60, 120, 200],
    "weight_decay": [1e-4, 1e-3, 1e-2],
    "lr": [5e-3],
    "use_pos_weight": [True, False],
    "warm_start": [True, False],
}
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7]


def _read(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig") as fh:
        return {r["clause_id"]: r for r in csv.DictReader(fh)}


def _labels(row: dict) -> np.ndarray:
    return np.array([1 if str(row.get(c, "")).strip() == "1" else 0 for c in ASPECT_COLS], dtype=np.float32)


def f1_binary(y: np.ndarray, p: np.ndarray) -> float:
    tp = float(((y == 1) & (p == 1)).sum())
    fp = float(((y == 0) & (p == 1)).sum())
    fn = float(((y == 1) & (p == 0)).sum())
    if tp == 0:
        return 0.0
    prec, rec = tp / (tp + fp), tp / (tp + fn)
    return 2 * prec * rec / (prec + rec)


def macro_micro(Y: np.ndarray, P: np.ndarray) -> tuple[float, float, dict]:
    per = {a: f1_binary(Y[:, j], P[:, j]) for j, a in enumerate(ALL_ASPECTS)}
    return float(np.mean(list(per.values()))), f1_binary(Y.reshape(-1), P.reshape(-1)), per


def embed(texts: list[str]):
    """Mean-pooling encoder beku - identik dengan DualHeadClassifier.forward tanpa dropout."""
    import torch  # noqa: PLC0415
    from transformers import AutoTokenizer  # noqa: PLC0415
    from model import DualHeadClassifier  # noqa: PLC0415

    bundle = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = DualHeadClassifier(bundle["base_model"])
    model.load_state_dict(bundle["state_dict"])
    model.eval()
    tok = AutoTokenizer.from_pretrained(str(CHECKPOINT.parent))
    outs = []
    with torch.no_grad():
        for s in range(0, len(texts), 64):
            enc = tok(texts[s:s + 64], truncation=True, max_length=32, padding=True, return_tensors="pt")
            h = model.encoder(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"]).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1).float()
            outs.append(((h * m).sum(1) / m.sum(1).clamp(min=1e-9)).numpy())
    X = np.vstack(outs).astype(np.float32)
    old_w = bundle["state_dict"]["aspect_head.weight"].numpy().copy()
    old_b = bundle["state_dict"]["aspect_head.bias"].numpy().copy()
    # Kepala lama mungkin urutan aspeknya berbeda dari ALL_ASPECTS - selaraskan.
    order = [bundle["aspects"].index(a) for a in ALL_ASPECTS]
    old_w, old_b = old_w[order], old_b[order]
    return X, (old_w, old_b), float(bundle.get("aspect_threshold", 0.5))


def train_head(X: np.ndarray, Y: np.ndarray, epochs: int, weight_decay: float, lr: float,
               use_pos_weight: bool, warm_start: bool, init: tuple[np.ndarray, np.ndarray],
               seed: int = SEED):
    """Regresi logistik multi-label (satu lapisan linier) - full-batch, deterministik."""
    import torch  # noqa: PLC0415

    torch.manual_seed(seed)
    Xt = torch.from_numpy(X)
    Yt = torch.from_numpy(Y)
    lin = torch.nn.Linear(X.shape[1], Y.shape[1])
    if warm_start:
        with torch.no_grad():
            lin.weight.copy_(torch.from_numpy(init[0]))
            lin.bias.copy_(torch.from_numpy(init[1]))
    pos_w = None
    if use_pos_weight:
        pos = Y.sum(0)
        neg = len(Y) - pos
        pos_w = torch.from_numpy(np.clip(neg / np.maximum(pos, 1.0), 1.0, 10.0).astype(np.float32))
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_w)
    opt = torch.optim.AdamW(lin.parameters(), lr=lr, weight_decay=weight_decay)
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(lin(Xt), Yt)
        loss.backward()
        opt.step()
    with torch.no_grad():
        return lin.weight.numpy().copy(), lin.bias.numpy().copy()


def predict(X: np.ndarray, w: np.ndarray, b: np.ndarray, thr: float) -> np.ndarray:
    z = X @ w.T + b
    return (1.0 / (1.0 + np.exp(-z)) >= thr).astype(int)


def cv_select(X: np.ndarray, Y: np.ndarray, init) -> tuple[dict, list[dict]]:
    rng = np.random.RandomState(SEED)
    idx = rng.permutation(len(X))
    folds = np.array_split(idx, N_FOLDS)
    rows = []
    for ep in GRID["epochs"]:
        for wd in GRID["weight_decay"]:
            for lr in GRID["lr"]:
                for pw in GRID["use_pos_weight"]:
                    for ws in GRID["warm_start"]:
                        per_thr = {t: [] for t in THRESHOLDS}
                        for k in range(N_FOLDS):
                            te = folds[k]
                            tr = np.concatenate([folds[j] for j in range(N_FOLDS) if j != k])
                            w, b = train_head(X[tr], Y[tr], ep, wd, lr, pw, ws, init)
                            for t in THRESHOLDS:
                                per_thr[t].append(macro_micro(Y[te], predict(X[te], w, b, t))[0])
                        for t in THRESHOLDS:
                            rows.append({"epochs": ep, "weight_decay": wd, "lr": lr,
                                         "use_pos_weight": pw, "warm_start": ws, "threshold": t,
                                         "cv_macro_f1": round(float(np.mean(per_thr[t])), 4),
                                         "cv_std": round(float(np.std(per_thr[t])), 4)})
    rows.sort(key=lambda r: (-r["cv_macro_f1"], r["cv_std"]))
    return rows[0], rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CHECKPOINT.exists():
        print(f"checkpoint tidak ada: {CHECKPOINT}")
        return 1
    human_path = HUMAN_FULL if HUMAN_FULL.exists() else HUMAN
    if not human_path.exists():
        print("label manusia belum ada - jalankan evaluate_aspect_human.py dulu")
        return 1

    gold = _read(GOLD)
    human = {i: r for i, r in _read(human_path).items() if r.get("sentimen")}
    test_ids = list(human)
    train_ids = [i for i in gold if i not in human]
    print(f"TRAIN = {len(train_ids)} klausa gold (di luar TEST) · TEST = {len(test_ids)} klausa manusia")

    texts = [gold[i]["clause_text"] for i in train_ids] + [human[i]["clause_text"] for i in test_ids]
    X, init, old_thr = embed(texts)
    Xtr, Xte = X[:len(train_ids)], X[len(train_ids):]
    Ytr = np.array([_labels(gold[i]) for i in train_ids])
    Yte = np.array([_labels(human[i]) for i in test_ids])

    print("CV 5-fold di TRAIN ...")
    best, table = cv_select(Xtr, Ytr, init)
    print(f"terpilih: {best}")

    # Kepala LAMA di TEST - pembanding utama, dihitung dari bobot yang sama persis dengan
    # yang dipakai produksi, pada ambang produksinya.
    old_macro, old_micro, old_per = macro_micro(Yte, predict(Xte, init[0], init[1], old_thr))

    w, b = train_head(Xtr, Ytr, best["epochs"], best["weight_decay"], best["lr"],
                      best["use_pos_weight"], best["warm_start"], init)
    new_macro, new_micro, new_per = macro_micro(Yte, predict(Xte, w, b, best["threshold"]))

    results = {
        "protocol": "TEST = 120 klausa berlabel manusia, tidak pernah ikut latih/seleksi; TRAIN = gold ADR-017 "
                    "minus TEST; encoder beku; kepala dipilih via 5-fold CV di TRAIN; TEST dilihat sekali.",
        "n_train": len(train_ids), "n_test": len(test_ids),
        "selected": best,
        "cv_top5": table[:5],
        "old_head_on_test": {"threshold": old_thr, "macro_f1": round(old_macro, 4),
                             "micro_f1": round(old_micro, 4), "per_class": {k: round(v, 4) for k, v in old_per.items()}},
        "new_head_on_test": {"threshold": best["threshold"], "macro_f1": round(new_macro, 4),
                             "micro_f1": round(new_micro, 4), "per_class": {k: round(v, 4) for k, v in new_per.items()}},
        "lexicon_on_test_reference": 0.581,
        "artifact_written": False,
    }

    print(f"\n{'':26s} {'macro':>7s} {'micro':>7s}")
    print(f"{'kepala lama (thr '+str(old_thr)+')':26s} {old_macro:7.3f} {old_micro:7.3f}")
    print(f"{'kepala baru (thr '+str(best['threshold'])+')':26s} {new_macro:7.3f} {new_micro:7.3f}")
    print(f"{'leksikon (rujukan L0)':26s} {0.581:7.3f}")
    print("\nper aspek (lama -> baru):")
    for a in ALL_ASPECTS:
        print(f"  {a:24s} {old_per[a]:.3f} -> {new_per[a]:.3f}")

    menang = new_macro > old_macro + 1e-9
    if menang and not args.dry_run:
        import torch  # noqa: PLC0415
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        torch.save({
            "aspect_head.weight": torch.from_numpy(w), "aspect_head.bias": torch.from_numpy(b),
            "aspects": list(ALL_ASPECTS), "aspect_threshold": float(best["threshold"]),
            "version": "asp-v2",
            "provenance": ("kepala aspek dilatih ulang di atas encoder beku dari 411 klausa gold ADR-017; "
                           "dipilih via 5-fold CV; dievaluasi sekali pada 120 klausa berlabel manusia "
                           f"(macro F1 {new_macro:.3f} vs kepala lama {old_macro:.3f}). Lihat MODEL_CARD §3.3c."),
        }, ARTIFACT)
        results["artifact_written"] = True
        print(f"\nARTEFAK DITULIS: {ARTIFACT}  (kepala baru mengungguli kepala lama di TEST)")
    elif not menang:
        print("\nKepala baru TIDAK mengungguli kepala lama di TEST - artefak tidak ditulis; sistem tetap memakai kepala lama.")
    else:
        print("\n--dry-run: artefak tidak ditulis.")

    EVAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    EVAL_OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"hasil: {EVAL_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
