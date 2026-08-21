"""Test BEN-01 - perbandingan terhadap baseline kategori (blueprint bagian 24).

Fokus berkas ini satu hal: perbandingan butuh sampel di KEDUA sisi. Sebelum temuan audit ini,
keyakinan sebuah baris benchmark hanya dinilai dari besar sampel baseline, sehingga toko lima
ulasan tampil "keyakinan tinggi" berdampingan dengan kolom selisih yang terbaca sebagai temuan.
"""

from __future__ import annotations

import pytest

from app.schemas import Aspect, AspectAggregate, Category, ConfidenceLevel, Severity, Trend
from app.tools.benchmark import MIN_STORE_REVIEWS, compare_category_baseline

BASELINE = {
    "categories": {
        "fashion": {
            "sample_size": 40000,
            "aspects": {
                "ukuran_varian": {"pct_negative": 0.12, "sample_size": 40000},
                "pengiriman": {"pct_negative": 0.08, "sample_size": 40000},
            },
        }
    }
}


def _agg(aspect=Aspect.UKURAN_VARIAN, negative=2, positive=1) -> AspectAggregate:
    total = negative + positive
    return AspectAggregate(
        aspect=aspect, total_mentions=total, negative_count=negative, positive_count=positive,
        neutral_count=0, pct_negative=negative / total, trend=Trend.STABIL,
        avg_confidence=0.8, dominant_severity=Severity.SEDANG,
    )


def _records(total_reviews: int):
    return compare_category_baseline(
        [_agg()], Category.FASHION, total_reviews, baseline=BASELINE
    )


def test_toko_bersampel_kecil_tidak_lagi_disebut_keyakinan_tinggi():
    """Temuan audit T4: baseline 40.000 ulasan tidak membuat toko 5 ulasan jadi meyakinkan."""
    record = _records(5)[0]
    assert record.confidence_level is ConfidenceLevel.RENDAH
    assert record.preliminary is True


def test_margin_sisi_toko_ikut_dilaporkan():
    """Angka inilah yang membuat pembaca paham kenapa selisihnya ditahan."""
    record = _records(5)[0]
    # p = 2/5 = 0,4 -> 1,96 * sqrt(0,24/5) ~ 0,429
    assert record.store_margin_of_error == pytest.approx(0.429, abs=0.005)
    assert record.store_sample_size == 5


def test_di_atas_ambang_perbandingan_kembali_penuh():
    # 600 ulasan, bukan 200: ambang "tinggi" berlaku sama di kedua sisi (500 ulasan).
    record = _records(600)[0]
    assert record.preliminary is False
    assert record.confidence_level is ConfidenceLevel.TINGGI


def test_ambang_diperiksa_tepat_di_batasnya():
    assert _records(MIN_STORE_REVIEWS - 1)[0].preliminary is True
    assert _records(MIN_STORE_REVIEWS)[0].preliminary is False


def test_keyakinan_mengikuti_sisi_terlemah_bukan_terkuat():
    """Baseline besar + toko sedang = keyakinan sedang, bukan tinggi."""
    record = _records(120)[0]
    assert record.preliminary is False
    assert record.confidence_level is ConfidenceLevel.SEDANG


def test_angka_toko_dan_baseline_tetap_diberikan_apa_adanya():
    """Yang ditahan hanya KLAIM perbandingannya - datanya sendiri tidak disembunyikan."""
    record = _records(5)[0]
    assert record.store_pct == pytest.approx(0.4)
    assert record.baseline_pct == pytest.approx(0.12)
    assert record.gap == pytest.approx(0.28)
