"""Regresi untuk dua pengelompokan batch yang dipasang demi kecepatan.

Keduanya dipasang karena analisis 66 ulasan berjalan 24 detik, dan keduanya menyentuh jalur
yang menghasilkan angka yang dilihat pengguna. Yang harus dijaga bukan kecepatannya - itu
terukur di luar test - melainkan bahwa hasilnya TIDAK berubah:

1. `EmbeddingAdapter.encode` menyusun batch menurut panjang teks, lalu harus mengembalikan
   vektor pada urutan MASUKAN. Kalau urutannya tertukar, `EvidenceIndex.build` memasangkan
   vektor dengan ulasan yang salah - dan gejalanya bukan error, melainkan kutipan bukti yang
   tidak nyambung dengan kartunya. Itu justru jenis kerusakan yang paling sulit terlihat.

2. `TextModelAdapter.classify` menyatukan klausa seluruh ulasan menjadi satu daftar sebelum
   inferensi, lalu memetakannya balik lewat rentang indeks. Salah rentang berarti prediksi
   milik ulasan A menempel pada ulasan B.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.adapters.embedding import EmbeddingAdapter
from app.adapters.text_model import TextModelAdapter, _segment
from app.schemas import Category, ProcessedReview

# Panjangnya sengaja berselang-seling. Kalau daftarnya sudah urut panjang sejak awal,
# pengurutan di dalam `encode` tidak memindahkan apa pun dan test-nya lolos tanpa menguji apa-apa.
TEKS = [
    "ukurannya kekecilan padahal sudah pesan size L dan sudah cek panduan ukuran dulu",
    "bagus",
    "kemasan rusak saat diterima, kardusnya penyok parah dan isinya ikut lecet di beberapa sisi",
    "adem",
    "pengiriman sangat cepat sampai besoknya, packing rapi berlapis bubble wrap tebal sekali",
    "oke",
]


@pytest.fixture(scope="module")
def adapter():
    """Jalur fallback TF-IDF - deterministic, tanpa unduhan model.

    Cukup untuk yang diuji di sini: TF-IDF melewati jalur pengurutan yang sama? TIDAK - jalur
    pengurutan hanya ada pada cabang neural. Karena itu test vektor di bawah memakai model
    tiruan, dan adapter ini hanya dipakai untuk memastikan cabang fallback tetap hidup.
    """
    return EmbeddingAdapter(model_name="__tidak-ada__")


def test_fallback_tfidf_tetap_mengembalikan_satu_vektor_per_teks(adapter):
    vektor = adapter.encode(TEKS)
    assert vektor.shape[0] == len(TEKS)
    # Vektor ternormalisasi - syarat cosine similarity di EvidenceIndex.
    assert np.allclose(np.linalg.norm(vektor, axis=1), 1.0, atol=1e-5)


class _TorchPalsu:
    """Cukup sebesar yang disentuh `encode`: `no_grad` dan `nn.functional.normalize`."""

    class _NoGrad:
        def __enter__(self):
            return None

        def __exit__(self, *_):
            return False

    def no_grad(self):
        return self._NoGrad()

    class nn:  # noqa: N801 - meniru tata nama torch
        class functional:
            @staticmethod
            def normalize(x, p=2, dim=1):
                data = x.data
                return _Tensor(data / np.clip(np.linalg.norm(data, axis=dim, keepdims=True), 1e-9, None))


class _Tensor:
    """Pembungkus array yang menyediakan metode tensor yang dipakai `encode`."""

    def __init__(self, data):
        self.data = np.asarray(data, dtype="float32")

    def unsqueeze(self, _dim):
        return _Tensor(self.data[..., None])

    def float(self):
        return self

    def sum(self, _dim):
        return _Tensor(self.data.sum(axis=1))

    def clamp(self, min=None):  # noqa: A002 - nama argumen mengikuti torch
        return _Tensor(np.clip(self.data, min, None))

    def cpu(self):
        return self

    def numpy(self):
        return self.data

    def __mul__(self, other):
        return _Tensor(self.data * other.data)

    def __truediv__(self, other):
        return _Tensor(self.data / other.data)


class _Keluaran:
    def __init__(self, hidden):
        self.last_hidden_state = _Tensor(hidden)


class _ModelPalsu:
    """Model yang keluarannya menjadi TANDA PENGENAL panjang teksnya.

    Vektor sebelum normalisasi bernilai `(n, 1)` dengan `n` panjang teks. Dua sumbu, bukan
    satu: kalau keduanya bernilai sama, normalisasi L2 memampatkan semuanya menjadi vektor
    yang identik dan test urutan tidak lagi menguji apa pun. Dengan `(n, 1)`, arah vektor
    berbeda untuk setiap panjang, sehingga posisi keluaran dapat dilacak balik ke teksnya.
    """

    def __init__(self):
        self.ukuran_batch_terpakai: list[int] = []
        self.panjang_per_batch: list[list[int]] = []

    def __call__(self, **enc):
        panjang = enc["__panjang__"]
        self.ukuran_batch_terpakai.append(len(panjang))
        self.panjang_per_batch.append(list(panjang))
        maks = max(panjang)
        hidden = np.zeros((len(panjang), maks, 2), dtype="float32")
        for i, n in enumerate(panjang):
            hidden[i, :n, 0] = float(n)
            hidden[i, :n, 1] = 1.0
        return _Keluaran(hidden)


def _panjang_dari_vektor(v):
    """Balikan dari model tiruan: dari vektor ternormalisasi kembali ke panjang teksnya."""
    return round(float(v[0] / v[1]))


class _TokenizerPalsu:
    def __call__(self, batch, truncation=None, max_length=None, padding=None, return_tensors=None):
        panjang = [len(t) for t in batch]
        maks = max(panjang)
        mask = np.zeros((len(batch), maks), dtype="float32")
        for i, n in enumerate(panjang):
            mask[i, :n] = 1.0
        return _EncPalsu({"attention_mask": _Tensor(mask), "__panjang__": panjang})


class _EncPalsu(dict):
    def to(self, _device):
        return self


def _adapter_tiruan():
    a = EmbeddingAdapter.__new__(EmbeddingAdapter)
    a.model = _ModelPalsu()
    a.tokenizer = _TokenizerPalsu()
    a._torch = _TorchPalsu()
    a._device = "cpu"
    a.batch_size = 2  # kecil, supaya benar-benar ada beberapa batch untuk ditukar urutannya
    a.max_length = 256
    a.model_name = "palsu"
    a.mode = "full"
    return a


def test_urutan_vektor_mengikuti_urutan_masukan_bukan_urutan_panjang():
    a = _adapter_tiruan()
    vektor = a.encode(TEKS)

    assert vektor.shape[0] == len(TEKS)
    # Inti test-nya: vektor pada posisi ke-i harus berasal dari TEKS[i], bukan dari teks
    # ke-i menurut urutan panjang.
    assert [_panjang_dari_vektor(v) for v in vektor] == [len(t) for t in TEKS]

    # Sekali lagi dengan urutan masukan dibalik. Kalau pengembalian urutan salah arah, test
    # pertama masih bisa lolos secara kebetulan pada susunan tertentu; yang ini tidak.
    terbalik = a.encode(list(reversed(TEKS)))
    assert np.allclose(terbalik, vektor[::-1], atol=1e-5)


def test_batch_dikelompokkan_menurut_panjang_teks():
    a = _adapter_tiruan()
    model = a.model
    a.encode(TEKS)

    # batch_size 2 atas 6 teks = 3 batch.
    assert model.ukuran_batch_terpakai == [2, 2, 2]
    # Dan isinya harus urut panjang - itulah yang membuat padding-nya sedikit. Tanpa
    # pengurutan, batch pertama akan memuat teks 79 dan 5 karakter sekaligus.
    datar = [n for batch in model.panjang_per_batch for n in batch]
    assert datar == sorted(datar)


# ------------------------------------------------------------------------------------------
# TextModelAdapter.classify - pemetaan balik klausa ke ulasan asalnya
# ------------------------------------------------------------------------------------------


def _ulasan(review_id: str, teks: str) -> ProcessedReview:
    return ProcessedReview(
        review_id=review_id,
        clean_text=teks,
        pii_redacted=False,
        rating=None,
        category=Category.FASHION,
        has_image=False,
    )


def test_prediksi_tetap_menempel_pada_ulasan_asalnya():
    """Jalur leksikon dipakai supaya test tidak menuntut checkpoint neural.

    Yang diuji pemetaan indeksnya, dan pemetaan itu sama untuk kedua jalur: `classify`
    meratakan klausa seluruh ulasan menjadi satu daftar, lalu memotongnya kembali dengan
    rentang yang dicatat saat perataan.
    """
    adapter = TextModelAdapter(checkpoint=__import__("pathlib").Path("__tidak-ada__"))
    assert adapter.model is None, "test ini memang menargetkan jalur leksikon"

    ulasan = [
        _ulasan("r1", "ukurannya kekecilan padahal pesan L"),
        _ulasan("r2", ""),  # tanpa klausa - rentangnya kosong, dan itu justru kasus rawannya
        _ulasan("r3", "pengiriman cepat. kemasan rusak parah"),
        _ulasan("r4", "harganya kemahalan"),
    ]

    hasil = adapter.classify(ulasan)
    assert [p.review_id for p in hasil] == ["r1", "r2", "r3", "r4"]
    assert hasil[1].predictions == [], "ulasan tanpa klausa tidak boleh kebagian prediksi tetangga"

    # Setiap `source_sentence` harus ada di antara klausa ulasannya SENDIRI. Pembandingnya
    # `_segment`, bukan `clean_text` mentah: segmentasi ikut menormalkan teks ("ukurannya" ->
    # "ukuran"), jadi klausa yang benar pun bukan potongan harfiah teks aslinya.
    for prediksi, asal in zip(hasil, ulasan):
        klausa_sendiri = set(_segment(asal.clean_text))
        for item in prediksi.predictions:
            assert item.source_sentence in klausa_sendiri, (
                f"{prediksi.review_id} memuat klausa milik ulasan lain: {item.source_sentence!r}"
            )


def test_classify_pada_daftar_kosong_tidak_meledak():
    adapter = TextModelAdapter(checkpoint=__import__("pathlib").Path("__tidak-ada__"))
    assert adapter.classify([]) == []


# ---------------------------------------------------------------- kalibrasi (L1)
#
# Sisi checkpoint dari kalibrasi diuji `tests/unit/test_calibration.py` pada logit sintetis.
# Yang diuji di sini kabelnya: bahwa adapter tidak pernah MENGAKU terkalibrasi saat ia bukan.


def test_jalur_leksikon_tidak_pernah_mengaku_terkalibrasi():
    """Ini penjaga yang menentukan angka keyakinan boleh tampil atau tidak di layar.

    Leksikon tidak menghasilkan probabilitas sama sekali - ia menghitung selisih jumlah kata.
    Kalau `calibrated` bocor menjadi True di jalur ini, angka 0,60 yang tidak berarti apa pun
    akan tampil di laporan sebagai "keyakinan model, terkalibrasi".
    """
    from pathlib import Path

    from app.adapters.text_model import LEXICON_CONFIDENCE, TextModelAdapter

    adapter = TextModelAdapter(checkpoint=Path("__checkpoint-tidak-ada__.pt"))
    assert adapter.mode == "fallback"
    assert adapter.calibrated is False
    assert adapter.sentiment_temperature == 1.0
    assert adapter.fallback_reason

    reviews = [
        ProcessedReview(
            review_id="r1", clean_text="paketnya telat dan kemasannya penyok",
            pii_redacted=False, rating=2, category=Category.FASHION, has_image=False,
        )
    ]
    hasil = adapter.classify(reviews)
    assert hasil[0].predictions
    for item in hasil[0].predictions:
        assert item.confidence == LEXICON_CONFIDENCE


def test_suhu_baku_tidak_mengubah_apa_pun():
    """Suhu 1,0 berarti pembagiannya tidak berefek - jalur inferensi checkpoint yang belum
    dikalibrasi harus identik dengan sebelum fitur ini ada."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml" / "text"))
    from calibration import softmax

    logits = [2.0, 0.5, -1.0]
    assert softmax(logits, 1.0) == softmax(logits)
