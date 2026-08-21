"""Test L2 - aturan agregasi klausa menjadi sentimen dokumen.

Dua hal diuji di sini, dan yang kedua lebih penting dari yang pertama:

1. Aturan asimetris berperilaku seperti yang dijanjikan.
2. Aturan itu SAMA dengan yang dipakai backend saat menghitung "ulasan berkeluhan". Selama
   keduanya berbeda, angka evaluasi yang kami laporkan mengukur sistem yang tidak kami kirim.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "ml" / "text"))

from aggregate import (  # noqa: E402
    NEGATIVE_CLAUSE_THRESHOLD,
    by_asymmetric,
    by_majority,
)

from app.schemas import Aspect, AspectPrediction, Sentiment, Severity, TextPrediction  # noqa: E402
from app.tools.segments import _negative_aspects  # noqa: E402


# ---------------------------------------------------------------- aturan lama


def test_mayoritas_menenggelamkan_satu_keluhan_di_antara_pujian():
    """Perilaku yang sedang diperbaiki, dikunci sebagai test supaya perbandingannya jelas.

    Temuan Fase 8 mengukurnya: 11 dari 128 ulasan negatif yang terlewat pada PRDECT-ID sudah
    punya klausa negatif meyakinkan, dan kalah di sini.
    """
    assert by_majority(["positif", "positif", "negatif"]) == "positif"


def test_mayoritas_mengabaikan_netral_saat_ada_yang_berpendapat():
    assert by_majority(["netral", "netral", "negatif"]) == "negatif"


def test_dokumen_tanpa_klausa_dianggap_netral():
    assert by_majority([]) == "netral"
    assert by_asymmetric([]) == "netral"


# ---------------------------------------------------------------- aturan asimetris


def test_satu_klausa_negatif_yakin_menegatifkan_dokumen():
    """Bagi produk yang tugasnya MENEMUKAN keluhan, ulasan berkeluhan tetap ulasan berkeluhan
    berapa pun jumlah pujian di sekitarnya."""
    labels = ["positif", "positif", "negatif"]
    probs = [0.02, 0.03, 0.91]
    assert by_asymmetric(labels, probs) == "negatif"


def test_klausa_negatif_yang_tidak_yakin_tidak_menegatifkan():
    """Aturannya berhenti menenggelamkan klausa yang modelnya sudah yakin - ia tidak
    menyelamatkan klausa yang modelnya sendiri ragu. Tanpa batas ini, aturan asimetris berubah
    menjadi mesin false positive."""
    labels = ["positif", "positif", "positif"]
    probs = [0.02, 0.03, 0.31]
    assert by_asymmetric(labels, probs) == "positif"


def test_ambang_diperiksa_tepat_di_batasnya():
    t = NEGATIVE_CLAUSE_THRESHOLD
    assert by_asymmetric(["positif"], [t]) == "negatif"
    assert by_asymmetric(["positif"], [t - 0.001]) == "positif"


def test_asimetri_hanya_berlaku_untuk_sisi_negatif():
    """Satu klausa positif TIDAK mempositifkan dokumen yang mayoritas klausanya mengeluh.
    Keluhan yang terlewat dan pujian yang terlewat tidak sepadan biayanya."""
    labels = ["negatif", "negatif", "positif"]
    probs = [0.88, 0.79, 0.03]
    assert by_asymmetric(labels, probs) == "negatif"

    labels = ["netral", "netral", "positif"]
    probs = [0.10, 0.08, 0.02]
    assert by_asymmetric(labels, probs) == "positif"


def test_tanpa_probabilitas_label_argmax_dipakai_apa_adanya():
    """Jalur leksikon tidak menghasilkan probabilitas; aturannya tetap harus berlaku."""
    assert by_asymmetric(["positif", "positif", "negatif"]) == "negatif"
    assert by_asymmetric(["positif", "positif", "netral"]) == "positif"


def test_dokumen_tanpa_klausa_negatif_tetap_diputuskan_mayoritas():
    """Yang berubah hanya sisi negatifnya. Sisanya sengaja tidak disentuh supaya perubahan
    ini punya satu sebab yang dapat ditunjuk kalau angkanya bergerak."""
    for labels in (["positif", "positif", "netral"], ["netral", "netral", "positif"]):
        assert by_asymmetric(labels, [0.01] * 3) == by_majority(labels)


# ---------------------------------------------------------------- sejalan dengan backend


def _pred(sentiments: list[Sentiment]) -> TextPrediction:
    return TextPrediction(
        review_id="r1",
        predictions=[
            AspectPrediction(
                aspect=Aspect.KUALITAS_PRODUK, sentiment=s, severity=Severity.SEDANG,
                confidence=0.8, source_sentence=f"klausa {i}",
            )
            for i, s in enumerate(sentiments)
        ],
        model_version="uji",
    )


def test_aturan_evaluasi_sama_dengan_aturan_backend():
    """Ini alasan sebenarnya berkas ini ada.

    Backend menghitung ulasan berkeluhan lewat `_negative_aspects()`: satu klausa negatif
    ber-aspek sudah cukup. Selama skrip evaluasi memakai suara terbanyak, macro-F1 yang kami
    laporkan menggambarkan sistem yang tidak pernah dikirim ke pengguna.
    """
    kasus = [
        [Sentiment.POSITIF, Sentiment.POSITIF, Sentiment.NEGATIF],
        [Sentiment.NEGATIF, Sentiment.POSITIF],
        [Sentiment.POSITIF, Sentiment.NETRAL],
        [Sentiment.NETRAL, Sentiment.NETRAL],
    ]
    for sentiments in kasus:
        backend_bilang_berkeluhan = bool(_negative_aspects(_pred(sentiments)))
        aturan_evaluasi = by_asymmetric([s.value for s in sentiments])
        assert backend_bilang_berkeluhan == (aturan_evaluasi == "negatif"), sentiments


def test_aturan_lama_terbukti_menyimpang_dari_backend():
    """Kontra-bukti untuk test di atas: dengan aturan lama, keduanya memang berbeda."""
    sentiments = [Sentiment.POSITIF, Sentiment.POSITIF, Sentiment.NEGATIF]
    assert bool(_negative_aspects(_pred(sentiments))) is True
    assert by_majority([s.value for s in sentiments]) == "positif"
