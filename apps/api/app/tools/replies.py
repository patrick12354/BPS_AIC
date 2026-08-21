"""build_reply_drafts() - draf balasan penjual untuk ulasan negatif (fitur S1).

Ini titik tempat produk menyeberang dari INSIGHT ke PERCAKAPAN. Sisa sistem menjawab "apa yang
salah dan apa yang harus saya kerjakan"; modul ini menjawab pertanyaan berikutnya yang selalu
datang sesudahnya: "lalu saya balas apa ke orang ini?".

Empat aturan mengikat, dan semuanya berasal dari sifat kanalnya, bukan dari selera:

1. **Deterministik, tanpa API luar.** Balasan yang dihasilkan LLM akan mengarang detail yang
   tidak ada di dalam ulasan - nama barang, tanggal kirim, janji ganti rugi - dan penjual tidak
   punya cara memeriksanya kalimat per kalimat sebelum menekan kirim. Template berisi slot dari
   data nyata tidak dapat mengarang, karena tidak ada tempat untuk mengarang. Ini juga menjaga
   dua klaim inti produk tetap utuh: berjalan lokal tanpa API berbayar, dan angka tidak pernah
   dikarang.

2. **Variasi dipilih lewat hash review_id, bukan `random`.** Balasan yang identik kata demi kata
   pada dua puluh ulasan terbaca sebagai bot dan justru merusak kepercayaan pembeli yang
   membacanya - itulah kenapa ada bank frasa. Tetapi sumber acak sungguhan membuat dua kali
   analisis atas data yang sama menghasilkan draf berbeda, dan produk yang setiap angkanya
   dapat direproduksi tidak boleh punya satu sudut yang tidak. Hash memberi keduanya sekaligus.

3. **Keputusan bisnis tidak pernah ditulis sistem.** Refund, ganti barang, dan kompensasi ongkir
   adalah komitmen uang yang hanya diketahui pemiliknya sanggup atau tidak. Slot-slot itu
   ditinggalkan sebagai tanda kurung siku yang MENGGANGGU untuk dibaca - draf yang tinggal
   disalin memang akan disalin, jadi bagian yang tidak boleh lolos harus terlihat.

4. **Draf wajib disunting sebelum dapat dipakai.** Dijaga di sisi antarmuka (tombol salin baru
   aktif setelah teksnya disentuh), pola yang sama dengan draf hasil OCR. Konsistensinya
   disengaja: setiap kali sistem menghasilkan teks yang akan mewakili pengguna di luar sana,
   manusia menyentuhnya lebih dulu.
"""

from __future__ import annotations

import hashlib
import re

from ..schemas import ActionCard, Aspect, EvidenceCitation, ReplyDraft, Severity

MAX_DRAFTS_PER_CARD = 5

# --------------------------------------------------------------------------------------
# Bank frasa
# --------------------------------------------------------------------------------------
# Tiga varian per slot. Angka tiga bukan target keindahan: dengan empat slot, tiga varian sudah
# menghasilkan puluhan kombinasi, jauh melampaui jumlah balasan yang ditulis satu toko dalam
# satu sesi. Menambah varian di luar itu hanya menambah teks untuk dirawat.

SAPAAN = (
    "Halo Kak, terima kasih sudah menuliskan ulasannya.",
    "Halo Kak, terima kasih atas masukannya.",
    "Halo Kak, terima kasih sudah berbelanja dan meninggalkan ulasan.",
)

