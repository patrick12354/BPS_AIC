"""Matematika kalibrasi keyakinan - temperature scaling (Guo et al., 2017), L1.

Dipisahkan dari skrip yang menjalankannya supaya dapat diuji tanpa checkpoint, tanpa dataset,
dan tanpa torch. Yang di sini murni aritmetika atas logit; yang di `calibrate.py` adalah
pemuatan model dan penulisan bundle.

**Masalah yang diselesaikan.** `AspectPrediction.confidence` sampai sekarang adalah konstanta
(0,80 saat checkpoint aktif, 0,60 saat leksikon) - penanda sementara yang tidak pernah diganti.
Ia dicabut dari antarmuka karena angka tetap yang berdiri di antara angka hasil hitungan akan
terbaca sebagai hasil hitungan juga (lihat docs/LIMITATIONS.md).

Menyembunyikan bukan penyelesaian, hanya penundaan yang jujur. Penyelesaiannya mengukur.

**Kenapa softmax mentah tidak cukup.** Jaringan neural modern terkenal terlalu percaya diri:
softmax 0,95 pada model yang tidak dikalibrasi kerap benar jauh di bawah 95% waktu. Temuan
Fase 8 memperlihatkannya dari sisi sebaliknya pada model ini - 113 dari 128 ulasan negatif
yang terlewat diprediksi dengan P(negatif) di bawah 0,10, median 0,0006. Model bukan ragu lalu
memilih salah; **ia yakin dan salah**. Angka seyakin itu tidak boleh sampai ke layar tanpa
diperiksa lebih dulu seberapa sering ia benar.

**Kenapa temperature scaling, bukan yang lain.** Ia satu parameter per head, di-fit pada split
validasi yang sudah ada, dan **tidak mengubah satu pun keputusan model**: membagi logit dengan
skalar positif tidak menggeser argmax-nya. Jadi akurasi, F1, dan urutan Action Card tetap sama
persis - yang berubah hanya seberapa jujur angka keyakinannya. Metode kalibrasi lain (isotonic,
Platt per kelas) lebih lentur tetapi mengubah keputusan, dan itu menuntut evaluasi ulang penuh
untuk sesuatu yang bukan tujuannya.

Inferensi produksi karenanya berubah satu baris: `logits / T`. Parameternya tetap statis saat
demo, sesuai batasan MVP.
"""

from __future__ import annotations

import math

# Jumlah bin untuk ECE. Sepuluh adalah angka yang dipakai makalah aslinya dan yang dipakai
# hampir semua laporan sesudahnya - dipertahankan supaya angkanya dapat dibandingkan dengan
# yang dilaporkan orang lain, bukan hanya dengan dirinya sendiri.
ECE_BINS = 10

# Rentang pencarian suhu. Batas bawah tidak nol karena T -> 0 membuat softmax menjadi one-hot
# dan NLL meledak; batas atas 10 sudah jauh melewati suhu yang pernah dilaporkan untuk model
# sebesar ini (biasanya 1,0-3,0).
T_MIN, T_MAX = 0.05, 10.0


def softmax(logits: list[float], temperature: float = 1.0) -> list[float]:
    """Softmax dengan suhu, stabil terhadap logit besar."""
    if temperature <= 0:
        raise ValueError("suhu harus positif")
    scaled = [x / temperature for x in logits]
    m = max(scaled)
    exp = [math.exp(x - m) for x in scaled]
    total = sum(exp)
    return [e / total for e in exp]


def negative_log_likelihood(
    logits: list[list[float]], labels: list[int], temperature: float = 1.0
) -> float:
    """Rata-rata NLL pada suhu tertentu - fungsi objektif yang diminimalkan.

    NLL dipakai, bukan ECE, meski ECE yang dilaporkan. Alasannya: ECE adalah fungsi tangga -
    ia hanya berubah ketika sebuah contoh berpindah bin - sehingga permukaannya datar di
    hampir semua tempat dan pencarian apa pun akan tersangkut di dataran itu. NLL mulus dan
    proper (minimumnya berada pada probabilitas yang benar), jadi ia mengarah ke tempat yang
    sama tanpa dataran.
    """
    if not logits:
        return 0.0
    total = 0.0
    for row, label in zip(logits, labels):
        p = softmax(row, temperature)[label]
        total -= math.log(max(p, 1e-12))
    return total / len(logits)


