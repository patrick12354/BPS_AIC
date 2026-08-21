"""Test S2 - jejak perhitungan Action Card ("Mode Juri").

Satu hal yang diuji berulang kali di berkas ini: jejaknya harus menghasilkan ANGKA YANG SAMA
dengan yang dibaca pengguna di kartu. Jejak yang meleset dari kartunya lebih buruk daripada
tidak ada jejak sama sekali - ia mengubah fitur transparansi menjadi bukti bahwa sistemnya
tidak konsisten.
"""

from __future__ import annotations

import pytest

from app.schemas import (
    AspectPrediction,
    Aspect,
    AspectAggregate,
    Sentiment,
    Severity,
    TextPrediction,
    Trend,
)
from app.tools.priority import DEFAULT_W_BENCHMARK, DEFAULT_W_RECENCY, calculate_priority_score
from app.tools.trace import MAX_TRACE_CLAUSES, build_action_trace


def _agg(negative=6, positive=2, trend=Trend.STABIL) -> AspectAggregate:
    total = negative + positive
    return AspectAggregate(
        aspect=Aspect.PENGIRIMAN, total_mentions=total, negative_count=negative,
        positive_count=positive, neutral_count=0, pct_negative=negative / total,
        trend=trend, avg_confidence=0.8, dominant_severity=Severity.SEDANG,
    )


def _pred(review_id: str, sentiment: Sentiment, clause: str) -> TextPrediction:
    return TextPrediction(
        review_id=review_id,
        predictions=[
            AspectPrediction(
                aspect=Aspect.PENGIRIMAN, sentiment=sentiment, severity=Severity.SEDANG,
                confidence=0.8, source_sentence=clause,
            )
        ],
        model_version="uji",
    )


def _trace(aggregate=None, predictions=None, total_reviews=40):
    aggregate = aggregate or _agg()
    priority = calculate_priority_score(aggregate, total_reviews)
    return build_action_trace(
        action_id="ACT-001",
        aspect=Aspect.PENGIRIMAN,
        aggregate=aggregate,
        priority=priority,
        predictions=predictions if predictions is not None else [
            _pred("r1", Sentiment.NEGATIF, "paketnya telat seminggu"),
            _pred("r2", Sentiment.POSITIF, "pengiriman cepat"),
        ],
        total_reviews=total_reviews,
    ), priority


# ---------------------------------------------------------------- konsistensi dengan kartu


def test_skor_pada_jejak_sama_dengan_skor_kartunya():
    trace, priority = _trace()
    assert trace.score == priority.score


def test_komponen_jejak_dapat_dihitung_ulang_menjadi_skornya():
    """Inti fiturnya: pembaca skeptis menghitung sendiri dan sampai ke angka yang sama."""
    trace, priority = _trace(aggregate=_agg(trend=Trend.MENINGKAT))
    nilai = {f.key: f.value for f in trace.factors}
    core = nilai["frequency_norm"] * nilai["severity_norm"] * nilai["confidence_norm"]
    modifier = (
        1.0
        + DEFAULT_W_RECENCY * nilai["recency_norm"]
        + DEFAULT_W_BENCHMARK * nilai["benchmark_gap_norm"]
    )
    assert core * modifier * 100.0 == pytest.approx(priority.score, abs=0.01)
    assert trace.core == pytest.approx(core, abs=1e-6)
    assert trace.modifier == pytest.approx(modifier, abs=1e-6)


def test_kelima_komponen_rumus_dilaporkan_seluruhnya():
    """Satu faktor yang hilang dari daftar berarti pembaca tidak dapat menghitung ulang."""
    trace, _ = _trace()
    assert {f.key for f in trace.factors} == {
        "frequency_norm", "severity_norm", "confidence_norm",
        "recency_norm", "benchmark_gap_norm",
    }


def test_peran_pengali_inti_dan_modifier_dibedakan():
    """Tanpa pembedaan ini, tren terbaca seolah sederajat dengan frekuensi."""
    trace, _ = _trace()
    peran = {f.key: f.role for f in trace.factors}
    assert peran["frequency_norm"] == "pengali inti"
    assert peran["recency_norm"] == "modifier"


def test_tiap_komponen_membawa_aritmetikanya_bukan_hanya_angka():
    trace, _ = _trace()
    frekuensi = next(f for f in trace.factors if f.key == "frequency_norm")
    assert "6" in frekuensi.explanation and "40" in frekuensi.explanation


def test_keyakinan_model_mengaku_belum_terkalibrasi():
    """Angka ini placeholder; jejak yang menampilkannya tanpa keterangan justru menyesatkan."""
    trace, _ = _trace()
    keyakinan = next(f for f in trace.factors if f.key == "confidence_norm")
    assert "terkalibrasi" in keyakinan.explanation


# ---------------------------------------------------------------- klausa


def test_klausa_berkeluhan_didahulukan():
    trace, _ = _trace(predictions=[
        _pred("r1", Sentiment.POSITIF, "pengiriman cepat"),
        _pred("r2", Sentiment.NEGATIF, "paketnya telat seminggu"),
    ])
    assert trace.clauses[0].sentiment is Sentiment.NEGATIF


def test_jumlah_klausa_sebenarnya_tetap_dilaporkan_saat_dipotong():
    """Pemotongan tanpa angka totalnya terbaca sebagai "cuma segini datanya"."""
    predictions = [
        _pred(f"r{i}", Sentiment.NEGATIF, f"keluhan ke-{i}")
        for i in range(MAX_TRACE_CLAUSES + 5)
    ]
    trace, _ = _trace(predictions=predictions)
    assert len(trace.clauses) == MAX_TRACE_CLAUSES
    assert trace.clauses_total == MAX_TRACE_CLAUSES + 5
    assert any(str(MAX_TRACE_CLAUSES + 5) in n for n in trace.notes)


def test_aspek_lain_tidak_ikut_masuk_jejak():
    lain = TextPrediction(
        review_id="r9",
        predictions=[
            AspectPrediction(
                aspect=Aspect.KEMASAN, sentiment=Sentiment.NEGATIF, severity=Severity.SEDANG,
                confidence=0.8, source_sentence="dusnya penyok",
            )
        ],
        model_version="uji",
    )
    trace, _ = _trace(predictions=[_pred("r1", Sentiment.NEGATIF, "telat"), lain])
    assert all(c.aspect is Aspect.PENGIRIMAN for c in trace.clauses)
    assert trace.clauses_total == 1


# ---------------------------------------------------------------- catatan


def test_pembatasan_urgensi_dijelaskan_saat_berlaku():
    trace, _ = _trace(total_reviews=8)
    assert any("Urgensi dibatasi" in n for n in trace.notes)


def test_catatan_tidak_muncul_saat_tidak_berlaku():
    """Penafian yang tampil di setiap jejak berhenti dibaca setelah jejak kedua."""
    trace, _ = _trace(total_reviews=200)
    assert trace.notes == []
