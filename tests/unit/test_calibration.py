"""Test L1 - temperature scaling.

Kalibrasi diuji pada logit sintetis, bukan pada checkpoint. Itu bukan kompromi: sifat yang
harus dijamin fitur ini seluruhnya sifat MATEMATIS - keputusan model tidak berubah, ECE turun
pada model yang terlalu percaya diri, suhu yang ditemukan deterministik - dan sifat matematis
diuji paling tajam pada data yang distribusinya kita kendalikan sendiri. Kualitas kalibrasi
pada model sungguhan diukur `ml/text/calibrate.py` dan dilaporkan di MODEL_CARD.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "ml" / "text"))

from calibration import (  # noqa: E402
    calibration_report,
    expected_calibration_error,
    fit_temperature,
    negative_log_likelihood,
    softmax,
)


def _terlalu_yakin(n: int = 300, akurasi: float = 0.7, ketajaman: float = 6.0):
    """Logit dari model yang benar ~70% waktu tetapi selalu berteriak yakin.

    Inilah bentuk kegagalan yang sedang diperbaiki, dan bentuk yang benar-benar dimiliki model
    ini: temuan Fase 8 mencatat 113 dari 128 negatif yang terlewat diprediksi dengan
    P(negatif) di bawah 0,10 - yakin, dan salah.
    """
    logits, labels = [], []
    for i in range(n):
        benar = i % 10 < akurasi * 10
        tebakan = 0
        label = 0 if benar else 1
        row = [0.0, 0.0, 0.0]
        row[tebakan] = ketajaman
        logits.append(row)
        labels.append(label)
    return logits, labels


# ---------------------------------------------------------------- softmax


def test_softmax_berjumlah_satu():
    p = softmax([2.0, 1.0, -3.0])
    assert sum(p) == pytest.approx(1.0)


def test_softmax_tahan_logit_besar():
    """Tanpa pengurangan maksimum, exp(800) meledak menjadi inf lalu nan."""
    p = softmax([800.0, 799.0, 0.0])
    assert sum(p) == pytest.approx(1.0)
    assert all(math.isfinite(x) for x in p)


def test_suhu_tinggi_meratakan_suhu_rendah_menajamkan():
    tajam = softmax([3.0, 0.0, 0.0], temperature=0.5)
    datar = softmax([3.0, 0.0, 0.0], temperature=5.0)
    assert max(tajam) > max(datar)


def test_suhu_nol_atau_negatif_ditolak():
    for t in (0.0, -1.0):
        with pytest.raises(ValueError):
            softmax([1.0, 0.0], temperature=t)


# ---------------------------------------------------------------- sifat inti


def test_suhu_tidak_pernah_mengubah_keputusan_model():
    """Sifat yang membuat fitur ini boleh dipasang tanpa evaluasi ulang.

    Membagi dengan skalar positif mempertahankan urutan, jadi argmax tidak bergeser - artinya
    akurasi, F1, dan urutan Action Card tetap sama persis. Diuji karena konsekuensi matematis
    tetap bisa gagal oleh bug, dan kalau ia gagal seluruh angka evaluasi berhenti berlaku.
    """
    logits = [[2.0, 1.0, -1.0], [-3.0, 0.5, 0.4], [0.1, 0.2, 0.15]]
    for t in (0.2, 0.9, 1.0, 2.5, 8.0):
        for row in logits:
            asli = row.index(max(row))
            setelah = softmax(row, t)
            assert setelah.index(max(setelah)) == asli


def test_kalibrasi_menurunkan_ece_pada_model_terlalu_yakin():
    logits, labels = _terlalu_yakin()
    t = fit_temperature(logits, labels)
    assert t > 1.0, "model terlalu yakin butuh suhu > 1 untuk diredakan"
    assert expected_calibration_error(logits, labels, t) < expected_calibration_error(
        logits, labels, 1.0
    )


def test_model_yang_sudah_terkalibrasi_tidak_dirusak():
    """Suhu yang ditemukan mendekati 1 - kalibrasi tidak menggeser yang sudah benar.

    Logitnya dihitung mundur dari keyakinan yang diinginkan, bukan dikarang: untuk tiga kelas
    dengan dua logit nol, P(kelas 0) = e^a / (e^a + 2), jadi a = ln(2p / (1 - p)).
    """
    p = 0.73
    a = math.log(2 * p / (1 - p))
    logits = [[a, 0.0, 0.0] for _ in range(300)]
    labels = [0 if i % 100 < 73 else 1 for i in range(300)]

    assert max(softmax(logits[0])) == pytest.approx(p, abs=1e-6)
    assert expected_calibration_error(logits, labels, 1.0) == pytest.approx(0.0, abs=0.01)

    t = fit_temperature(logits, labels)
    assert 0.9 < t < 1.1, t


def test_suhu_deterministik():
    """Angka keyakinan di layar tidak boleh berbeda antar-build tanpa model berubah."""
    logits, labels = _terlalu_yakin()
    assert fit_temperature(logits, labels) == fit_temperature(logits, labels)


def test_nll_minimum_berada_di_suhu_yang_ditemukan():
    logits, labels = _terlalu_yakin()
    t = fit_temperature(logits, labels)
    di_titik = negative_log_likelihood(logits, labels, t)
    for lain in (t * 0.5, t * 0.8, t * 1.25, t * 2.0):
        assert di_titik <= negative_log_likelihood(logits, labels, lain) + 1e-9


# ---------------------------------------------------------------- ECE


def test_ece_nol_saat_keyakinan_sama_dengan_akurasi():
    """Model yang selalu bilang 100% dan selalu benar memang terkalibrasi sempurna."""
    logits = [[50.0, 0.0, 0.0]] * 50
    labels = [0] * 50
    assert expected_calibration_error(logits, labels, 1.0) == pytest.approx(0.0, abs=1e-6)


def test_ece_besar_saat_yakin_tetapi_selalu_salah():
    logits = [[50.0, 0.0, 0.0]] * 50
    labels = [1] * 50
    assert expected_calibration_error(logits, labels, 1.0) > 0.9


def test_keyakinan_penuh_masuk_bin_terakhir_bukan_di_luar_rentang():
    """`int(1.0 * bins)` bernilai `bins` - satu di luar larik. Tanpa penjepitan, satu contoh
    dengan keyakinan tepat 1,0 melempar IndexError."""
    logits = [[1000.0, 0.0]]
    labels = [0]
    assert expected_calibration_error(logits, labels, 1.0) == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------- laporan


def test_laporan_memeriksa_bahwa_keputusan_tidak_berubah():
    logits, labels = _terlalu_yakin()
    t = fit_temperature(logits, labels)
    laporan = calibration_report(logits, labels, t)
    assert laporan["keputusan_tidak_berubah"] is True
    assert laporan["akurasi_sebelum"] == laporan["akurasi_sesudah"]
    assert laporan["ece_sesudah"] < laporan["ece_sebelum"]
    assert laporan["n"] == len(logits)


def test_data_kosong_tidak_error():
    assert fit_temperature([], []) == 1.0
    assert expected_calibration_error([], [], 1.0) == 0.0
    assert negative_log_likelihood([], [], 1.0) == 0.0
