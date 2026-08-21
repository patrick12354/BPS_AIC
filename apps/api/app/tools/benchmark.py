"""compare_category_baseline() - tool contract bagian 27.3, BEN-01 bagian 24.

Baseline dihitung SEKALI saat persiapan (`scripts/precompute_baseline.py`), bukan real-time -
tidak ada panggilan keluar saat pengguna menjalankan analisis (ADR-012).

Terminologi yang dipakai konsisten dengan bagian 24.2: "baseline kategori" dan "peer aggregate",
BUKAN "kompetitor" atau "rata-rata pasar". Datanya agregat kategori publik, bukan data toko
pesaing yang teridentifikasi, dan menyebutnya kompetitor akan menyesatkan pengguna.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from ..schemas import (
    Aspect,
    AspectAggregate,
    BenchmarkRecord,
    Category,
    ConfidenceLevel,
)

DEFAULT_BASELINE_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "processed" / "category_baseline.json"
)

# Ambang ukuran sampel -> tingkat keyakinan (bagian 24.1). Kategori bersampel kecil TIDAK
# disembunyikan; ia ditampilkan dengan keyakinan rendah supaya pengguna menilai sendiri.
CONFIDENCE_THRESHOLDS = {"tinggi": 500, "sedang": 100}

# Ambang sisi TOKO. Di bawah angka ini, selisih terhadap baseline berhenti bermakna sebagai
# temuan dan hanya layak disebut indikasi awal.
#
# Bukan angka pilihan selera: pada 30 ulasan dengan proporsi 0,2, margin kesalahan 95% masih
# sekitar +-14 poin persentase - sudah lebar, tetapi selisih yang benar-benar besar (20 poin
# ke atas, yang memang muncul di kartu prioritas) masih dapat dibedakan dari nol. Pada 10
# ulasan marginnya +-25 poin dan hampir semua selisih tenggelam di dalamnya.
MIN_STORE_REVIEWS = 30

Z_95 = 1.96  # untuk margin of error proporsi


def _confidence_level(sample_size: int) -> ConfidenceLevel:
    if sample_size >= CONFIDENCE_THRESHOLDS["tinggi"]:
        return ConfidenceLevel.TINGGI
    if sample_size >= CONFIDENCE_THRESHOLDS["sedang"]:
        return ConfidenceLevel.SEDANG
    return ConfidenceLevel.RENDAH


# Keyakinan sebuah perbandingan tidak bisa melampaui sisi terlemahnya. Diurutkan dari yang
# paling lemah supaya `min()` di bawah punya arti.
_CONFIDENCE_ORDER = [ConfidenceLevel.RENDAH, ConfidenceLevel.SEDANG, ConfidenceLevel.TINGGI]


def _weakest(*levels: ConfidenceLevel) -> ConfidenceLevel:
    return min(levels, key=_CONFIDENCE_ORDER.index)


def _margin_of_error(p: float, n: int) -> float:
    """Margin of error proporsi pada tingkat keyakinan 95%.

    Ditampilkan berdampingan dengan angka baseline (bagian 24.1) supaya pembaca tahu presisi
    yang sebenarnya, bukan menerima satu angka tunggal seolah eksak.
    """
    if n <= 0:
        return 0.0
    return round(Z_95 * math.sqrt(max(p * (1.0 - p), 0.0) / n), 4)


def load_baseline(path: Path | None = None) -> dict:
    path = path or DEFAULT_BASELINE_PATH
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def compare_category_baseline(
    aggregates: list[AspectAggregate],
    category: Category,
    total_reviews: int,
    baseline: dict | None = None,
) -> list[BenchmarkRecord]:
    """Bandingkan distribusi keluhan toko terhadap baseline kategori sejenis.

    Args:
        aggregates: keluaran calculate_aspect_statistics()
        category: kategori produk sesi ini
        total_reviews: penyebut store_pct - proporsi ulasan, bukan jumlah mentah, supaya
            dapat dibandingkan lintas ukuran sampel yang berbeda (bagian 24.1 "Normalisasi")
        baseline: artifact precomputed; dimuat dari disk bila tidak diberikan

    Returns:
        Daftar BenchmarkRecord untuk aspek yang punya padanan di baseline. Aspek tanpa
        padanan DILEWATI, bukan dibandingkan terhadap nol - baseline yang tidak ada bukan
        berarti baseline bernilai nol.
    """
    data = baseline if baseline is not None else load_baseline()
    category_data = (data.get("categories") or {}).get(category.value)
    if not category_data or not total_reviews:
        return []

    sample_size = int(category_data.get("sample_size", 0))
    per_aspect = category_data.get("aspects", {})

    records: list[BenchmarkRecord] = []
    for aggregate in aggregates:
        entry = per_aspect.get(aggregate.aspect.value)
        if entry is None:
            continue

        store_pct = round(aggregate.negative_count / total_reviews, 4)
        baseline_pct = float(entry["pct_negative"])
        aspect_n = int(entry.get("sample_size", sample_size))

        # Sisi toko dinilai dengan alat yang sama seperti sisi baseline, dan itu justru
        # intinya: sebelum ini hanya satu sisi yang pernah ditimbang.
        preliminary = total_reviews < MIN_STORE_REVIEWS
        confidence = _weakest(
            _confidence_level(aspect_n),
            ConfidenceLevel.RENDAH if preliminary else _confidence_level(total_reviews),
        )

        records.append(
            BenchmarkRecord(
                category=category,
                aspect=aggregate.aspect,
                store_pct=store_pct,
                baseline_pct=round(baseline_pct, 4),
                baseline_sample_size=aspect_n,
                confidence_level=confidence,
                gap=round(store_pct - baseline_pct, 4),
                margin_of_error=_margin_of_error(baseline_pct, aspect_n),
                store_sample_size=total_reviews,
                store_margin_of_error=_margin_of_error(store_pct, total_reviews),
                preliminary=preliminary,
            )
        )

    return sorted(records, key=lambda r: r.gap, reverse=True)
