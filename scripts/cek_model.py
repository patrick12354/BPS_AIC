"""Pemeriksaan kesehatan model — satu perintah untuk menjawab "apakah ini bekerja benar?".

Empat lapis, dari yang paling murah ke yang paling mahal:

1. **Kesiapan**  — checkpoint ada? taksonomi di kode masih cocok dengan konfigurasi?
2. **Perilaku**  — model diberi ulasan yang jawabannya jelas bagi manusia mana pun. Ini lapis
                   yang paling berguna dibaca orang non-teknis: benar atau salahnya terlihat
                   langsung, tanpa perlu memahami macro F1.
3. **Ketahanan** — masukan aneh: kosong, satu kata, emoji, sangat panjang, campur Inggris.
                   Yang diuji bukan akurasi melainkan apakah sistem tetap berdiri.
4. **Angka**     — metrik yang sudah diukur pada label manusia, dibaca dari berkas evaluasi.

Kasus pada lapis 2 sengaja memuat dua yang **modelnya memang salah** (negasi dan sarkasme).
Pemeriksaan kesehatan yang hanya memuat contoh berhasil tidak memeriksa apa pun — ia hanya
mengonfirmasi bahwa kita pandai memilih contoh.

Jalankan:
    python scripts/cek_model.py
    python scripts/cek_model.py --cepat     # lewati lapis 3 dan 4
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "apps" / "api"))

OK, GAGAL, WARN = "  [OK] ", "  [X]  ", "  [!]  "

# Ulasan yang jawabannya tidak akan diperdebatkan manusia mana pun.
KASUS = [
    ("ukurannya kekecilan padahal pesan L", "ukuran_varian", "negatif"),
    ("paketnya telat seminggu, kecewa", "pengiriman", "negatif"),
    ("barang datang rusak, kardusnya penyok", "kualitas_produk", "negatif"),
    ("pengiriman cepat sekali, packing rapi", "pengiriman", "positif"),
    ("bahannya adem dan jahitannya rapi", "kualitas_produk", "positif"),
    ("harganya murah banget, worth it", "harga_value", "positif"),
    ("seller responsif, fast respon banget", "pelayanan_penjual", "positif"),
    ("warnanya beda jauh dari foto di aplikasi", "kesesuaian_deskripsi", "negatif"),
    # Dua di bawah sengaja sulit — negasi dan sarkasme, keduanya tercatat di LIMITATIONS.
    ("kualitasnya not oke", "kualitas_produk", "negatif"),
    ("bagus banget sampai rusak dalam sehari", "kualitas_produk", "negatif"),
]

ANEH = [
    ("kosong", ""),
    ("spasi saja", "   "),
    ("satu kata", "oke"),
    ("emoji saja", "\U0001F600\U0001F600"),
    ("angka saja", "12345"),
    ("campur Inggris", "the size is too small, sangat kecewa"),
    ("sangat panjang", "bagus " * 300),
    ("tanda baca", "!!!???..."),
]


def garis(judul: str) -> None:
    print("\n" + "=" * 68)
    print(judul)
    print("=" * 68)


def lapis1_kesiapan() -> bool:
    garis("1. KESIAPAN — apakah semua yang dibutuhkan tersedia?")
    sehat = True

    ckpt = REPO / "models" / "indobert-nlp01" / "model.pt"
    if ckpt.exists():
        print(OK + "Checkpoint ada (%.0f MB)" % (ckpt.stat().st_size / 1e6))
    else:
        print(WARN + "Checkpoint TIDAK ada — sistem akan memakai jalur leksikon.")
        print("       Jalankan: python scripts/download_checkpoint.py")
        sehat = False

    # Kalibrasi diperiksa terpisah dari keberadaan checkpoint: checkpoint yang ada tetapi
    # belum dikalibrasi berjalan normal, hanya angka keyakinannya tidak tampil di layar.
    # Itu keadaan yang sah, jadi ia peringatan - bukan kegagalan.
    from app.adapters.text_model import TextModelAdapter  # noqa: PLC0415

    adapter = TextModelAdapter()
    if adapter.calibrated:
        print(OK + "Model terkalibrasi (T=%s) — angka keyakinan tampil di laporan"
              % adapter.sentiment_temperature)
    elif adapter.mode == "full":
        print(WARN + "Checkpoint belum dikalibrasi — angka keyakinan disembunyikan dari UI.")
        print("       Jalankan: python ml/text/calibrate.py")

    # Jalur visual. Nonaktif adalah keadaan yang BENAR hari ini (gerbangnya belum lolos),
    # jadi ia dilaporkan sebagai keterangan, bukan sebagai masalah yang perlu diperbaiki.
    from app.adapters.vision_model import VisionModelAdapter  # noqa: PLC0415

    visual = VisionModelAdapter()
    if visual.active:
        print(OK + "Jalur visual aktif (%s)" % visual.model_version)
    else:
        print(WARN + "Jalur visual nonaktif: %s" % visual.inactive_reason)

    try:
        from app.schemas.enums import verify_taxonomy_matches_config

        verify_taxonomy_matches_config()
        print(OK + "Taksonomi di kode cocok dengan configs/taxonomy.yaml")
    except Exception as exc:  # noqa: BLE001
        print(GAGAL + "Taksonomi TIDAK cocok: %s" % exc)
        sehat = False

    return sehat


def lapis2_perilaku() -> bool:
    garis("2. PERILAKU — ulasan yang jawabannya jelas bagi manusia")
    from app.adapters.text_model import TextModelAdapter
    from app.schemas import Category, ProcessedReview

    adapter = TextModelAdapter()
    reviews = [
        ProcessedReview(
            review_id="c%d" % i, clean_text=teks, pii_redacted=False, rating=None,
            category=Category.OTHER, has_image=False, image_refs=[], timestamp=None,
        )
        for i, (teks, _, _) in enumerate(KASUS)
    ]
    hasil = {p.review_id: p for p in adapter.classify(reviews)}

    benar_aspek = benar_sent = 0
    print("  %-44s %-22s %s" % ("ulasan", "aspek", "sentimen"))
    print("  " + "-" * 78)
    for i, (teks, aspek_harap, sent_harap) in enumerate(KASUS):
        pred = hasil["c%d" % i].predictions
        aspek = sorted({x.aspect.value for x in pred})
        sent = sorted({x.sentiment.value for x in pred})
        a_ok = aspek_harap in aspek
        s_ok = sent_harap in sent
        benar_aspek += a_ok
        benar_sent += s_ok
        print("  %-44s %s%-20s %s%s" % (
            teks[:43],
            "v " if a_ok else "x ", (",".join(aspek) or "kosong")[:20],
            "v " if s_ok else "x ", ",".join(sent) or "-",
        ))

    n = len(KASUS)
    print("\n  Aspek benar    : %d/%d" % (benar_aspek, n))
    print("  Sentimen benar : %d/%d" % (benar_sent, n))
    print("\n  Dua kasus terakhir (negasi & sarkasme) memang sulit dan boleh salah —")
    print("  keduanya sudah tercatat sebagai keterbatasan di docs/LIMITATIONS.md.")
    return benar_sent >= n - 3


def lapis3_ketahanan() -> bool:
    garis("3. KETAHANAN — masukan aneh tidak boleh menjatuhkan sistem")
    from app.adapters.text_model import TextModelAdapter
    from app.schemas import Category, RawReview, ReviewSource
    from app.services.analyze import AnalyzeService

    svc = AnalyzeService(text_adapter=TextModelAdapter(), embedding_adapter=None, baseline={})
    sehat = True
    for nama, teks in ANEH:
        try:
            r = svc.analyze([
                RawReview(review_id="x", text=teks, source=ReviewSource.MANUAL_UPLOAD,
                          category=Category.OTHER)
            ])
            print(OK + "%-16s -> %d ulasan diproses, %d kartu, peringatan: %s" % (
                nama, r.summary.total_reviews, len(r.top_actions),
                ", ".join(r.warnings) or "tidak ada"))
        except Exception as exc:  # noqa: BLE001
            print(GAGAL + "%-16s -> %s: %s" % (nama, type(exc).__name__, str(exc)[:55]))
            sehat = False
    return sehat


def lapis4_angka() -> bool:
    garis("4. ANGKA — metrik yang sudah diukur pada label manusia")
    p = REPO / "ml" / "evaluation" / "external_results.json"
    if not p.exists():
        print(WARN + "Belum ada %s. Jalankan ml/text/evaluate_external.py." % p.name)
        return True

    d = json.loads(p.read_text(encoding="utf-8"))
    for nama, hasil in d.get("hasil", {}).items():
        bert = (hasil.get("indobert_finetuned") or {}).get("macro_f1")
        leks = (hasil.get("lexicon_rule_based") or {}).get("macro_f1")
        if bert is None:
            continue
        tanda = OK if (leks is None or bert > leks) else WARN
        baris = "%-32s model %.3f" % (nama, bert)
        if leks is not None:
            baris += "  vs leksikon %.3f" % leks
        print(tanda + baris)

    g = REPO / "ml" / "evaluation" / "visual_gate.json"
    if g.exists():
        v = json.loads(g.read_text(encoding="utf-8"))
        kep = v["varian_prompt"]["all"]["keputusan"]
        print(WARN + "%-32s %s — hasil foto sengaja tidak ditampilkan" % ("gerbang visual VIS-01", kep))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cepat", action="store_true", help="lewati lapis 3 dan 4")
    args = ap.parse_args()

    print("PEMERIKSAAN KESEHATAN MODEL — Ulasin")
    hasil = [lapis1_kesiapan(), lapis2_perilaku()]
    if not args.cepat:
        hasil += [lapis3_ketahanan(), lapis4_angka()]

    garis("KESIMPULAN")
    if all(hasil):
        print("  Seluruh lapis lolos. Sistem berperilaku sesuai yang didokumentasikan.")
        return 0
    print("  Ada lapis yang tidak lolos — baca keluaran di atas.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
