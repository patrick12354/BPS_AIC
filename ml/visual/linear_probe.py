"""VIS-01b - linear probe di atas embedding CLIP beku.

**Kenapa jalur ini ditambahkan.** Gerbang zero-shot (`evaluate_gate.py`) memutuskan NO-GO:
akurasi argmax 45% tidak melampaui pembanding sepele "selalu tebak normal" (61%), dan 61% foto
yang sebenarnya normal salah ditandai bermasalah. Diagnosanya bukan bahwa CLIP tidak melihat
apa-apa, melainkan bahwa RUANG TEKS-nya tidak sejajar dengan pertanyaan produk ini: "a photo of
a damaged product" dan "foto barang normal" berada terlalu berdekatan untuk foto ulasan HP yang
gelap, buram, dan berlatar lantai rumah.

Linear probe memisahkan dua hal itu. Encoder tetap beku - tidak ada yang dilatih ulang, jadi
tidak ada yang bisa dihafal olehnya - tetapi pemetaan dari embedding ke kelas dipelajari dari
foto ulasan Indonesia yang sebenarnya, bukan dipinjam dari kalimat berbahasa Inggris.

**Tiga pagar yang membuat angkanya sah**, sama seperti gerbang zero-shot:

1. **Split per ULASAN, bukan per foto.** Satu ulasan kerap melampirkan empat foto nyaris
   identik; membelahnya per foto menaruh kembaran di kedua sisi dan melambungkan skor.
2. **Cross-validation berulang, bukan satu split.** Dengan 97 foto, satu split 50/50 hanya
   menyisakan belasan foto uji - angkanya lebih ditentukan oleh keberuntungan pembagian
   daripada oleh model. Yang dilaporkan adalah rata-rata beserta sebarannya.
3. **Pembanding sepele selalu ikut dilaporkan.** Model yang tidak mengalahkan "selalu tebak
   normal" tetap NO-GO berapa pun selective accuracy-nya.

**Dua perumusan, sengaja.** Empat kelas adalah bentuk yang dikunci pada Fase 0, tetapi dua di
antaranya hanya punya 4 dan 7 label - terlalu sedikit untuk klaim apa pun. Perumusan biner
("perlu dilihat pemilik toko" vs "tidak") menyatukan ketiga kelas masalah menjadi 36 contoh
melawan 57, dan kebetulan itulah keputusan yang benar-benar dibutuhkan produk: foto ini perlu
Anda periksa sendiri atau tidak. Keduanya dijalankan dan keduanya dilaporkan; yang menentukan
lolos-tidaknya gerbang adalah angka, bukan preferensi.

Jalankan:
    python ml/visual/linear_probe.py
    python ml/visual/linear_probe.py --ulang 20     # lebih banyak pengulangan CV
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]

TASK_CSV = REPO / "data" / "annotation" / "visual_labeling_task.csv"
PHOTOS = REPO / "data" / "raw" / "review_photos"
CACHE = REPO / "ml" / "embeddings" / "clip_probe_features.npz"
OUT = REPO / "ml" / "evaluation" / "visual_probe.json"
# Artefak yang benar-benar dipakai backend. Formatnya npz karena isinya cuma matriks kecil
# (koefisien 512x2) plus metadata - pickle sebuah objek sklearn akan menyeret versi
# sklearn ikut menjadi ketergantungan runtime image API, yang sengaja tidak memasangnya.
PROBE_OUT = REPO / "models" / "visual-probe" / "probe.npz"

MODEL = "openai/clip-vit-base-patch32"

KELAS4 = ["produk_rusak", "salah_kirim", "kemasan_rusak", "normal"]
MASALAH = {"produk_rusak", "salah_kirim", "kemasan_rusak"}

# Kelas dengan label di bawah ini boleh ikut dilatih, tetapi akurasinya TIDAK dilaporkan
# sebagai capaian - satu kekeliruan menggeser angkanya lebih dari sepuluh poin.
MIN_N_LAPOR = 10

# Kisi ambang abstention. Dikalibrasi di dalam fold pelatihan, tidak pernah pada fold uji.
GRID_CONF = np.round(np.arange(0.35, 0.96, 0.05), 3)


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------


def load_gold() -> list[dict]:
    """Baca label manusia. Foto yang manusia sendiri tidak dapat nilai dipisahkan.

    Foto `sulit_dinilai` bukan bahan uji akurasi - tidak ada jawaban benar untuk dibandingkan.
    Ia diuji terpisah: apakah model IKUT abstain di situ.
    """
    if not TASK_CSV.exists():
        raise SystemExit(f"Berkas label tidak ditemukan: {TASK_CSV}")

    rows = []
    for r in csv.DictReader(TASK_CSV.open(encoding="utf-8")):
        label = r["label_manusia"].strip()
        sulit = bool(r["sulit_dinilai"].strip())
        if not label and not sulit:
            continue  # belum dilabeli sama sekali
        rows.append(
            {
                "image_file": r["image_file"],
                # Foto kembar dikenali dari teks ulasan yang sama; kalau teksnya kosong,
                # nama berkas dipakai sehingga foto itu menjadi grupnya sendiri.
                "grup": r["review_text"] or r["image_file"],
                "gold": None if sulit else label,
            }
        )
    return rows


def embed(rows: list[dict], batch: int = 16) -> np.ndarray:
    """Embedding gambar dari CLIP beku, di-cache ke cakram.

    Encoder tidak pernah dilatih, jadi embedding-nya deterministik: menghitungnya ulang setiap
    kali hanya membuang beberapa menit CPU pada setiap percobaan ambang.
    """
    nama = [r["image_file"] for r in rows]
    if CACHE.exists():
        simpan = np.load(CACHE, allow_pickle=True)
        if list(simpan["names"]) == nama and str(simpan["model"]) == MODEL:
            print(f"Embedding dibaca dari cache: {CACHE}")
            return simpan["features"]

    hilang = [n for n in nama if not (PHOTOS / n).exists()]
    if hilang:
        raise SystemExit(
            f"{len(hilang)} dari {len(nama)} foto tidak ada di {PHOTOS}.\n"
            "Foto ulasan tidak ikut di-commit (data/raw/ ada di .gitignore) dan tidak dapat\n"
            "diunduh ulang dari berkas label - nama berkasnya berupa hash isi, bukan URL.\n"
            "Jalankan ulang scripts/prepare_apify_photos.py pada berkas hasil scraper untuk\n"
            "menyusun ulang folder foto sebelum melatih probe."
        )

    import torch  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    from transformers import CLIPModel, CLIPProcessor  # noqa: PLC0415

    print(f"Memuat {MODEL} …", flush=True)
    model = CLIPModel.from_pretrained(MODEL).eval()
    processor = CLIPProcessor.from_pretrained(MODEL)

    def as_tensor(out):
        """transformers 5 mengembalikan objek keluaran, versi sebelumnya tensor langsung."""
        if hasattr(out, "pooler_output"):
            return out.pooler_output
        if hasattr(out, "last_hidden_state"):
            return out.last_hidden_state[:, 0]
        return out

    fitur = []
    with torch.no_grad():
        for i in range(0, len(nama), batch):
            potongan = nama[i : i + batch]
            gambar = [Image.open(PHOTOS / n).convert("RGB") for n in potongan]
            pix = processor(images=gambar, return_tensors="pt")
            f = as_tensor(model.get_image_features(**pix))
            # Normalisasi L2: probe linear pada vektor ternormalisasi setara dengan bekerja
            # pada kemiripan kosinus, ruang yang sama dengan tempat CLIP dilatih.
            f = f / f.norm(dim=-1, keepdim=True)
            fitur.append(f.cpu().numpy())
            print(f"  {min(i + batch, len(nama))}/{len(nama)}", flush=True)

    features = np.concatenate(fitur).astype(np.float32)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE, features=features, names=np.array(nama), model=MODEL)
    print(f"Embedding disimpan ke {CACHE}")
    return features


# --------------------------------------------------------------------------------------
# Evaluasi
# --------------------------------------------------------------------------------------


def fold_per_ulasan(grup: list[str], seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Satu pembagian latih/uji yang menjaga foto satu ulasan tetap di sisi yang sama."""
    unik = sorted(set(grup))
    rng = np.random.default_rng(seed)
    rng.shuffle(unik)
    uji_grup = set(unik[: max(1, len(unik) // 3)])
    mask_uji = np.array([g in uji_grup for g in grup])
    return ~mask_uji, mask_uji


def satu_putaran(X, y, grup, seed, kelas) -> dict | None:
    """Latih pada fold latih, kalibrasi ambang di dalamnya, lapor pada fold uji."""
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415

    latih, uji = fold_per_ulasan(grup, seed)
    if len(set(y[latih])) < 2 or uji.sum() == 0:
        return None  # pembagian yang kebetulan menyisakan satu kelas saja

    # class_weight="balanced" bukan hiasan: 57 dari 93 foto berkelas `normal`, dan tanpa
    # penyeimbangan model belajar bahwa menjawab "normal" selalu adalah strategi teraman -
    # persis kegagalan yang membuat zero-shot ditolak.
    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced").fit(
        X[latih], y[latih]
    )

    def ukur(mask, conf_min):
        probs = clf.predict_proba(X[mask])
        atas = probs.max(axis=1)
        tebak = clf.classes_[probs.argmax(axis=1)]
        jawab = atas >= conf_min
        benar = (tebak == y[mask]) & jawab
        return {
            "n": int(mask.sum()),
            "n_dijawab": int(jawab.sum()),
            "coverage": float(jawab.mean()) if mask.sum() else 0.0,
            "selective_accuracy": float(benar.sum() / jawab.sum()) if jawab.sum() else 0.0,
            "akurasi_argmax": float((tebak == y[mask]).mean()),
            "tebak": tebak,
            "jawab": jawab,
        }

    # Ambang dipilih HANYA dari fold latih. Memilihnya pada fold uji akan melaporkan angka
    # yang sudah dioptimalkan terhadap jawabannya sendiri.
    kandidat = [(c, ukur(latih, c)) for c in GRID_CONF]
    layak = [(c, m) for c, m in kandidat if 0.30 <= m["coverage"] <= 0.95]
    conf_min = max(layak or kandidat, key=lambda km: (km[1]["selective_accuracy"], km[1]["coverage"]))[0]

    hasil = ukur(uji, conf_min)
    y_uji = y[uji]

    per_kelas = {}
    for k in kelas:
        ada = y_uji == k
        if ada.sum():
            per_kelas[k] = {"n": int(ada.sum()), "benar": int((hasil["tebak"][ada] == k).sum())}

    return {
        "min_confidence": float(conf_min),
        "coverage": hasil["coverage"],
        "selective_accuracy": hasil["selective_accuracy"],
        "akurasi_argmax": hasil["akurasi_argmax"],
        # Pembanding sepele dihitung pada fold uji yang SAMA - bukan pada keseluruhan data -
        # supaya perbandingannya adil.
        "akurasi_kelas_mayoritas": float((y_uji == _mayoritas(y[latih])).mean()),
        "per_kelas": per_kelas,
    }


def _mayoritas(y) -> str:
    nilai, jumlah = np.unique(y, return_counts=True)
    return str(nilai[jumlah.argmax()])


def rangkum(putaran: list[dict], kelas: list[str]) -> dict:
    """Rata-rata dan sebaran lintas pengulangan.

    Sebaran ikut dilaporkan, bukan hanya rata-rata: pada 97 foto, selisih antar-fold kerap
    lebih besar daripada selisih antar-model, dan menyembunyikannya akan membuat perbaikan
    yang sebenarnya derau terlihat seperti kemajuan.
    """

    def stat(kunci):
        nilai = [p[kunci] for p in putaran]
        return {
            "rata2": round(float(np.mean(nilai)), 4),
            "sd": round(float(np.std(nilai)), 4),
            "min": round(float(np.min(nilai)), 4),
            "maks": round(float(np.max(nilai)), 4),
        }

    gabung = {}
    for k in kelas:
        n = sum(p["per_kelas"].get(k, {}).get("n", 0) for p in putaran)
        benar = sum(p["per_kelas"].get(k, {}).get("benar", 0) for p in putaran)
        if n:
            gabung[k] = {
                "n_terakumulasi": n,
                "akurasi": round(benar / n, 4),
                "dilaporkan": n / len(putaran) >= MIN_N_LAPOR,
            }

    return {
        "n_putaran": len(putaran),
        "selective_accuracy": stat("selective_accuracy"),
        "coverage": stat("coverage"),
        "akurasi_argmax": stat("akurasi_argmax"),
        "akurasi_kelas_mayoritas": stat("akurasi_kelas_mayoritas"),
        "min_confidence_terpilih": stat("min_confidence"),
        "per_kelas": gabung,
    }


def putuskan(ringkas: dict) -> tuple[str, str]:
    """Terjemahkan angka menjadi keputusan gerbang.

    Syarat pertamanya mutlak dan tidak dapat dikelabui dengan mengatur ambang: model harus
    mengalahkan "selalu tebak kelas mayoritas". Selective accuracy yang tinggi pada coverage
    rendah bisa saja hanya berarti model berani menjawab pada kelas mayoritas saja.
    """
    argmax = ringkas["akurasi_argmax"]["rata2"]
    sepele = ringkas["akurasi_kelas_mayoritas"]["rata2"]
    acc = ringkas["selective_accuracy"]["rata2"]
    cov = ringkas["coverage"]["rata2"]
    sd = ringkas["selective_accuracy"]["sd"]

    if argmax <= sepele:
        return "NO-GO", (
            f"Akurasi argmax {argmax:.0%} tidak melampaui pembanding sepele 'selalu tebak "
            f"kelas mayoritas' ({sepele:.0%}). Probe belum mempelajari apa pun yang berguna."
        )
    layak = [k for k, v in ringkas["per_kelas"].items() if v["dilaporkan"]]
    if acc >= 0.80 and cov >= 0.50 and len(layak) >= 2:
        return "GO", (
            f"Selective accuracy {acc:.0%} (sd {sd:.2f}) pada coverage {cov:.0%}, mengalahkan "
            f"pembanding sepele {sepele:.0%}, dengan {len(layak)} kelas yang jumlah labelnya "
            "memadai. Hasil visual boleh disebut sebagai kapabilitas."
        )
    if acc >= 0.65 and cov >= 0.30:
        return "CONDITIONAL GO", (
            f"Selective accuracy {acc:.0%} (sd {sd:.2f}) pada coverage {cov:.0%}, di atas "
            f"pembanding sepele {sepele:.0%}. Cukup untuk ditampilkan sebagai fitur pendukung "
            "yang menyertakan keterbatasannya, TIDAK boleh disebut sebagai kapabilitas yang "
            "terbukti, dan tidak boleh menjadi sorotan video."
        )
    return "NO-GO", (
        f"Selective accuracy {acc:.0%} pada coverage {cov:.0%} tidak cukup untuk klaim apa pun, "
        f"meski argmax {argmax:.0%} sudah di atas pembanding sepele {sepele:.0%}."
    )


# --------------------------------------------------------------------------------------


def jalankan(X, rows, biner: bool, ulang: int) -> dict:
    dinilai = [i for i, r in enumerate(rows) if r["gold"]]
    y_mentah = [rows[i]["gold"] for i in dinilai]
    y = np.array(
        ["perlu_diperiksa" if v in MASALAH else "normal" for v in y_mentah] if biner else y_mentah
    )
    kelas = ["perlu_diperiksa", "normal"] if biner else KELAS4
    grup = [rows[i]["grup"] for i in dinilai]
    Xd = X[dinilai]

    putaran = [p for s in range(ulang) if (p := satu_putaran(Xd, y, grup, 100 + s, kelas))]
    if not putaran:
        raise SystemExit("Tidak ada pembagian latih/uji yang layak - data terlalu sedikit.")

    ringkas = rangkum(putaran, kelas)
    keputusan, alasan = putuskan(ringkas)
    ringkas["keputusan"] = keputusan
    ringkas["alasan"] = alasan
    ringkas["distribusi_label"] = {k: int((y == k).sum()) for k in kelas}
    return ringkas


def simpan_probe(X, rows, ringkas: dict, path=PROBE_OUT) -> dict:
    """Latih probe final pada SELURUH data berlabel dan tulis artefak yang dapat dimuat backend.

    Dua hal yang membuat berkas ini boleh ada meski gerbangnya belum tentu lolos:

    1. **Vonis gerbang ikut ditulis ke dalamnya.** Backend membaca `keputusan` dari artefak dan
       menolak menyalakan jalur visual kalau isinya NO-GO. Gerbang berhenti menjadi kalimat di
       dokumen yang bisa dilupakan orang, dan menjadi syarat yang dijalankan kode.
    2. **Ambang abstention ikut dibawa.** Ia dikalibrasi di dalam fold latih saat evaluasi;
       menaruhnya di artefak memastikan produksi memakai ambang yang SAMA dengan yang angkanya
       dilaporkan, bukan ambang bawaan yang tidak pernah diukur.

    Probe final dilatih pada seluruh data - itu benar dan bukan kebocoran. Angka yang dilaporkan
    berasal dari cross-validation; model yang dikirim boleh memakai semua label yang ada,
    persis seperti model teks yang dilatih ulang pada train+val setelah hyperparameternya
    dipilih.
    """
    from sklearn.linear_model import LogisticRegression  # noqa: PLC0415

    dinilai = [i for i, r in enumerate(rows) if r["gold"]]
    y = np.array(
        ["perlu_diperiksa" if rows[i]["gold"] in MASALAH else "normal" for i in dinilai]
    )
    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced").fit(X[dinilai], y)

    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "encoder": MODEL,
        "perumusan": "biner_perlu_diperiksa",
        "keputusan": ringkas["keputusan"],
        "alasan": ringkas["alasan"],
        "min_confidence": ringkas["min_confidence_terpilih"]["rata2"],
        "selective_accuracy": ringkas["selective_accuracy"]["rata2"],
        "coverage": ringkas["coverage"]["rata2"],
        "n_berlabel": int(len(dinilai)),
    }
    np.savez(
        path,
        coef=clf.coef_.astype(np.float32),
        intercept=clf.intercept_.astype(np.float32),
        classes=np.array([str(c) for c in clf.classes_]),
        meta=json.dumps(meta, ensure_ascii=False),
    )
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ulang", type=int, default=12, help="jumlah pengulangan cross-validation")
    ap.add_argument(
        "--simpan",
        action="store_true",
        help="tulis artefak probe yang dapat dimuat backend (models/visual-probe/probe.npz)",
    )
    args = ap.parse_args()

    rows = load_gold()
    berlabel = sum(1 for r in rows if r["gold"])
    print(f"{len(rows)} foto ({berlabel} berlabel, {len(rows) - berlabel} sulit dinilai).")
    if berlabel < 40:
        print("Label terlalu sedikit untuk melatih probe.", file=sys.stderr)
        return 1

    X = embed(rows)

    hasil = {}
    for nama, biner in (("empat_kelas", False), ("biner_perlu_diperiksa", True)):
        print(f"\n=== Perumusan: {nama} ===", flush=True)
        r = jalankan(X, rows, biner, args.ulang)
        print(
            f"  argmax {r['akurasi_argmax']['rata2']:.0%} vs sepele "
            f"{r['akurasi_kelas_mayoritas']['rata2']:.0%} · "
            f"selective {r['selective_accuracy']['rata2']:.0%} "
            f"(sd {r['selective_accuracy']['sd']:.2f}) pada coverage "
            f"{r['coverage']['rata2']:.0%}"
        )
        print(f"  -> {r['keputusan']}", flush=True)
        hasil[nama] = r

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "catatan": (
                    "Linear probe di atas embedding CLIP BEKU. Encoder tidak dilatih ulang. "
                    "Ambang abstention dikalibrasi di dalam fold latih dan dilaporkan pada fold "
                    "uji. Split dilakukan per ULASAN, bukan per foto. Angka adalah rata-rata "
                    "lintas pengulangan cross-validation beserta sebarannya - pada 97 foto, "
                    "satu split tunggal lebih menggambarkan keberuntungan pembagian daripada "
                    "kemampuan model."
                ),
                "model_encoder": MODEL,
                "n_foto": len(rows),
                "n_berlabel": berlabel,
                "pembanding": (
                    "Zero-shot pada data yang sama menghasilkan akurasi argmax 45% terhadap "
                    "pembanding sepele 61% (ml/evaluation/visual_gate.json)."
                ),
                "kelas_tidak_dilaporkan": (
                    f"Kelas dengan rata-rata n < {MIN_N_LAPOR} per fold ditandai "
                    "dilaporkan=false dan tidak boleh disebut sebagai capaian."
                ),
                "perumusan": hasil,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nDitulis ke {OUT}")

    if args.simpan:
        meta = simpan_probe(X, rows, hasil["biner_perlu_diperiksa"])
        print(f"Artefak probe ditulis ke {PROBE_OUT}")
        print(f"  vonis gerbang di dalam artefak: {meta['keputusan']}")
        if meta["keputusan"] == "NO-GO":
            print(
                "  Backend AKAN MENOLAK menyalakan jalur visual dengan artefak ini. Itu memang\n"
                "  yang seharusnya terjadi - vonisnya dijalankan kode, bukan diingat orang."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
