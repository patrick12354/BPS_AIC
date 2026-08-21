"""Aturan agregasi klausa menjadi sentimen dokumen (L2).

Model bekerja pada KLAUSA; sebagian besar dataset berlabel manusia memberi label pada DOKUMEN.
Jembatan di antara keduanya adalah aturan keputusan - dan aturan itu adalah pilihan produk,
bukan detail teknis evaluasi.

**Kenapa berkas ini ada.** Sampai sekarang aturannya ditulis ulang di dua tempat
(`evaluate_external.py` dan `tune_sentiment_threshold.py`), keduanya memakai suara terbanyak,
dan tidak satu pun sama dengan aturan yang dipakai produk. Backend menghitung "ulasan
berkeluhan" dengan cara yang sama sekali berbeda: satu klausa negatif ber-aspek sudah cukup
(`tools/segments.py::_negative_aspects`, `services/analyze.py::reviews_with_complaint`).

Akibatnya angka macro-F1 yang kami laporkan mengukur sistem yang tidak kami kirimkan. Itu bukan
kesalahan kecil pada laporan - itu klaim yang tidak berlaku bagi barangnya.

**Kenapa suara terbanyak salah untuk produk ini.** Temuan Fase 8 mengukurnya: dari 128 ulasan
negatif yang terlewat pada PRDECT-ID, **11 sudah punya klausa dengan P(negatif) >= 0,5** dan
kalah pada agregasi dokumen. Ulasan "bahannya bagus, pengiriman cepat, tapi jahitannya lepas"
memuat dua pujian dan satu keluhan; suara terbanyak menyimpulkannya positif. Bagi pemilik toko
yang membuka produk ini untuk MENEMUKAN keluhan, itu kegagalan misi - bukan kesalahan
klasifikasi yang bisa ditoleransi.

**Kenapa asimetris, bukan sekadar ambang yang lebih longgar.** Keluhan dan pujian tidak
sepadan biayanya. Keluhan yang terlewat berarti pemilik toko tidak pernah tahu ada masalah;
pujian yang terlewat berarti satu baris kurang di daftar peluang. Aturan yang memperlakukan
keduanya sama dengan sendirinya salah menimbang.

Aturan asimetris ini MENAIKKAN recall negatif dan MENURUNKAN presisinya - itu pasti, bukan
dugaan. Yang tidak pasti adalah besarannya, dan itulah kenapa `evaluate_external.py` sekarang
melaporkan kedua aturan berdampingan alih-alih diam-diam mengganti yang satu dengan yang lain.
Angkanya diputuskan setelah diukur, bukan sebelum.
"""

from __future__ import annotations

SENTIMENTS = ["negatif", "netral", "positif"]
NEGATIF, NETRAL, POSITIF = SENTIMENTS

# Ambang keyakinan minimal sebuah klausa boleh menegatifkan seluruh dokumen.
#
# 0,5 bukan angka pilihan selera: pada tiga kelas, probabilitas >= 0,5 berarti kelas itu pasti
# argmax-nya. Jadi aturan di bawah tidak pernah "menyelamatkan" klausa yang modelnya sendiri
# tidak yakin - ia hanya berhenti menenggelamkan klausa yang modelnya SUDAH yakin. Ambang yang
# lebih rendah akan mulai memungut derau, dan temuan Fase 8 sudah menunjukkan tidak ada yang
# bisa dipungut di sana: 113 dari 128 yang terlewat berada di bawah P(negatif) 0,10.
NEGATIVE_CLAUSE_THRESHOLD = 0.5


def by_majority(clause_sentiments: list[str]) -> str:
    """Aturan lama: suara terbanyak, klausa non-netral menang atas netral.

    Dipertahankan sebagai PEMBANDING, bukan sebagai pilihan. Tanpa angkanya, klaim bahwa aturan
    baru lebih baik tidak dapat diperiksa siapa pun - termasuk oleh kami sendiri.
    """
    if not clause_sentiments:
        return NETRAL
    non_neutral = [s for s in clause_sentiments if s != NETRAL]
    pool = non_neutral or clause_sentiments
    return max(set(pool), key=pool.count)


def by_asymmetric(clause_sentiments: list[str], negative_probs: list[float] | None = None,
                  threshold: float = NEGATIVE_CLAUSE_THRESHOLD) -> str:
    """Aturan produk: satu klausa negatif yang yakin sudah menegatifkan dokumen.

    Args:
        clause_sentiments: label per klausa hasil argmax
        negative_probs: P(negatif) per klausa. Bila diberikan, klausa dianggap negatif ketika
            probabilitasnya melewati ambang - bukan hanya ketika ia menang argmax. Bila tidak
            diberikan (mis. jalur leksikon yang tidak menghasilkan probabilitas), label argmax
            dipakai apa adanya.
        threshold: ambang keyakinan klausa

    Sisanya - dokumen yang tidak punya satu pun klausa negatif meyakinkan - tetap diputuskan
    suara terbanyak. Yang berubah hanya sisi negatifnya, dan itulah arti "asimetris" di sini:
    bukan aturan baru untuk semua, melainkan satu pengecualian yang sengaja berat sebelah ke
    arah yang biaya kesalahannya lebih murah.
    """
    if not clause_sentiments:
        return NETRAL

    if negative_probs is not None:
        if any(p >= threshold for p in negative_probs):
            return NEGATIF
    elif NEGATIF in clause_sentiments:
        return NEGATIF

    return by_majority(clause_sentiments)


# Nama aturan -> fungsinya, dipakai skrip evaluasi untuk melaporkan keduanya berdampingan.
RULES = {
    "mayoritas_klausa": by_majority,
    "asimetris_negatif": by_asymmetric,
}
