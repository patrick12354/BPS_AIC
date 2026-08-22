"""Label pelabel A (LLM - Claude) untuk paket validasi aspek, ditulis 22 Agustus 2026.

Berkas ini adalah ARTEFAK ANOTASI, bukan kode produk. Ia menghasilkan
`data/annotation/aspect_human_A_done.csv` dari keputusan yang tercatat di sini - supaya siapa pun
dapat melihat PERSIS label apa yang diberikan LLM untuk tiap klausa, beserta bendera ragu/yakin,
tanpa harus mempercayai berkas CSV yang bisa saja disunting.

Aturan yang dipakai sama dengan PANDUAN_ANOTASI_ASPEK.md. Gold ADR-017 TIDAK dilihat saat melabeli.
Label ini BUKAN rujukan: rujukannya adalah label manusia (pelabel B). Peran berkas ini adalah
(1) menjadi satu "pendekatan" pembanding di tabel hasil, dan (2) menentukan baris mana yang wajib
dilabeli manusia (semua yang RAGU) di samping sampel kontrol acak dari yang YAKIN.

Jalankan:
    python scripts/_llm_aspect_labels_A.py
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ml" / "text"))
from lexicon import ALL_ASPECTS  # noqa: E402

ANNOT = REPO / "data" / "annotation"
SRC = ANNOT / "aspect_human_A.csv"
OUT_A = ANNOT / "aspect_human_A_done.csv"
OUT_B = ANNOT / "aspect_human_B_sisa.csv"

# Jumlah baris YAKIN yang ikut dilabeli manusia sebagai kontrol. Dengan ~60 baris kontrol,
# tingkat kesalahan label "yakin" dapat ditaksir dengan margin sekitar +-10 poin - cukup untuk
# tahu apakah "yakin" layak dipercaya, tidak cukup untuk mengklaim presisi lebih dari itu.
N_CONTROL = 60
CONTROL_SEED = 7

KP, KD, HV, UV, RM, KM, PG, PP, KL, KA, KU = (
    "kualitas_produk", "kesesuaian_deskripsi", "harga_value", "ukuran_varian",
    "rasa_kualitas_makanan", "kemasan", "pengiriman", "pelayanan_penjual", "kelengkapan",
    "keaslian", "kemudahan_penggunaan",
)

# (indeks urutan di aspect_human_A.csv) -> (aspek, sentimen, ragu?, catatan)
L: dict[int, tuple[tuple[str, ...], str, bool, str]] = {
    0: ((RM,), "negatif", False, ""),
    1: ((PG,), "positif", False, ""),
    2: ((KM, PG), "negatif", True, "'sudah sampai' netral soal pengiriman; keluhannya packing"),
    3: ((HV,), "positif", False, ""),
    4: ((UV,), "positif", False, ""),
    5: ((UV,), "negatif", False, ""),
    6: ((PG,), "positif", False, ""),
    7: ((), "netral", True, "ucapan terima kasih - bisa dibaca positif"),
    8: ((KP, PG), "positif", False, ""),
    9: ((KP,), "positif", True, "ada 'mungkin ada kesalahan' - campuran, arahnya tidak jelas"),
    10: ((KP, HV), "negatif", False, ""),
    11: ((UV,), "negatif", False, "varian warna yang dikirim salah"),
    12: ((KP,), "positif", False, ""),
    13: ((KP,), "netral", True, "'bisa dipakai' - datar, bisa dibaca positif lemah"),
    14: ((KP, HV), "positif", False, ""),
    15: ((KA, KM), "positif", False, ""),
    16: ((), "positif", True, "pujian umum ke merek, tidak menyebut aspek"),
    17: ((UV,), "netral", True, "saran agar disediakan pilihan ukuran - netral atau keluhan ringan"),
    18: ((HV,), "positif", False, ""),
    19: ((KP, HV), "positif", False, ""),
    20: ((KP,), "negatif", True, "barang rusak saat dikirim - kualitas produk atau kerusakan pengiriman?"),
    21: ((PP,), "netral", False, ""),
    22: ((KD,), "negatif", False, ""),
    23: ((KD, PP), "positif", False, ""),
    24: ((KU,), "positif", False, ""),
    25: ((PG,), "positif", False, ""),
    26: ((KP, KD), "negatif", True, "campuran: nyaman tapi warna tidak sesuai ekspektasi"),
    27: ((UV,), "negatif", False, ""),
    28: ((KP, KA), "positif", False, ""),
    29: ((UV,), "negatif", False, ""),
    30: ((KA,), "positif", False, ""),
    31: ((PP,), "positif", False, ""),
    32: ((KP, UV), "negatif", False, ""),
    33: ((KP,), "positif", False, ""),
    34: ((UV, KP), "negatif", True, "'kaki sakit' - ukuran/fit atau kualitas sepatu?"),
    35: ((KD, UV), "positif", True, "klausa terpotong: 'mungkin size...'"),
    36: ((UV,), "negatif", False, "warna tidak sesuai pesanan = varian"),
    37: ((), "positif", False, ""),
    38: ((), "netral", True, "'ya sudah lah' - pasrah, bisa dibaca negatif"),
    39: ((PP,), "netral", False, ""),
    40: ((RM,), "negatif", False, ""),
    41: ((KP, PP), "positif", False, ""),
    42: ((KP,), "negatif", True, "'untuk molar jangan pakai ini' - ketidakcocokan fungsi; kesesuaian atau kualitas?"),
    43: ((KU,), "negatif", False, ""),
    44: ((UV,), "negatif", False, ""),
    45: ((KM,), "negatif", False, ""),
    46: ((RM,), "positif", False, ""),
    47: ((PG, KM), "positif", False, ""),
    48: ((KP,), "positif", False, ""),
    49: ((KL,), "positif", False, ""),
    50: ((RM,), "positif", True, "'sedap gurih' pada kategori fashion - mungkin sarkasme atau salah kategori"),
    51: ((PG,), "positif", False, ""),
    52: ((KL,), "netral", False, ""),
    53: ((KP, KL), "positif", False, ""),
    54: ((PP,), "positif", False, ""),
    55: ((PG, PP), "positif", False, ""),
    56: ((KA,), "positif", False, ""),
    57: ((KD, KL), "positif", False, ""),
    58: ((PP,), "positif", False, ""),
    59: ((KP,), "positif", False, ""),
    60: ((KA,), "positif", False, ""),
    61: ((KL,), "positif", False, ""),
    62: ((KP,), "negatif", False, ""),
    63: ((RM,), "negatif", False, ""),
    64: ((), "positif", False, ""),
    65: ((KD,), "negatif", False, ""),
    66: ((KP, KA), "positif", False, ""),
    67: ((HV,), "positif", False, ""),
    68: ((PG,), "negatif", False, ""),
    69: ((KP, HV), "positif", True, "'kualitas sesuai harga' - positif lemah atau netral"),
    70: ((PP, PG, KP), "positif", False, ""),
    71: ((KM,), "positif", False, ""),
    72: ((PG,), "negatif", True, "ongkir & pengiriman ribet - konteks terpotong"),
    73: ((UV,), "negatif", False, ""),
    74: ((PG,), "netral", False, ""),
    75: ((KD,), "negatif", True, "isi box berbeda dari label - kesesuaian atau varian?"),
    76: ((RM,), "positif", False, ""),
    77: ((KP,), "positif", False, ""),
    78: ((KP,), "negatif", True, "campuran: nyaman/bagus tapi bolong"),
    79: ((PP, PG, KM, KL, KD), "positif", False, ""),
    80: ((PG, HV), "positif", False, ""),
    81: ((KP,), "positif", False, ""),
    82: ((), "positif", True, "'top markotop' - pujian umum tanpa aspek"),
    83: ((HV,), "netral", True, "'standar sesuai harga' - netral atau positif lemah"),
    84: ((), "positif", True, "'but oke lah' - positif lemah, klausa terpotong"),
    85: ((PG,), "positif", False, ""),
    86: ((KP, PP, UV), "negatif", True, "tiga hal sekaligus; 'pesannya warna putih 1 dan coklat' tersirat varian salah"),
    87: ((PP,), "negatif", False, ""),
    88: ((KP,), "negatif", True, "'boro-boro dikonsumsi' - kategori other; rasa atau kualitas?"),
    89: ((PP,), "positif", False, ""),
    90: ((KP, PG), "positif", False, ""),
    91: ((KA, KD), "negatif", True, "'tidak sesuai dengan yang original bawaannya' - keaslian atau kesesuaian"),
    92: ((KP,), "positif", True, "'main jadi lebih asik' - manfaat produk, aspeknya samar"),
    93: ((KA, KL), "positif", False, ""),
    94: ((PP, KP, KM), "positif", False, ""),
    95: ((UV,), "negatif", False, ""),
    96: ((KP,), "negatif", True, "barang penyok - produk atau kemasan?"),
    97: ((KP,), "positif", False, ""),
    98: ((KD,), "negatif", True, "'tidak sesuai pesanan' generik - kesesuaian atau varian"),
    99: ((KP,), "positif", False, ""),
    100: ((KP,), "positif", True, "campuran: nerawang tapi overall bagus"),
    101: ((KP,), "positif", False, ""),
    102: ((KP, KM, PG), "positif", False, ""),
    103: ((PP, KL), "positif", True, "'beli di sini' = toko; 'lengkap' = kelengkapan"),
    104: ((PG,), "netral", True, "ucapan terima kasih + barang sampai"),
    105: ((KP,), "positif", False, ""),
    106: ((UV, KD), "positif", False, ""),
    107: ((KD,), "positif", False, ""),
    108: ((PP,), "negatif", False, ""),
    109: ((KP,), "positif", False, ""),
    110: ((HV,), "negatif", True, "'eman juga beli dengan harga 40rb' - sesal soal harga, konteks terpotong"),
    111: ((KP, HV), "positif", False, ""),
    112: ((KU,), "positif", True, "'mdh' terpotong - kemungkinan 'mudah'"),
    113: ((KP,), "positif", True, "'bisa dipakai di rumah saja' - pujian terbatas"),
    114: ((KP,), "negatif", True, "bahan beda antar-varian - keluhan konsistensi atau sekadar info"),
    115: ((KD, UV), "negatif", False, ""),
    116: ((KP, UV), "positif", False, ""),
    117: ((UV,), "netral", False, ""),
    118: ((PP,), "negatif", False, ""),
    119: ((KD,), "positif", False, ""),
    120: ((KP,), "negatif", True, "saran perbaikan bahan & jahitan - keluhan halus"),
    121: ((KA,), "positif", False, ""),
    122: ((PG,), "netral", True, "kurir bertanggung jawab (positif) + pesan di toko lain (negatif) - campuran"),
    123: ((PP, PG), "positif", False, ""),
    124: ((KP, HV), "positif", True, "'kualitas sesuai harga' - netral atau positif lemah"),
    125: ((KP, KM, PG), "positif", False, ""),
    126: ((KP,), "positif", False, ""),
    127: ((UV,), "negatif", False, ""),
    128: ((), "negatif", False, ""),
    129: ((KA,), "positif", False, ""),
    130: ((UV,), "netral", True, "deskripsi dimensi - dimensi = ukuran_varian menurut panduan, tetapi datar"),
    131: ((PG,), "negatif", True, "ongkir mahal - pengiriman atau harga?"),
    132: ((KP,), "positif", False, ""),
    133: ((KD, PP), "positif", False, ""),
    134: ((KL,), "positif", False, ""),
    135: ((UV,), "netral", True, "pertanyaan soal warna yang di-checkout - tersirat salah kirim"),
    136: ((KP,), "negatif", True, "tombol L2 kurang enak ditekan - kualitas atau kemudahan pakai"),
    137: ((HV,), "negatif", True, "'rugi' tanpa konteks"),
    138: ((UV, KP), "positif", False, ""),
    139: ((UV, KD), "positif", False, ""),
    140: ((PG,), "positif", True, "ucapan terima kasih + diterima dengan baik"),
    141: ((KP,), "positif", True, "fitur hook - kualitas/desain atau kemudahan pakai"),
    142: ((UV, KP), "negatif", True, "bahan random tidak bisa pilih - varian atau kualitas"),
    143: ((KP,), "positif", False, ""),
    144: ((KP,), "negatif", True, "'tidak bisa digunakan' - cacat produk atau sulit dipakai"),
    145: ((KP, UV), "positif", False, ""),
    146: ((KP, UV), "positif", False, ""),
    147: ((UV,), "netral", False, ""),
    148: ((PG,), "positif", False, ""),
    149: ((HV,), "negatif", True, "'harga lumayan mahal' - konteks terpotong"),
    150: ((KL, KD), "positif", False, ""),
    151: ((PP, PG, KM, KA, HV), "positif", False, ""),
    152: ((PP, KM, KD), "positif", False, ""),
    153: ((PP,), "negatif", False, ""),
    154: ((KM,), "negatif", False, ""),
    155: ((PG, KD, KP), "positif", False, ""),
    156: ((KM,), "positif", False, ""),
    157: ((KD,), "positif", False, ""),
    158: ((KP, HV), "positif", True, "'sesuai harga' - netral atau positif lemah"),
    159: ((PP,), "negatif", True, "peringatan ke toko, isi keluhannya tidak disebut"),
    160: ((KM,), "positif", False, ""),
    161: ((UV,), "negatif", False, ""),
    162: ((KL,), "negatif", False, ""),
    163: ((KP,), "positif", False, ""),
    164: ((UV, PP), "negatif", False, ""),
    165: ((KL,), "positif", False, ""),
    166: ((RM,), "negatif", False, ""),
    167: ((KP, KD), "positif", False, ""),
    168: ((UV,), "netral", True, "'buat anak usia 7 tahun' - konteks ukuran, tanpa penilaian"),
    169: ((KM,), "positif", False, ""),
    170: ((KL, KD), "negatif", True, "pesan 2 datang 1 - kelengkapan atau kesesuaian pesanan"),
    171: ((RM,), "netral", True, "info 'tidak cocok untuk yang tidak suka manis' - netral atau negatif"),
    172: ((KP,), "positif", True, "'bagus' generik - aspeknya ditebak kualitas"),
    173: ((KP,), "positif", False, ""),
    174: ((UV,), "negatif", True, "'sesaknya luar biasa' - ukuran/fit; kategori other"),
    175: ((KD, PP), "positif", False, ""),
    176: ((KM,), "negatif", False, ""),
    177: ((KA,), "negatif", False, ""),
    178: ((), "positif", True, "'mantap' generik"),
    179: ((), "negatif", True, "'hadeuh' - keluhan tanpa aspek"),
    180: ((KP,), "positif", False, ""),
    181: ((KL, KM), "positif", False, ""),
    182: ((KP,), "positif", True, "'bagusbtas' - typo 'bagus banget'?"),
    183: ((KD,), "positif", False, ""),
    184: ((KU, KP), "positif", True, "tutorial penggunaan efektif - kemudahan pakai atau kualitas"),
    185: ((KP,), "positif", False, ""),
    186: ((PP,), "negatif", False, ""),
    187: ((KD,), "positif", True, "'pas dengan body' perangkat - kesesuaian atau ukuran"),
    188: ((UV, PP), "negatif", False, ""),
    189: ((PP,), "positif", False, ""),
    190: ((UV,), "positif", False, ""),
    191: ((UV, KP), "negatif", True, "campuran: warna salah tapi bahan enak"),
    192: ((KP,), "positif", False, ""),
    193: ((PG,), "negatif", False, ""),
    194: ((PP, KP), "positif", True, "'proses cepat' - pelayanan atau pengiriman"),
    195: ((RM,), "positif", False, ""),
    196: ((KP,), "positif", False, ""),
    197: ((KP, PP), "positif", False, ""),
    198: ((KP, HV, KA), "positif", False, ""),
    199: ((KP, KL, KD), "positif", False, ""),
}


def main() -> int:
    with SRC.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames
        rows = list(reader)
    assert len(rows) == len(L) == 200, (len(rows), len(L))

    ragu_rows, yakin_rows = [], []
    for i, r in enumerate(rows):
        aspects, sent, ragu, note = L[i]
        for a in ALL_ASPECTS:
            r[f"asp_{a}"] = "1" if a in aspects else ""
        r["sentimen"] = sent
        r["catatan_pelabel"] = ("RAGU: " + note) if ragu else "yakin"
        (ragu_rows if ragu else yakin_rows).append(r)

    with OUT_A.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # Berkas untuk pelabel manusia: semua yang RAGU + kontrol acak dari yang YAKIN, diacak lagi,
    # TANPA label dan TANPA bendera - manusia tidak boleh tahu mana yang LLM ragukan.
    rng = random.Random(CONTROL_SEED)
    control = rng.sample(yakin_rows, min(N_CONTROL, len(yakin_rows)))
    subset = ragu_rows + control
    rng.shuffle(subset)
    with OUT_B.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in subset:
            w.writerow({**{k: "" for k in fields}, "clause_id": r["clause_id"],
                        "clause_text": r["clause_text"], "category_produk": r["category_produk"]})

    print(f"A (LLM) : {len(rows)} klausa -> {OUT_A.name}  ({len(ragu_rows)} RAGU, {len(yakin_rows)} yakin)")
    print(f"B (manusia): {len(subset)} klausa -> {OUT_B.name}  ({len(ragu_rows)} ragu + {len(control)} kontrol acak)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