def expected_calibration_error(
    logits: list[list[float]], labels: list[int], temperature: float = 1.0,
    bins: int = ECE_BINS,
) -> float:
    """ECE - selisih rata-rata antara keyakinan yang diakui dan akurasi yang dicapai.

    Dibaca lurus: ECE 0,15 berarti ketika model bilang "yakin 90%", rata-rata ia benar sekitar
    75% waktu. Itulah angka yang menentukan boleh atau tidaknya keyakinan ditampilkan ke
    pengguna - bukan akurasi, dan bukan F1.
    """
    if not logits:
        return 0.0
    ember: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for row, label in zip(logits, labels):
        probs = softmax(row, temperature)
        conf = max(probs)
        pred = probs.index(conf)
        # Keyakinan 1,0 harus jatuh di bin terakhir, bukan di luar rentang.
        index = min(int(conf * bins), bins - 1)
        ember[index].append((conf, pred == label))

    n = len(logits)
    total = 0.0
    for isi in ember:
        if not isi:
            continue
        keyakinan = sum(c for c, _ in isi) / len(isi)
        akurasi = sum(1 for _, benar in isi if benar) / len(isi)
        total += (len(isi) / n) * abs(keyakinan - akurasi)
    return total


def fit_temperature(
    logits: list[list[float]], labels: list[int],
    lo: float = T_MIN, hi: float = T_MAX, iterations: int = 60,
) -> float:
    """Cari suhu yang meminimalkan NLL dengan pencarian bagi-tiga (ternary search).

    Bukan gradient descent, dan itu bukan kemalasan. Ini pencarian satu dimensi atas fungsi
    yang terbukti unimodal terhadap T (NLL menurun lalu menaik, tepat satu minimum), sehingga
    bagi-tiga menemukan optimumnya secara deterministik tanpa laju belajar, tanpa jumlah
    langkah yang harus disetel, dan tanpa titik awal yang bisa salah. Enam puluh iterasi
    mempersempit rentang [0,05; 10] sampai jauh di bawah presisi yang berarti bagi T.

    Deterministik penting di sini bukan demi keanggunan: seluruh angka di produk ini harus
    dapat direproduksi, dan suhu yang berbeda tiap kali di-fit akan membuat angka keyakinan
    di layar ikut berbeda antar-build tanpa satu pun perubahan pada model.
    """
    if not logits:
        return 1.0
    for _ in range(iterations):
        a = lo + (hi - lo) / 3.0
        b = hi - (hi - lo) / 3.0
        if negative_log_likelihood(logits, labels, a) < negative_log_likelihood(logits, labels, b):
            hi = b
        else:
            lo = a
    return round((lo + hi) / 2.0, 4)


def calibration_report(
    logits: list[list[float]], labels: list[int], temperature: float,
    bins: int = ECE_BINS,
) -> dict:
    """Angka sebelum dan sesudah, ditambah pemeriksaan bahwa keputusan tidak berubah.

    Baris terakhir itu yang membuat laporan ini dapat dipercaya. Klaim "kalibrasi tidak
    mengubah akurasi" adalah konsekuensi matematis dari membagi dengan skalar positif, tetapi
    konsekuensi matematis tetap bisa gagal karena bug - dan kalau ia gagal, seluruh evaluasi
    yang sudah dilaporkan ikut tidak berlaku. Jadi ia diperiksa, bukan diasumsikan.
    """
    def akurasi(t: float) -> float:
        benar = 0
        for row, label in zip(logits, labels):
            p = softmax(row, t)
            if p.index(max(p)) == label:
                benar += 1
        return benar / len(logits) if logits else 0.0

    return {
        "temperature": round(temperature, 4),
        "n": len(logits),
        "ece_sebelum": round(expected_calibration_error(logits, labels, 1.0, bins), 4),
        "ece_sesudah": round(expected_calibration_error(logits, labels, temperature, bins), 4),
        "nll_sebelum": round(negative_log_likelihood(logits, labels, 1.0), 4),
        "nll_sesudah": round(negative_log_likelihood(logits, labels, temperature), 4),
        "akurasi_sebelum": round(akurasi(1.0), 4),
        "akurasi_sesudah": round(akurasi(temperature), 4),
        "keputusan_tidak_berubah": akurasi(1.0) == akurasi(temperature),
    }
