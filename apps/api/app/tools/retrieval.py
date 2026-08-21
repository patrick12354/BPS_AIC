"""retrieve_evidence() - RET-01, tool contract bagian 27.3 (desain bagian 21).

Mengambil kutipan ulasan ASLI sebagai bukti setiap klaim. Ini fondasi kepercayaan produk:
pemilik UMKM yang skeptis pada AI ingin melihat kalimat pelanggannya sendiri, bukan ringkasan
(bagian 8.1, JTBD-07).

Empat perilaku yang mengikat, semuanya berasal dari bagian 21:

- **Unit indexing adalah ULASAN, bukan klausa.** Klausa dipakai untuk klasifikasi karena
  sentimennya per-aspek, tetapi bukti yang ditunjukkan ke pengguna harus utuh - kutipan
  sepotong justru mengurangi kepercayaan.
- **Menolak menjawab lebih baik daripada mengarang.** Bila skor kemiripan tertinggi di bawah
  ambang, fungsi mengembalikan daftar kosong dan pemanggilnya WAJIB menampilkan "data belum
  cukup" - LLM tidak pernah dipanggil untuk mengarang kutipan (bagian 21.3).
- **Deduplikasi near-duplicate**, supaya top-k tidak dipenuhi ulasan yang isinya nyaris sama.
- **Diversifikasi ringan (MMR)**, supaya bukti tidak seluruhnya berasal dari satu produk.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from ..schemas import Aspect, EvidenceCitation

# Di bawah ambang ini, sistem menyatakan data belum cukup dan TIDAK memanggil LLM.
# Nilai ini dikalibrasi pada Fase 8; sampai saat itu dipakai ambang konservatif.
DEFAULT_MIN_SIMILARITY = 0.30

# Bobot relevansi vs keberagaman pada MMR. 1.0 = murni relevansi.
MMR_LAMBDA = 0.7

# Dua ulasan dianggap near-duplicate bila kemiripan token-nya melewati ini.
NEAR_DUPLICATE_THRESHOLD = 0.85

_WORD = re.compile(r"\w+")


@dataclass
class IndexedReview:
    review_id: str
    text: str
    vector: np.ndarray
    aspects: frozenset[str]
    # Aspek yang disebut NEGATIF pada ulasan ini. Dipisahkan dari `aspects` karena bukti untuk
    # Action Card keluhan harus berupa keluhan - kutipan pujian pada kartu keluhan justru
    # merusak kepercayaan yang ingin dibangun bukti itu.
    negative_aspects: frozenset[str] = frozenset()
    # Cerminan dari `negative_aspects`, dan ada karena alasan yang sama dibalik: pertanyaan
    # "apa yang paling disukai pembeli" dijawab kalimat pujian, dan kalimat itu wajib
    # dibuktikan kutipan pujian. Sebelum ini kartu peluang dan jawaban pujian sama-sama
    # mengambil kutipan tanpa penyaringan sentimen, sehingga keduanya kerap tampil dengan
    # keluhan sebagai buktinya.
    positive_aspects: frozenset[str] = frozenset()
    product_id: str | None = None
    rating: int | None = None
    timestamp: object | None = None


def _token_overlap(a: str, b: str) -> float:
    ta, tb = set(_WORD.findall(a.lower())), set(_WORD.findall(b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


class EvidenceIndex:
    """Indeks bukti untuk SATU sesi analisis.

    Cakupannya sengaja dibatasi per sesi (bagian 23.3 session_scope): retrieval tidak pernah
    menjangkau data pengguna lain, dan indeksnya hilang bersama sesinya.
    """

    def __init__(self, adapter, min_similarity: float = DEFAULT_MIN_SIMILARITY):
        self.adapter = adapter
        self.min_similarity = min_similarity
        self.items: list[IndexedReview] = []
        # Vektor kueri disimpan per teks kueri.
        #
        # Satu analisis memanggil retrieve() sekali per Action Card dan sekali lagi per aspek
        # yang dipuji - dan kueri untuk aspek yang sama SELALU teks yang sama ("kualitas
        # produk", "ukuran varian", ...). Tanpa singgahan ini, aspek yang muncul di kartu
        # keluhan sekaligus di daftar peluang di-encode dua kali untuk hasil yang identik.
        # Isinya hilang bersama indeksnya, jadi cakupannya tetap satu sesi (bagian 23.3).
        self._query_vectors: dict[str, np.ndarray] = {}

    def build(self, reviews: list[dict]) -> None:
        """Bangun indeks dari ulasan sesi. `reviews` memuat review_id, text, aspects, dst."""
        texts = [r["text"] for r in reviews]
        if not texts:
            self.items = []
            return
        vectors = self.adapter.encode(texts, corpus=texts)
        self._query_vectors.clear()  # indeks baru, korpus baru - vektor lama tidak lagi berlaku
        self.items = [
            IndexedReview(
                review_id=r["review_id"],
                text=r["text"],
                vector=v,
                aspects=frozenset(r.get("aspects", [])),
                negative_aspects=frozenset(r.get("negative_aspects", [])),
                positive_aspects=frozenset(r.get("positive_aspects", [])),
                product_id=r.get("product_id"),
                rating=r.get("rating"),
                timestamp=r.get("timestamp"),
            )
            for r, v in zip(reviews, vectors)
        ]

    def _candidates(
        self, aspect: Aspect | None, negative_only: bool, positive_only: bool = False
    ) -> list[IndexedReview]:
        """Filter metadata SEBELUM ranking similarity (bagian 21.1) - mengurangi derau."""
        if aspect is None:
            # Penyaringan sentimen tetap berlaku tanpa aspek. Pertanyaan "apa yang paling
            # disukai pembeli" tidak menyebut aspek mana pun, dan justru pertanyaan itulah
            # yang paling mudah dijawab dengan kutipan keluhan kalau penyaringnya dilewati.
            if positive_only:
                positive = [i for i in self.items if i.positive_aspects]
                if positive:
                    return positive
            if negative_only:
                negative = [i for i in self.items if i.negative_aspects]
                if negative:
                    return negative
            return self.items

        if positive_only:
            positive = [i for i in self.items if aspect.value in i.positive_aspects]
            if positive:
                return positive

        if negative_only:
            # Bukti untuk kartu keluhan HARUS keluhan. Diukur pada dataset demo, tanpa filter
            # ini kartu "perbaiki keterangan ukuran" mendapat kutipan "warna/ukuran sesuai" -
            # bukti yang membantah klaimnya sendiri.
            negative = [i for i in self.items if aspect.value in i.negative_aspects]
            if negative:
                return negative

        filtered = [i for i in self.items if aspect.value in i.aspects]
        # Bila filter menyisakan terlalu sedikit, jangan kosongkan hasil - lebih baik mencari
        # di seluruh indeks daripada mengembalikan tangan kosong karena metadata tidak lengkap.
        return filtered if len(filtered) >= 3 else self.items

    def retrieve(
        self, query: str, aspect: Aspect | None = None, top_k: int = 5,
        negative_only: bool = False, positive_only: bool = False,
    ) -> list[EvidenceCitation]:
        """Ambil kutipan paling relevan. Daftar KOSONG berarti data belum cukup.

        `negative_only` dipakai saat bukti diminta untuk Action Card keluhan, `positive_only`
        untuk kartu peluang dan jawaban tentang apa yang dipuji. Keduanya tidak pernah aktif
        bersamaan; bila terjadi, pujian menang karena ia pemanggil yang lebih spesifik.
        """
        candidates = self._candidates(aspect, negative_only, positive_only)
        if not candidates:
            return []

        query_vector = self._query_vectors.get(query)
        if query_vector is None:
            query_vector = self.adapter.encode(
                [query], corpus=[i.text for i in self.items]
            )[0]
            self._query_vectors[query] = query_vector
        scores = np.array([float(query_vector @ i.vector) for i in candidates])

        eligible = [(s, c) for s, c in zip(scores, candidates) if s >= self.min_similarity]
        if not eligible:
            # Ambang tidak terlampaui - sistem menolak menjawab alih-alih mengarang bukti.
            return []
        eligible.sort(key=lambda x: -x[0])

        selected: list[tuple[float, IndexedReview]] = []
        for score, item in eligible:
            if len(selected) >= top_k:
                break
            # Deduplikasi near-duplicate.
            if any(_token_overlap(item.text, s.text) >= NEAR_DUPLICATE_THRESHOLD for _, s in selected):
                continue
            # Diversifikasi ringan: turunkan peringkat bukti dari produk yang sudah terwakili.
            if item.product_id and any(
                s.product_id == item.product_id for _, s in selected
            ):
                score *= MMR_LAMBDA
            selected.append((score, item))

        selected.sort(key=lambda x: -x[0])
        return [
            EvidenceCitation(
                citation_id=f"c{idx + 1}",
                review_id=item.review_id,
                quote=item.text,  # kutipan ASLI, tidak diparafrase (bagian 25.10)
                relevance_score=round(min(max(float(score), 0.0), 1.0), 4),
                aspect=aspect,
                rating=item.rating,
                timestamp=item.timestamp,
            )
            for idx, (score, item) in enumerate(selected)
        ]


def retrieve_evidence(
    index: EvidenceIndex, query: str, aspect: Aspect | None = None, top_k: int = 5,
    negative_only: bool = False, positive_only: bool = False,
) -> list[EvidenceCitation]:
    """Bentuk fungsi sesuai tool contract bagian 27.3."""
    return index.retrieve(
        query=query, aspect=aspect, top_k=top_k,
        negative_only=negative_only, positive_only=positive_only,
    )