# Pengakuan disusun per aspek, karena kalimat yang mengaku secara umum ("maaf atas
# ketidaknyamanannya") adalah kalimat yang paling sering dibaca pembeli sebagai balasan tempel.
# Yang membedakan balasan sungguhan adalah ia menyebut hal yang dikeluhkan.
PENGAKUAN: dict[Aspect, tuple[str, ...]] = {
    Aspect.PENGIRIMAN: (
        "Kami minta maaf pesanan Kakak sampai lebih lama dari yang seharusnya.",
        "Mohon maaf atas keterlambatan pengiriman yang Kakak alami.",
        "Kami turut menyesal proses pengirimannya tidak berjalan semestinya.",
    ),
    Aspect.KEMASAN: (
        "Kami minta maaf kemasan pesanan Kakak sampai dalam kondisi kurang baik.",
        "Mohon maaf pengemasannya belum melindungi barang seperti seharusnya.",
        "Kami menyesal barangnya sampai dengan kemasan yang tidak layak.",
    ),
    Aspect.KUALITAS_PRODUK: (
        "Kami minta maaf kondisi barang yang Kakak terima tidak sesuai harapan.",
        "Mohon maaf kualitas barangnya belum seperti yang seharusnya Kakak terima.",
        "Kami menyesal barang yang sampai ternyata bermasalah.",
    ),
    Aspect.UKURAN_VARIAN: (
        "Kami minta maaf ukuran yang Kakak terima tidak sesuai perkiraan.",
        "Mohon maaf ukuran atau variannya tidak sesuai dengan yang Kakak harapkan.",
        "Kami menyesal pilihan ukurannya ternyata tidak pas.",
    ),
    Aspect.KESESUAIAN_DESKRIPSI: (
        "Kami minta maaf barangnya berbeda dari keterangan di halaman produk.",
        "Mohon maaf apa yang Kakak terima tidak sesuai dengan deskripsi kami.",
        "Kami menyesal keterangan produk kami membuat Kakak salah membayangkan.",
    ),
    Aspect.PELAYANAN_PENJUAL: (
        "Kami minta maaf pesan Kakak tidak kami balas sebagaimana mestinya.",
        "Mohon maaf pelayanan kami belum seperti yang Kakak harapkan.",
        "Kami menyesal Kakak tidak mendapat tanggapan yang memadai dari kami.",
    ),
    Aspect.HARGA_VALUE: (
        "Terima kasih sudah menyampaikan pendapat Kakak soal harganya.",
        "Kami memahami harganya terasa belum sepadan bagi Kakak.",
        "Masukan Kakak soal nilai barang dibanding harganya kami catat.",
    ),
    Aspect.RASA_KUALITAS_MAKANAN: (
        "Kami minta maaf rasanya tidak sesuai dengan yang Kakak harapkan.",
        "Mohon maaf produk yang Kakak terima tidak dalam kondisi rasa terbaiknya.",
        "Kami menyesal pengalaman rasanya mengecewakan.",
    ),
    Aspect.KELENGKAPAN: (
        "Kami minta maaf ada bagian pesanan yang tidak lengkap saat Kakak terima.",
        "Mohon maaf isi paketnya tidak sesuai dengan yang seharusnya.",
        "Kami menyesal ada yang kurang dari pesanan Kakak.",
    ),
    Aspect.KEASLIAN: (
        "Terima kasih sudah menyampaikan keraguan Kakak soal keaslian barangnya.",
        "Kami memahami kekhawatiran Kakak mengenai keaslian produk ini.",
        "Masukan Kakak soal keaslian barang kami tanggapi dengan serius.",
    ),
    Aspect.KEMUDAHAN_PENGGUNAAN: (
        "Kami minta maaf cara pemakaiannya menyulitkan Kakak.",
        "Mohon maaf petunjuk pemakaian kami belum cukup membantu.",
        "Kami menyesal barangnya tidak semudah itu dipakai.",
    ),
}

