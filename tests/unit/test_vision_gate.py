"""Test L3 - gerbang visual sebagai kode, bukan sebagai catatan.

Ini berkas test yang paling penting dari seluruh jalur visual, dan alasannya bukan teknis.

Gerbang go/no-go modul visual sudah diputuskan sejak Fase 3: zero-shot 45% tidak melampaui
pembanding sepele 61%, vonisnya NO-GO. Vonis itu ditulis di LIMITATIONS.md, disebut di README,
dan dijalankan oleh **ingatan orang**. Tidak ada satu baris kode pun yang mencegah siapa pun
menyalakan model yang belum lolos - dan pada malam sebelum demo, ingatan adalah hal pertama
yang gagal.

Test di sini mengunci syarat itu ke dalam kode: artefak yang membawa vonis NO-GO membuat
adapter menolak aktif, dan alasannya terbaca dari luar.

Probe sintetis dipakai, bukan yang sungguhan. Bukan kompromi: yang diuji adalah PERILAKU
GERBANG, dan perilaku itu harus berlaku untuk artefak apa pun - termasuk artefak yang belum
pernah ada karena fotonya belum dilabeli.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.adapters.vision_model import GERBANG_LOLOS, VisionModelAdapter


def _artefak(tmp_path, keputusan="GO", min_confidence=0.6):
    path = tmp_path / "probe.npz"
    np.savez(
        path,
        coef=np.zeros((1, 512), dtype=np.float32),
        intercept=np.zeros(1, dtype=np.float32),
        classes=np.array(["normal", "perlu_diperiksa"]),
        meta=json.dumps(
            {
                "encoder": "openai/clip-vit-base-patch32",
                "perumusan": "biner_perlu_diperiksa",
                "keputusan": keputusan,
                "alasan": "alasan uji",
                "min_confidence": min_confidence,
                "selective_accuracy": 0.82,
                "coverage": 0.55,
                "n_berlabel": 150,
            },
            ensure_ascii=False,
        ),
    )
    return path


# ---------------------------------------------------------------- gerbang


def test_artefak_no_go_membuat_adapter_menolak_aktif():
    """Inti seluruh berkas ini."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        adapter = VisionModelAdapter(probe_path=_artefak(Path(d), keputusan="NO-GO"))
        assert adapter.active is False
        assert "NO-GO" in adapter.inactive_reason
        assert adapter.classify([("img1", "r1", b"")]) == []


def test_artefak_go_menyalakan_adapter():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        adapter = VisionModelAdapter(probe_path=_artefak(Path(d), keputusan="GO"))
        assert adapter.active is True
        assert adapter.inactive_reason is None
        assert adapter.min_confidence == pytest.approx(0.6)


def test_conditional_go_ikut_lolos():
    """Konsekuensinya tertulis di `putuskan()`: boleh tampil sebagai fitur pendukung yang
    menyertakan keterbatasannya, tidak boleh disebut kapabilitas terbukti."""
    assert "CONDITIONAL GO" in GERBANG_LOLOS


def test_vonis_asing_diperlakukan_sebagai_tidak_lolos():
    """Daftar putih, bukan daftar hitam. Vonis baru yang belum dikenal harus MEMATIKAN jalur
    ini, bukan diam-diam menghidupkannya."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        adapter = VisionModelAdapter(probe_path=_artefak(Path(d), keputusan="MUNGKIN"))
        assert adapter.active is False


def test_artefak_tidak_ada_disebut_alasannya_bukan_didiamkan():
    """Keadaan normal hari ini - fotonya belum dilabeli. Ia harus terbaca dari /readiness,
    bukan hanya diketahui orang yang membaca kode."""
    from pathlib import Path

    adapter = VisionModelAdapter(probe_path=Path("__probe-tidak-ada__.npz"))
    assert adapter.active is False
    assert "tidak ada" in adapter.inactive_reason
    assert "linear_probe.py" in adapter.inactive_reason


def test_artefak_rusak_tidak_menjatuhkan_sistem():
    """Kegagalan jalur visual menurunkan alur ke teks-saja, tidak pernah menghentikan analisis."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        rusak = Path(d) / "probe.npz"
        rusak.write_bytes(b"bukan npz sama sekali")
        adapter = VisionModelAdapter(probe_path=rusak)
        assert adapter.active is False
        assert adapter.inactive_reason
        assert adapter.classify([("img1", "r1", b"")]) == []


# ---------------------------------------------------------------- abstention


def test_ambang_abstention_datang_dari_artefak_bukan_dari_nilai_bawaan():
    """Produksi harus memakai ambang yang SAMA dengan yang angkanya dilaporkan - ambang itu
    dikalibrasi di dalam fold latih saat evaluasi."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        adapter = VisionModelAdapter(probe_path=_artefak(Path(d), min_confidence=0.83))
        assert adapter.min_confidence == pytest.approx(0.83)


def test_probabilitas_biner_dipulihkan_menjadi_dua_kolom():
    """Regresi logistik biner sklearn menyimpan SATU baris koefisien. Tanpa pemulihan ini,
    softmax berjalan atas satu kolom dan setiap gambar keluar dengan keyakinan 100% - abstention
    berhenti bekerja sepenuhnya, dan justru itu penjaga utama fitur ini."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        adapter = VisionModelAdapter(probe_path=_artefak(Path(d)))
        fitur = np.zeros((3, 512), dtype=np.float32)
        probs = adapter._probabilitas(fitur)
        assert probs.shape == (3, 2)
        assert probs.sum(axis=1) == pytest.approx(np.ones(3))
        # Koefisien nol -> tidak ada informasi -> 50/50, dan 0,5 di bawah ambang 0,6 berarti
        # seluruhnya abstain. Itu perilaku yang benar untuk model yang tidak tahu apa-apa.
        assert probs.max() < adapter.min_confidence
