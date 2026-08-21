"""Test L5 - arsip analisis dan perbandingan antar-periode tanpa database.

Dua hal yang harus dijamin berkas ini, dan keduanya bersifat mengikat:

1. **Arsip tidak pernah membawa teks ulasan.** Berkas ini berpindah lewat WhatsApp dan email,
   dan pemiliknya tidak akan membacanya sebelum meneruskan. Kebocoran satu kutipan di sini
   adalah kebocoran data pelanggan orang lain.
2. **Selisih yang tidak dapat dibedakan dari kebetulan tidak pernah disebut perubahan.** Angka
   ini akan dibaca sebagai "pergantian kurir saya berhasil", lalu menjadi keputusan bisnis.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.schemas import (
    AnalysisArchive,
    ArchiveAspect,
    Aspect,
    AspectAggregate,
    Category,
    Severity,
    Trend,
)
from app.tools.archive import (
    MIN_REVIEWS_FOR_COMPARISON,
    SCHEMA_VERSION,
    build_archive,
    compare_archives,
)


def _agg(aspect=Aspect.PENGIRIMAN, negative=6, positive=2) -> AspectAggregate:
    total = negative + positive
    return AspectAggregate(
        aspect=aspect, total_mentions=total, negative_count=negative, positive_count=positive,
        neutral_count=0, pct_negative=negative / total, trend=Trend.STABIL,
        avg_confidence=0.8, dominant_severity=Severity.SEDANG,
    )


def _archive(
    analysis_id="an_1", total=100, per_aspect=None, category=Category.FASHION,
    period_start=None, period_end=None,
) -> AnalysisArchive:
    per_aspect = per_aspect or {Aspect.PENGIRIMAN: 19}
    return AnalysisArchive(
        analysis_id=analysis_id,
        total_reviews=total,
        reviews_with_complaint=sum(per_aspect.values()),
        category=category,
        period_start=period_start,
        period_end=period_end,
        aspects=[
            ArchiveAspect(
                aspect=a, total_mentions=n + 5, negative_count=n, positive_count=5,
                pct_negative_of_reviews=round(n / total, 4),
            )
            for a, n in per_aspect.items()
        ],
    )


# ---------------------------------------------------------------- privasi


def test_arsip_tidak_membawa_satu_pun_kata_dari_ulasan():
    """Penjaga terpenting berkas ini. Diperiksa pada seluruh JSON, bukan per medan - medan
    baru yang ditambahkan kelak ikut tertangkap tanpa test-nya perlu diperbarui."""
    arsip = build_archive(
        analysis_id="an_1",
        aggregates=[_agg(), _agg(Aspect.KEMASAN, 3, 1)],
        total_reviews=40,
        reviews_with_complaint=9,
        category=Category.FASHION,
    )
    # `note` dikecualikan: ia kalimat yang kami tulis sendiri, dan ia memang MENYEBUT kata
    # "kutipan" untuk menjanjikan tidak ada kutipan di dalamnya.
    isi = arsip.model_dump_json(exclude={"note"})
    for bocor in ["paketnya", "telat", "SHP", "review_id", "quote", "kutipan", "source_sentence"]:
        assert bocor not in isi, bocor


def test_arsip_membawa_nomor_format():
    """Arsip berumur panjang di luar kendali kami; satu-satunya yang bisa dilakukan adalah
    memberinya nomor sekarang, sebelum ada yang beredar."""
    arsip = build_archive("an_1", [_agg()], 40, 6, Category.FASHION)
    assert arsip.schema_version == SCHEMA_VERSION


def test_penyebut_adalah_jumlah_ulasan_bukan_jumlah_sebutan():
    """Proporsi terhadap sebutan tidak dapat dibandingkan antar sesi - penyebutnya sendiri
    ikut berubah."""
    arsip = build_archive("an_1", [_agg(negative=6, positive=2)], total_reviews=50,
                          reviews_with_complaint=6, category=Category.FASHION)
    assert arsip.aspects[0].pct_negative_of_reviews == pytest.approx(6 / 50)


# ---------------------------------------------------------------- selisih


def test_perubahan_besar_pada_data_cukup_disebut_berarti():
    lama = _archive("an_1", 300, {Aspect.PENGIRIMAN: 57})   # 19%
    baru = _archive("an_2", 300, {Aspect.PENGIRIMAN: 24})   # 8%
    hasil = compare_archives(lama, baru)
    d = next(x for x in hasil.deltas if x.aspect is Aspect.PENGIRIMAN)
    assert d.significant is True
    assert d.direction == "membaik"
    assert d.delta_pct < 0
    assert "turun" in hasil.headline


def test_perubahan_besar_pada_data_tipis_tidak_disebut_berarti():
    """Persis contoh yang paling menggoda ditampilkan: 19% ke 8% terdengar meyakinkan sampai
    penyebutnya diperiksa."""
    lama = _archive("an_1", 21, {Aspect.PENGIRIMAN: 4})
    baru = _archive("an_2", 25, {Aspect.PENGIRIMAN: 2})
    hasil = compare_archives(lama, baru)
    d = next(x for x in hasil.deltas if x.aspect is Aspect.PENGIRIMAN)
    assert d.significant is False
    assert d.direction == "tetap"
    assert any("kurang dari" in w for w in hasil.warnings)


def test_margin_selisih_lebih_lebar_dari_margin_masing_masing_sisi():
    """Ragam selisih adalah jumlah kedua ragam. Memakai margin satu sisi akan membuat
    perubahan tampak berarti jauh lebih sering daripada yang sebenarnya."""
    import math

    lama = _archive("an_1", 200, {Aspect.PENGIRIMAN: 40})
    baru = _archive("an_2", 200, {Aspect.PENGIRIMAN: 30})
    d = compare_archives(lama, baru).deltas[0]
    satu_sisi = 1.96 * math.sqrt(0.2 * 0.8 / 200)
    assert d.margin_of_error > satu_sisi


def test_aspek_yang_hilang_atau_muncul_tetap_dilaporkan():
    """Justru perubahan paling menarik: keluhan yang muncul dari ketiadaan."""
    lama = _archive("an_1", 200, {Aspect.PENGIRIMAN: 40})
    baru = _archive("an_2", 200, {Aspect.KEMASAN: 30})
    hasil = compare_archives(lama, baru)
    aspek = {d.aspect for d in hasil.deltas}
    assert Aspect.PENGIRIMAN in aspek and Aspect.KEMASAN in aspek
    kemasan = next(d for d in hasil.deltas if d.aspect is Aspect.KEMASAN)
    assert kemasan.before_count == 0 and kemasan.after_count == 30


def test_tanpa_perubahan_berarti_kalimat_kepalanya_tetap_mengatakan_sesuatu():
    """"Belum terlihat efeknya" adalah temuan, bukan ketiadaan temuan."""
    lama = _archive("an_1", 300, {Aspect.PENGIRIMAN: 60})
    baru = _archive("an_2", 300, {Aspect.PENGIRIMAN: 62})
    hasil = compare_archives(lama, baru)
    assert all(not d.significant for d in hasil.deltas)
    assert "belum terlihat efeknya" in hasil.headline.lower()


def test_kalimat_kepala_memilih_perubahan_berarti_bukan_yang_terbesar():
    """Kalau tidak, kepala laporan justru jadi tempat derau paling mudah lolos."""
    lama = _archive("an_1", 400, {Aspect.PENGIRIMAN: 80, Aspect.KEASLIAN: 4})
    baru = _archive("an_2", 400, {Aspect.PENGIRIMAN: 40, Aspect.KEASLIAN: 12})
    hasil = compare_archives(lama, baru)
    assert "pengiriman" in hasil.headline


# ---------------------------------------------------------------- peringatan


def test_periode_tumpang_tindih_diperingatkan():
    """Ulasan yang sama terhitung dua kali meredam perubahannya, dan peredaman itu tidak
    terlihat di angka mana pun."""
    lama = _archive("an_1", 200, period_end=datetime(2026, 7, 20))
    baru = _archive("an_2", 200, period_start=datetime(2026, 7, 1))
    hasil = compare_archives(lama, baru)
    assert any("tumpang tindih" in w for w in hasil.warnings)


def test_kategori_berbeda_diperingatkan():
    lama = _archive("an_1", 200, category=Category.FASHION)
    baru = _archive("an_2", 200, category=Category.ELECTRONICS)
    assert any("Kategori berbeda" in w for w in compare_archives(lama, baru).warnings)


def test_arsip_dari_analisis_yang_sama_diperingatkan():
    arsip = _archive("an_sama", 200)
    hasil = compare_archives(arsip, arsip)
    assert any("sedang Anda buka" in w for w in hasil.warnings)
    assert all(d.delta_pct == 0 for d in hasil.deltas)


def test_format_arsip_asing_diperingatkan_bukan_ditolak_diam_diam():
    lama = _archive("an_1", 200)
    lama = lama.model_copy(update={"schema_version": "ulasin-archive-0"})
    hasil = compare_archives(lama, _archive("an_2", 200))
    assert any("format" in w for w in hasil.warnings)
    assert hasil.deltas, "tetap dibandingkan, hanya diberi peringatan"


def test_ambang_perbandingan_diperiksa_tepat_di_batasnya():
    n = MIN_REVIEWS_FOR_COMPARISON
    kurang = compare_archives(
        _archive("an_1", n - 1, {Aspect.PENGIRIMAN: 0}),
        _archive("an_2", 200, {Aspect.PENGIRIMAN: 60}),
    )
    assert all(not d.significant for d in kurang.deltas)

    cukup = compare_archives(
        _archive("an_1", 200, {Aspect.PENGIRIMAN: 0}),
        _archive("an_2", 200, {Aspect.PENGIRIMAN: 60}),
    )
    assert any(d.significant for d in cukup.deltas)