# Langkah perbaikan per aspek. Kalimatnya menyebut apa yang DIKERJAKAN TOKO, bukan apa yang
# didapat pembeli - yang kedua adalah janji, dan janji bukan wewenang sistem.
LANGKAH: dict[Aspect, tuple[str, ...]] = {
    Aspect.PENGIRIMAN: (
        "Kami sedang meninjau ulang jasa kirim yang kami pakai untuk tujuan seperti Kakak.",
        "Waktu proses sebelum paket diserahkan ke kurir sedang kami perbaiki.",
        "Kami sedang menata ulang alur pengiriman supaya tidak terulang.",
    ),
    Aspect.KEMASAN: (
        "Bahan pengemas kami sedang kami ganti dengan yang lebih tebal.",
        "Cara pengemasan untuk barang seperti ini sedang kami tinjau ulang.",
        "Kami sedang menambah lapisan pelindung pada pengiriman berikutnya.",
    ),
    Aspect.KUALITAS_PRODUK: (
        "Kami sedang memeriksa kembali stok dari batch yang sama.",
        "Pemeriksaan barang sebelum dikirim sedang kami perketat.",
        "Kami sedang menelusuri hal ini sampai ke pemasoknya.",
    ),
    Aspect.UKURAN_VARIAN: (
        "Tabel ukuran di halaman produk sedang kami perjelas.",
        "Keterangan ukuran akan kami lengkapi dengan angka yang lebih rinci.",
        "Kami sedang menambahkan panduan memilih ukuran di halaman produk.",
    ),
    Aspect.KESESUAIAN_DESKRIPSI: (
        "Foto dan keterangan di halaman produk sedang kami perbaiki.",
        "Deskripsi produknya akan kami sesuaikan supaya tidak lagi membingungkan.",
        "Kami sedang mengganti foto produk dengan yang lebih apa adanya.",
    ),
    Aspect.PELAYANAN_PENJUAL: (
        "Kami sedang membenahi cara kami menanggapi pesan yang masuk.",
        "Jam balas chat kami akan kami perbaiki supaya tidak ada yang terlewat.",
        "Kami sedang menyiapkan jawaban siap pakai untuk pertanyaan yang sering masuk.",
    ),
    Aspect.HARGA_VALUE: (
        "Masukan ini kami pakai saat meninjau harga dan isi paket penjualan kami.",
        "Kami akan menimbang kembali apa yang kami sertakan pada harga ini.",
        "Kami sedang meninjau kembali kesepadanan harga dan isinya.",
    ),
    Aspect.RASA_KUALITAS_MAKANAN: (
        "Kami sedang memeriksa kembali batch produksi dan cara penyimpanannya.",
        "Masa simpan dan pengemasan produk sedang kami tinjau ulang.",
        "Kami sedang menelusuri di bagian mana rasanya berubah.",
    ),
    Aspect.KELENGKAPAN: (
        "Pemeriksaan isi paket sebelum dikirim sedang kami perketat.",
        "Daftar periksa pengemasan kami akan kami lengkapi.",
        "Kami sedang menambahkan pemeriksaan kedua sebelum paket ditutup.",
    ),
    Aspect.KEASLIAN: (
        "Kami dapat mengirimkan keterangan asal barang ini bila Kakak membutuhkannya.",
        "Kami akan menampilkan keterangan asal barang lebih jelas di halaman produk.",
        "Kami sedang melengkapi bukti asal barang untuk seluruh produk kami.",
    ),
    Aspect.KEMUDAHAN_PENGGUNAAN: (
        "Petunjuk pemakaian akan kami tambahkan di halaman produk.",
        "Kami sedang menyiapkan panduan singkat yang lebih mudah diikuti.",
        "Kami akan menyertakan kartu petunjuk di dalam paket berikutnya.",
    ),
}

PENUTUP = (
    "Terima kasih sudah memberi tahu kami, Kak.",
    "Masukan Kakak sangat membantu kami membenahi ini.",
    "Sekali lagi terima kasih, dan mohon maaf atas ketidaknyamanannya.",
)

# Slot keputusan bisnis. Muncul HANYA pada keluhan berkeparahan tinggi, tempat pembeli memang
# menunggu jawaban soal uang atau barangnya - dan justru di situ sistem paling tidak berhak
# menjawab. Aspek yang tidak ada di sini (harga, keaslian, kemudahan pemakaian) tidak punya
# jalan keluar berupa ganti barang, jadi memasang slotnya hanya akan mengarang pilihan.
SLOT_KEPUTUSAN: dict[Aspect, str] = {
    Aspect.PENGIRIMAN: "[keputusan Anda: ganti ongkir / kompensasi / tidak ada]",
    Aspect.KEMASAN: "[keputusan Anda: kirim ulang / ganti rugi / tidak ada]",
    Aspect.KUALITAS_PRODUK: "[keputusan Anda: ganti barang / refund / tidak ada]",
    Aspect.UKURAN_VARIAN: "[keputusan Anda: tukar ukuran / refund / tidak ada]",
    Aspect.KESESUAIAN_DESKRIPSI: "[keputusan Anda: retur / refund / tidak ada]",
    Aspect.RASA_KUALITAS_MAKANAN: "[keputusan Anda: kirim ulang / refund / tidak ada]",
    Aspect.KELENGKAPAN: "[keputusan Anda: kirim kekurangannya / refund / tidak ada]",
    Aspect.PELAYANAN_PENJUAL: "[keputusan Anda: kompensasi / tidak ada]",
}

KALIMAT_SLOT = "Untuk pesanan ini, kami tawarkan {slot}."

# Kata yang boleh dirujuk ulang dari keluhan pembeli, DIKELOMPOKKAN PER ASPEK.
#
# Daftar tertutup adalah inti keamanannya: apa pun isi ulasan - termasuk umpatan, nama orang
# yang lolos redaksi, atau tuduhan yang belum tentu benar - tidak ada jalan bagi teks pembeli
# masuk ke dalam balasan yang terbit atas nama toko. Yang ditiru hanya TOPIKNYA.
#
# Pengelompokan per aspek datang belakangan, setelah satu daftar datar terbukti menghasilkan
# kalimat yang menabrak dirinya sendiri. Ulasan "harganya mahal untuk kualitas segini" masuk
# ke kartu kualitas produk, tetapi kata pertama yang cocok di daftar datar adalah "mahal" -
# hasilnya "mohon maaf kualitas barangnya belum seperti yang seharusnya, khususnya soal
# harganya". Dua topik dalam satu kalimat, dan pembaca yang menerimanya tahu persis bahwa
# yang menulisnya tidak membaca ulasannya.
#
# Kata yang sah untuk beberapa aspek ditulis ulang di tiap kelompoknya, bukan dibagi lewat
# daftar bersama: "sobek" berarti kemasan yang sobek pada kartu kemasan dan barang yang sobek
# pada kartu kualitas, dan frasa rujukannya memang harus berbeda.
KATA_RUJUKAN: dict[Aspect, dict[str, str]] = {
    Aspect.PENGIRIMAN: {
        "telat": "keterlambatannya",
        "lambat": "lambatnya proses pengiriman",
        "lama": "lamanya menunggu",
        "belum sampai": "paket yang belum sampai",
        "hilang": "paket yang tidak sampai",
    },
    Aspect.KEMASAN: {
        "penyok": "kemasan yang penyok",
        "sobek": "kemasan yang sobek",
        "robek": "kemasan yang robek",
        "bocor": "kebocorannya",
        "rusak": "kondisi kemasannya",
        "kotor": "kondisinya yang kotor",
        "asal": "cara pengemasannya",
    },
    Aspect.KUALITAS_PRODUK: {
        "rusak": "kondisi barangnya",
        "pecah": "barang yang pecah",
        "sobek": "barang yang sobek",
        "robek": "barang yang robek",
        "bolong": "barang yang bolong",
        "lepas": "jahitan yang lepas",
        "jahitan": "kerapian jahitannya",
        "tipis": "ketebalan bahannya",
        "luntur": "warnanya yang luntur",
        "cacat": "cacat pada barangnya",
        "kotor": "kondisinya yang kotor",
    },
    # Kata ukuran sendiri ("kekecilan", "sempit") sengaja TIDAK ada di sini. Kalimat pengakuan
    # aspek ini sudah berbunyi "ukuran yang Kakak terima tidak sesuai perkiraan"; menambahkan
    # "khususnya soal ukurannya" di belakangnya menghasilkan kalimat yang mengulang dirinya
    # sendiri, dan pengulangan itu persis yang membuat balasan terbaca sebagai tempelan.
    # Yang tersisa hanyalah rujukan yang benar-benar menambah keterangan.
    Aspect.UKURAN_VARIAN: {
        "salah warna": "warna yang dikirim",
        "salah kirim": "varian yang salah dikirim",
        "warna": "varian warnanya",
        "model": "model yang dikirim",
    },
    # Alasan yang sama: "tidak sesuai" dan "berbeda" adalah nama aspek ini diucapkan ulang.
    # Yang bernilai adalah menyebut DI MANA bedanya terlihat.
    Aspect.KESESUAIAN_DESKRIPSI: {
        "foto": "perbedaannya dengan foto di halaman produk",
        "gambar": "perbedaannya dengan gambar di halaman produk",
        "warna": "warna yang berbeda dari keterangan",
        "bahan": "bahan yang berbeda dari keterangan",
        "ukuran": "ukuran yang berbeda dari keterangan",
    },
    Aspect.PELAYANAN_PENJUAL: {
        "tidak dibalas": "chat yang tidak terbalas",
        "tidak di bales": "chat yang tidak terbalas",
        "tidak dibales": "chat yang tidak terbalas",
        "lambat": "lambatnya balasan kami",
        "lama": "lamanya menunggu balasan",
        "jutek": "cara kami menanggapi",
        "ketus": "cara kami menanggapi",
    },
    Aspect.HARGA_VALUE: {
        "mahal": "harganya",
        "kemahalan": "harganya",
        "tidak sepadan": "kesepadanan harga dan isinya",
    },
    Aspect.RASA_KUALITAS_MAKANAN: {
        "basi": "kondisi produknya",
        "expired": "tanggal kedaluwarsanya",
        "kadaluarsa": "tanggal kedaluwarsanya",
        "hambar": "rasanya",
        "asin": "rasanya",
        "pahit": "rasanya",
    },
    Aspect.KELENGKAPAN: {
        "tidak lengkap": "kelengkapan isinya",
        "kurang": "kekurangannya",
        "hilang": "bagian yang hilang",
    },
    Aspect.KEASLIAN: {
        "palsu": "keaslian barangnya",
        "kw": "keaslian barangnya",
        "tiruan": "keaslian barangnya",
    },
    Aspect.KEMUDAHAN_PENGGUNAAN: {
        "ribet": "cara pemakaiannya",
        "susah": "cara pemakaiannya",
        "sulit": "cara pemakaiannya",
        "bingung": "kejelasan petunjuknya",
    },
}

_KATA = re.compile(r"[a-z]+")


def _varian(review_id: str, slot: str, jumlah: int) -> int:
    """Pilih varian frasa secara deterministik dari review_id.

    Nama slot ikut di-hash supaya sapaan, pengakuan, dan penutup tidak selalu jatuh pada
    indeks yang sama - tanpa itu "varian 3" berarti tiga kalimat yang selalu muncul bersama,
    dan bank frasanya efektif menyusut menjadi tiga balasan tetap.
    """
    if jumlah <= 1:
        return 0
    digest = hashlib.sha256(f"{review_id}|{slot}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % jumlah


def _rujukan(teks: str, aspect: Aspect) -> str | None:
    """Cari satu kata dari daftar aspek INI yang benar-benar ada di keluhannya.

    Dibatasi pada aspek kartunya, bukan seluruh daftar: ulasan kerap menyinggung beberapa hal
    sekaligus, dan kata pertama yang cocok belum tentu kata yang membuat ulasan ini masuk ke
    kartu ini.

    Mengembalikan None bila tidak ada yang cocok, dan itu hasil yang sah: balasannya tetap
    terbit tanpa kalimat rujukan, sedikit lebih umum tetapi tidak keliru. Menebak topik dari
    ulasan yang tidak menyebut satu pun kata yang dikenali akan menghasilkan balasan yang
    membicarakan hal yang tidak dikeluhkan siapa pun.
    """
    daftar = KATA_RUJUKAN.get(aspect)
    if not daftar:
        return None
    lowered = teks.lower()
    kata = set(_KATA.findall(lowered))
    # Frasa panjang lebih dulu: "tidak sesuai" harus menang atas "sesuai", dan "salah warna"
    # atas "warna". Tanpa pengurutan ini hasilnya bergantung pada urutan penulisan daftar.
    for kunci in sorted(daftar, key=len, reverse=True):
        cocok = kunci in lowered if " " in kunci else kunci in kata
        if cocok:
            return daftar[kunci]
    return None


def _sudah_disebut(rujukan: str, pengakuan: str) -> bool:
    """True bila kalimat pengakuan sudah memuat inti rujukannya.

    Bank frasa punya tiga varian pengakuan per aspek, dan sebagian menyebut hal yang sama
    dengan rujukannya sementara sebagian tidak - "mohon maaf atas KETERLAMBATAN pengiriman"
    versus "pesanan Kakak sampai lebih lama dari yang seharusnya". Menempelkan rujukan pada
    varian pertama menghasilkan "atas keterlambatan pengiriman, khususnya soal
    keterlambatannya", dan pengulangan seperti itu adalah tanda paling khas balasan tempelan.

    Yang diperiksa kata TERAKHIR rujukannya - di situlah kata pembedanya berada ("kemasan yang
    PENYOK", "ukuran yang KEBESARAN"). Dicocokkan dengan potongan lima huruf pertama supaya
    imbuhan tidak meloloskannya: "keterlambatannya" dan "keterlambatan" sama-sama "keter".
    """
    kata = _KATA.findall(rujukan.lower())
    if not kata:
        return False
    inti = kata[-1]
    return len(inti) >= 5 and inti[:5] in pengakuan.lower()


def build_reply_draft(
    citation: EvidenceCitation,
    aspect: Aspect,
    severity: Severity,
    clause: str | None = None,
) -> ReplyDraft:
    """Susun satu draf balasan. Deterministik terhadap (review_id, aspect, severity)."""
    rid = citation.review_id
    sapaan = SAPAAN[_varian(rid, "sapaan", len(SAPAAN))]

    pengakuan_bank = PENGAKUAN.get(aspect) or PENGAKUAN[Aspect.KUALITAS_PRODUK]
    i_akui = _varian(rid, "akui", len(pengakuan_bank))
    pengakuan = pengakuan_bank[i_akui]

    # Rujukan dicari pada KLAUSA negatifnya bila tersedia, bukan pada seluruh ulasan. Ulasan
    # campuran ("bagus sih, cuma jahitannya lepas") memuat kata dari kedua sisi, dan mencari di
    # seluruh teks bisa menangkap kata dari bagian yang justru memuji.
    rujukan = _rujukan(clause or citation.quote, aspect)
    if rujukan and not _sudah_disebut(rujukan, pengakuan):
        pengakuan = pengakuan.rstrip(".") + f", khususnya soal {rujukan}."

    langkah_bank = LANGKAH.get(aspect) or LANGKAH[Aspect.KUALITAS_PRODUK]
    i_langkah = _varian(rid, "langkah", len(langkah_bank))
    langkah = langkah_bank[i_langkah]

    penutup = PENUTUP[_varian(rid, "tutup", len(PENUTUP))]

    kalimat = [sapaan, pengakuan, langkah]
    slots: list[str] = []
    slot = SLOT_KEPUTUSAN.get(aspect)
    if slot is not None and severity is Severity.TINGGI:
        kalimat.append(KALIMAT_SLOT.format(slot=slot))
        slots.append(slot)
    kalimat.append(penutup)

    return ReplyDraft(
        review_id=rid,
        quote=citation.quote,
        rating=citation.rating,
        aspect=aspect,
        severity=severity,
        draft=" ".join(kalimat),
        decision_slots=slots,
        template_id=f"{aspect.value}.{severity.value}.{i_akui}{i_langkah}",
    )


def build_reply_drafts(
    card: ActionCard,
    clauses_by_review: dict[str, str] | None = None,
    limit: int = MAX_DRAFTS_PER_CARD,
) -> list[ReplyDraft]:
    """Satu draf per ulasan pendukung kartu ini.

    Sumbernya `card.evidence_quotes`, bukan pencarian baru: kutipan itu SUDAH tersaring hanya
    berisi keluhan pada aspek kartu, dan sudah dibaca pengguna di layar. Menyusun balasan untuk
    ulasan yang tidak pernah ia lihat sebagai bukti akan terasa datang entah dari mana.
    """
    clauses = clauses_by_review or {}
    return [
        build_reply_draft(
            citation=c,
            aspect=card.aspect,
            severity=card.severity,
            clause=clauses.get(c.review_id),
        )
        for c in card.evidence_quotes[:limit]
    ]
