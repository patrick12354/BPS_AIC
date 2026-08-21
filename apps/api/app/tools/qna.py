"""QNA-01 - tanya jawab yang ter-ground pada ulasan pengguna (blueprint bagian 30.2).

Jawaban di sini **diekstraksi, bukan dikarang**. Setiap kalimat jawaban disusun dari angka yang
sudah dihitung tool lain, dan setiap jawaban wajib membawa kutipan aslinya. Ketika bukti tidak
ditemukan, sistem mengatakan tidak tahu - persis perilaku yang dijanjikan bagian 30.2.

Konsekuensinya jawaban terdengar seperti template. Itu pertukaran yang disengaja: pada produk
yang seluruh nilainya bersandar pada kepercayaan terhadap angka, jawaban yang enak dibaca tetapi
tidak dapat ditelusuri jauh lebih berbahaya daripada jawaban yang kaku.
"""

from __future__ import annotations

import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field

from ..schemas import (
    ActionCard,
    Aspect,
    AspectAggregate,
    Category,
    EvidenceCitation,
    QnAResponse,
)

# Kata kunci untuk MENGARAHKAN pertanyaan ke aspek - bukan untuk melabeli ulasan. Pelabelan
# ditangani model; daftar ini hanya menebak topik yang sedang ditanyakan pengguna.
QUESTION_KEYWORDS: dict[Aspect, list[str]] = {
    Aspect.PENGIRIMAN: ["kirim", "pengiriman", "ongkir", "kurir", "sampai", "telat", "lama"],
    Aspect.KEMASAN: ["kemasan", "packing", "bungkus", "dus", "box"],
    Aspect.KUALITAS_PRODUK: ["kualitas", "mutu", "rusak", "cacat", "awet", "bagus"],
    Aspect.HARGA_VALUE: ["harga", "mahal", "murah", "worth", "value"],
    Aspect.PELAYANAN_PENJUAL: ["pelayanan", "penjual", "seller", "respon", "admin", "cs"],
    Aspect.UKURAN_VARIAN: ["ukuran", "size", "varian", "warna", "model"],
    Aspect.KESESUAIAN_DESKRIPSI: ["deskripsi", "sesuai", "gambar", "foto", "beda"],
    Aspect.KEASLIAN: ["asli", "ori", "original", "palsu", "kw"],
    Aspect.RASA_KUALITAS_MAKANAN: ["rasa", "enak", "basi", "expired", "kadaluarsa"],
    Aspect.KELENGKAPAN: ["lengkap", "kurang", "hilang", "isi"],
    Aspect.KEMUDAHAN_PENGGUNAAN: ["mudah", "ribet", "susah", "pakai", "instruksi"],
}

MAX_SESSIONS = 50
SESSION_TTL_SECONDS = 60 * 60
MAX_CITATIONS = 3

# --------------------------------------------------------------------------------------
# Penjaga pertanyaan di luar domain
# --------------------------------------------------------------------------------------
# Retrieval SELALU mengembalikan tetangga terdekat, bahkan untuk pertanyaan yang datanya tidak
# mungkin menjawab. "Berapa harga saham Telkom besok?" mengenai kata "harga", lalu terjawab
# dengan statistik harga produk - lengkap dengan kutipan, sehingga tampak sah. Kegagalan seperti
# itu lebih berbahaya daripada menolak, karena pengguna tidak punya cara menyadarinya.
#
# Penjaganya: berapa banyak kata isi pertanyaan yang sama sekali asing bagi data pengguna.
# Diukur pada korpus contoh (120 ulasan, 467 kata unik) atas 14 pertanyaan - pertanyaan yang
# wajar berhenti di 0.50, pertanyaan di luar domain mulai dari 0.75. Ambang 0.65 duduk di celah
# itu dengan jarak ke kedua sisi.
MAX_UNKNOWN_RATIO = 0.65

# Kata tata bahasa tidak membawa topik, sehingga tidak boleh ikut dihitung.
GRAMMAR_WORDS = {
    "apa", "apakah", "bagaimana", "kenapa", "mengapa", "berapa", "yang", "dan", "itu", "ini",
    "dari", "untuk", "dengan", "saya", "ada", "pada", "tentang", "soal", "paling", "sering",
    "banyak", "mana", "atau", "bisa", "dapat", "juga", "lebih", "kurang", "saja", "sudah",
    "belum", "akan", "harus", "semua", "setiap", "antara", "tersebut", "dalam", "adalah",
    "seperti", "bagi", "oleh", "kalau", "jika", "tapi", "tetapi",
}

# Kosakata untuk BERTANYA tentang analisis. Kata-kata ini jarang muncul di dalam ulasan itu
# sendiri - pembeli menulis "paketnya telat", bukan "aspek pengiriman bersentimen negatif" -
# sehingga tanpa daftar ini pertanyaan analitis yang wajar akan ikut tertolak.
#
# Tiga rumpun ditambahkan setelah audit, karena masing-masing menutup satu pertanyaan yang
# sepenuhnya wajar tetapi tertolak penjaga domain:
#
#   aksi        "apa yang harus saya perbaiki duluan?" - pertanyaan pertama yang diajukan
#               hampir setiap pemilik toko, dan satu-satunya isi kata yang tersisa setelah kata
#               tata bahasa dibuang adalah "perbaiki" dan "duluan". Keduanya asing bagi korpus
#               ulasan (pembeli tidak menulis "perbaiki"), sehingga rasio tak dikenalnya 1,0.
#   pujian      "apa yang paling disukai pembeli?" - simetri dari "apa yang dikeluhkan", dan
#               separuh nilai produk ada di sisi ini (bagian OPP-01).
#   kuantitatif "berapa persen ulasan yang mengeluh?" - angkanya sudah dihitung, hanya tidak
#               pernah sampai karena pertanyaannya berhenti di gerbang.
ANALYSIS_WORDS = [
    "keluhan", "masalah", "aspek", "pembeli", "pelanggan", "ulasan", "review", "toko", "produk",
    "barang", "komplain", "positif", "negatif", "puas", "kecewa", "tren", "dikeluhkan",
    "pendapat", "penilaian", "rating", "bintang", "sentimen", "dipuji", "muncul",
    # aksi
    "perbaiki", "benahi", "atasi", "kerjakan", "dulu", "duluan", "prioritas", "utama",
    "penting", "fokus", "langkah", "saran", "rekomendasi", "tindakan", "solusi", "mulai",
    # pujian
    "disukai", "suka", "kelebihan", "keunggulan", "unggul", "pujian", "memuji", "senang",
    # kuantitatif
    "persen", "persentase", "proporsi", "rasio", "jumlah", "total", "seberapa",
]

_PREFIXES = ("meng", "meny", "mem", "men", "ber", "ter", "peng", "pem", "per", "di", "ke", "se",
             "me", "pe")
_SUFFIXES = ("kannya", "annya", "nya", "kan", "an", "i")


def _stem(word: str) -> str:
    """Pemenggal imbuhan seadanya - cukup untuk MENCOCOKKAN kosakata, bukan analisis morfologi.

    Tanpa ini "dikeluhkan" pada pertanyaan tidak akan bertemu "keluhan" pada daftar di atas,
    dan pertanyaan yang sepenuhnya wajar akan tertolak.

    Peluluhan bunyi tidak ditangani: "pengiriman" menjadi "irim", bukan "kirim", karena huruf
    yang luluh tidak dapat dipulihkan tanpa menebak ("mengambil" berasal dari "ambil", bukan
    "kambil"). Yang dibutuhkan penjaga domain hanyalah KONSISTENSI - kata yang sama pada
    pertanyaan dan pada ulasan menghasilkan bentuk yang sama - sehingga kekeliruan linguistik
    ini tidak merugikan. Efeknya hanya sebagian bentuk berimbuhan tidak bertemu bentuk dasarnya,
    dan itu membuat penjaga sedikit lebih mudah menolak, arah kegagalan yang memang diinginkan.
    """
    for prefix in _PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            word = word[len(prefix):]
            break
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word


_ANALYSIS_STEMS = {_stem(w) for w in ANALYSIS_WORDS}


def is_out_of_domain(question: str, corpus_vocabulary: set[str]) -> bool:
    """True bila sebagian besar isi pertanyaan tidak ada dalam data pengguna."""
    content = [
        _stem(w)
        for w in re.findall(r"[a-z]{3,}", question.lower())
        if w not in GRAMMAR_WORDS
    ]
    if not content:
        return True
    unknown = [w for w in content if w not in corpus_vocabulary and w not in _ANALYSIS_STEMS]
    return len(unknown) / len(content) > MAX_UNKNOWN_RATIO


@dataclass
class QnAContext:
    """Bahan tindak lanjut untuk satu analisis. Disimpan di memori saja, tidak pernah ke disk.

    Namanya menyebut Q&A karena itulah pemakai pertamanya, dan tetap begitu supaya perubahan
    ini tidak merembet ke seluruh pemanggilnya. Isinya sekarang lebih luas: apa pun yang
    dibutuhkan permintaan LANJUTAN atas satu analisis - jawaban pertanyaan, jejak perhitungan,
    draf balasan - hidup di objek yang sama.

    Satu wadah, bukan tiga, dan itu bukan penghematan kode melainkan sifat privasi yang
    diinginkan: seluruh sisa satu analisis kedaluwarsa pada satu waktu yang sama, lewat satu
    kebijakan yang sama (bagian 37.1). Tiga cache dengan tiga TTL adalah tiga peluang untuk
    salah satunya tertinggal lebih lama dari yang dijanjikan di layar pertama.
    """

    index: object | None
    aggregates: list[AspectAggregate]
    total_reviews: int
    created_at: float = field(default_factory=time.time)
    vocabulary: set[str] = field(default_factory=set)
    # Kartu aksi yang sudah tersusun untuk analisis ini. Dibawa ke sini supaya pertanyaan
    # "apa yang harus saya perbaiki duluan?" dijawab oleh URUTAN YANG SAMA yang dibaca
    # pengguna di laporan. Menjawabnya dengan aspek berkeluhan-terbanyak akan menghasilkan
    # jawaban yang kadang berbeda dari kartu nomor satu di layar - skor prioritas bukan
    # sekadar frekuensi - dan dua urutan berbeda dari satu sistem menghapus kepercayaan
    # pada keduanya.
    actions: list[ActionCard] = field(default_factory=list)
    # Jumlah ULASAN yang memuat keluhan (bukan jumlah sebutan). Dipakai jawaban kuantitatif
    # supaya persentasenya punya penyebut yang benar; lihat catatan di AnalysisSummary.
    reviews_with_complaint: int | None = None
    # Jejak perhitungan per action_id (fitur S2). Dibangun saat analisis, bukan saat diminta:
    # `predictions` sudah dilepas ke sampah begitu request analisis selesai, dan menghidupkan
    # ulangnya berarti menjalankan inferensi kedua atas data yang sudah tidak ada.
    traces: dict[str, object] = field(default_factory=dict)
    # Klausa negatif per (review_id, aspect) - bahan kalimat pengakuan pada draf balasan.
    # Kuncinya tuple supaya satu ulasan yang mengeluhkan dua aspek tidak saling menimpa.
    negative_clauses: dict[tuple[str, str], str] = field(default_factory=dict)
    # Keterangan sesi yang dibutuhkan arsip (L5). Kategori dan rentang tanggal tidak ada
    # di dalam agregat, padahal keduanya menentukan apakah dua arsip layak dibandingkan.
    category: Category = Category.OTHER
    period_start: object | None = None
    period_end: object | None = None

    def __post_init__(self) -> None:
        # Kosakata diambil dari teks yang SUDAH diredaksi (index dibangun dari clean_text),
        # sehingga tidak ada PII yang ikut tersimpan di sini.
        if not self.vocabulary and self.index is not None:
            texts = [item.text for item in getattr(self.index, "items", [])]
            self.vocabulary = {
                _stem(w) for t in texts for w in re.findall(r"[a-z]{3,}", t.lower())
            }


class QnAStore:
    """Cache sesi terbatas: paling banyak 50 analisis dan kedaluwarsa dalam satu jam.

    Batas ini bukan optimasi memori, melainkan bagian dari janji privasi di layar pertama:
    data pengguna hidup selama sesi, lalu hilang dengan sendirinya (bagian 37.1).
    """

    def __init__(self, max_sessions: int = MAX_SESSIONS, ttl: int = SESSION_TTL_SECONDS):
        self._items: OrderedDict[str, QnAContext] = OrderedDict()
        self._max = max_sessions
        self._ttl = ttl

    def put(self, analysis_id: str, context: QnAContext) -> None:
        self._evict_expired()
        self._items[analysis_id] = context
        self._items.move_to_end(analysis_id)
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def get(self, analysis_id: str) -> QnAContext | None:
        self._evict_expired()
        return self._items.get(analysis_id)

    def _evict_expired(self) -> None:
        cutoff = time.time() - self._ttl
        for key in [k for k, v in self._items.items() if v.created_at < cutoff]:
            del self._items[key]


def _detect_aspect(question: str) -> Aspect | None:
    lowered = question.lower()
    best, best_hits = None, 0
    for aspect, keywords in QUESTION_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        if hits > best_hits:
            best, best_hits = aspect, hits
    return best


# --------------------------------------------------------------------------------------
# Maksud pertanyaan
# --------------------------------------------------------------------------------------
# Sebelum ini hanya ada SATU bentuk jawaban: "berapa banyak yang mengeluh". Akibatnya
# pertanyaan tentang pujian dijawab dengan daftar keluhan, dan pertanyaan tentang apa yang
# harus dikerjakan lebih dulu dijawab dengan statistik yang tidak menyebut satu pun tindakan.
# Bentuk jawabannya benar secara angka dan salah sebagai jawaban.
#
# Dicocokkan pada teks pertanyaan apa adanya, bukan pada stem: frasa seperti "lebih dulu"
# terdiri dari dua kata yang masing-masing tidak berarti apa-apa. Pemenggal imbuhan di atas
# hanya bertugas menjaga gerbang domain, bukan memahami pertanyaan.

INTENT_PRIORITAS = "prioritas"
INTENT_POSITIF = "positif"
INTENT_KUANTITATIF = "kuantitatif"
INTENT_UMUM = "umum"

_POLA_PRIORITAS = (
    "duluan", "lebih dulu", "paling dulu", "pertama kali", "langkah pertama", "mulai dari mana",
    "prioritas", "diprioritaskan", "paling penting", "paling utama", "harus saya perbaiki",
    "harus diperbaiki", "perlu diperbaiki", "harus saya kerjakan", "harus dikerjakan",
    "saya benahi", "apa yang harus", "rekomendasi", "saran", "sebaiknya saya",
)

_POLA_POSITIF = (
    "dipuji", "memuji", "pujian", "disukai", "disuka", "paling suka", "kelebihan",
    "keunggulan", "paling bagus", "paling baik", "yang bagus", "yang positif", "hal positif",
    "sisi positif", "paling puas", "senang",
)

# Pengingkaran yang membalik arti frasa pujian. Tanpa ini "apa yang tidak disukai pembeli?"
# terbaca sebagai pertanyaan pujian dan dijawab dengan aspek yang paling banyak dipuji -
# kebalikan persis dari yang ditanyakan, dan justru pada bentuk pertanyaan yang wajar.
_POLA_INGKAR = (
    "tidak dipuji", "tidak disukai", "tidak disuka", "tidak suka", "tidak puas", "kurang puas",
    "kurang suka", "tidak bagus", "tidak baik", "tidak senang", "belum puas",
)

_POLA_KUANTITATIF = (
    "berapa persen", "berapa %", "persentase", "berapa banyak", "berapa jumlah", "ada berapa",
    "berapa ulasan", "seberapa banyak", "proporsi", "rasio", "berapa yang",
)


def _detect_intent(question: str) -> str:
    """Tentukan BENTUK jawaban yang diminta, bukan topiknya.

    Urutannya bermakna dan tidak boleh diacak. Pertanyaan prioritas menang lebih dulu karena
    ia meminta satu tindakan, bukan satu angka - "berapa yang harus saya perbaiki duluan"
    tetap dijawab dengan kartu prioritas, bukan dengan hitungan. Pujian mendahului kuantitatif
    dengan alasan yang sama terbalik: "berapa persen yang memuji pengiriman" memang meminta
    angka, dan jawaban pujian di bawah memang membawa angkanya sendiri.
    """
    lowered = question.lower()
    if any(p in lowered for p in _POLA_PRIORITAS):
        return INTENT_PRIORITAS
    if any(p in lowered for p in _POLA_POSITIF) and not any(p in lowered for p in _POLA_INGKAR):
        return INTENT_POSITIF
    if any(p in lowered for p in _POLA_KUANTITATIF):
        return INTENT_KUANTITATIF
    return INTENT_UMUM


def _priority_sentence(
    actions: list[ActionCard], aggregates: list[AspectAggregate], total: int
) -> str:
    """Jawaban untuk "apa yang harus saya perbaiki duluan?".

    Diambil dari kartu aksi teratas, bukan dihitung ulang di sini - satu urutan prioritas
    untuk seluruh produk (ADR-011).
    """
    if actions:
        top = actions[0]
        kalimat = (
            f"Yang perlu dikerjakan lebih dulu: {top.title}. {top.one_line_summary}. "
            f"Skor prioritasnya {top.priority_score} dengan urgensi {top.urgency.value}, "
            f"tertinggi di antara {len(actions)} rekomendasi yang tersusun. "
            f"Dasarnya: {top.priority_reasoning}"
        )
        if len(actions) > 1:
            berikut = ", lalu ".join(a.title.lower() for a in actions[1:3])
            kalimat += f" Sesudah itu: {berikut}."
        return kalimat

    # Tidak ada kartu aksi berarti tidak ada keluhan yang cukup untuk diprioritaskan. Itu
    # jawaban yang sah dan harus diucapkan, bukan diisi dengan aspek sembarang.
    berkeluhan = [a for a in aggregates if a.negative_count]
    if not berkeluhan:
        return (
            f"Dari {total} ulasan, tidak ada aspek yang cukup sering dikeluhkan untuk "
            f"dijadikan prioritas perbaikan."
        )
    top = max(berkeluhan, key=lambda a: a.negative_count)
    return (
        f"Rekomendasi berperingkat belum tersusun untuk analisis ini, tetapi keluhan "
        f"terbanyak ada pada {top.aspect.value.replace('_', ' ')} - {top.negative_count} "
        f"dari {total} ulasan."
    )


def _positive_sentence(
    aggregates: list[AspectAggregate], total: int, aspect: Aspect | None = None
) -> str:
    """Jawaban untuk pertanyaan tentang apa yang DIPUJI - bukan cerminan dari sisi keluhan."""
    by_aspect = {a.aspect: a for a in aggregates}
    if aspect is not None and aspect in by_aspect:
        agg = by_aspect[aspect]
        name = agg.aspect.value.replace("_", " ")
        if agg.positive_count == 0:
            return (
                f"Dari {total} ulasan, {agg.total_mentions} membahas {name} dan tidak satu pun "
                f"menyebutnya secara positif."
            )
        pct = agg.positive_count / agg.total_mentions
        return (
            f"Dari {total} ulasan, {agg.positive_count} memuji {name} - {pct:.0%} dari "
            f"{agg.total_mentions} yang membahasnya."
        )

    dipuji = [a for a in aggregates if a.positive_count]
    if not dipuji:
        return f"Dari {total} ulasan, belum ada aspek yang disebut secara positif."
    urut = sorted(dipuji, key=lambda a: a.positive_count, reverse=True)
    top = urut[0]
    pct = top.positive_count / top.total_mentions
    kalimat = (
        f"Dari {total} ulasan, yang paling sering dipuji adalah "
        f"{top.aspect.value.replace('_', ' ')} - {top.positive_count} sebutan positif, "
        f"{pct:.0%} dari {top.total_mentions} yang membahasnya."
    )
    if len(urut) > 1:
        lain = ", ".join(
            f"{a.aspect.value.replace('_', ' ')} ({a.positive_count})" for a in urut[1:3]
        )
        kalimat += f" Menyusul: {lain}."
    return kalimat


def _quantitative_sentence(
    aggregates: list[AspectAggregate],
    total: int,
    aspect: Aspect | None = None,
    reviews_with_complaint: int | None = None,
) -> str:
    """Jawaban untuk pertanyaan berapa dan berapa persen.

    Penyebutnya disebut eksplisit di setiap kalimat. Persentase tanpa penyebut adalah cara
    paling mudah menyesatkan pembaca sendiri: "30% mengeluh" berarti dua hal yang sangat
    berbeda kalau dihitung dari seluruh ulasan atau dari yang membahas aspek itu saja.
    """
    by_aspect = {a.aspect: a for a in aggregates}
    if aspect is not None and aspect in by_aspect:
        agg = by_aspect[aspect]
        name = agg.aspect.value.replace("_", " ")
        share = agg.total_mentions / total if total else 0.0
        pct_neg = agg.negative_count / agg.total_mentions if agg.total_mentions else 0.0
        return (
            f"{agg.total_mentions} dari {total} ulasan ({share:.0%}) membahas {name}. "
            f"Di antaranya {agg.negative_count} berisi keluhan ({pct_neg:.0%} dari yang "
            f"membahas, {agg.negative_count / total if total else 0:.0%} dari seluruh ulasan) "
            f"dan {agg.positive_count} positif."
        )

    berkeluhan = [a for a in aggregates if a.negative_count]
    if reviews_with_complaint is not None and total:
        pct = reviews_with_complaint / total
        kalimat = (
            f"{reviews_with_complaint} dari {total} ulasan ({pct:.0%}) memuat setidaknya satu "
            f"keluhan, tersebar di {len(berkeluhan)} aspek."
        )
    else:
        kalimat = (
            f"Dari {total} ulasan, {len(berkeluhan)} aspek memuat keluhan."
        )
    if berkeluhan:
        top = max(berkeluhan, key=lambda a: a.negative_count)
        pct_top = top.negative_count / total if total else 0.0
        kalimat += (
            f" Yang terbanyak {top.aspect.value.replace('_', ' ')}: {top.negative_count} "
            f"ulasan ({pct_top:.0%} dari seluruhnya)."
        )
    return kalimat


def _aspect_sentence(aggregate: AspectAggregate, total: int) -> str:
    name = aggregate.aspect.value.replace("_", " ")
    pct_neg = aggregate.negative_count / aggregate.total_mentions if aggregate.total_mentions else 0
    if aggregate.negative_count == 0:
        return (
            f"Dari {total} ulasan, {aggregate.total_mentions} membahas {name} dan tidak ada yang "
            f"berisi keluhan ({aggregate.positive_count} di antaranya positif)."
        )
    return (
        f"Dari {total} ulasan, {aggregate.total_mentions} membahas {name}. "
        f"{aggregate.negative_count} di antaranya berisi keluhan ({pct_neg:.0%}), "
        f"{aggregate.positive_count} positif."
    )


def _overall_sentence(aggregates: list[AspectAggregate], total: int) -> str:
    complained = [a for a in aggregates if a.negative_count]
    if not complained:
        return f"Dari {total} ulasan, tidak ditemukan aspek yang menonjol sebagai keluhan."
    top = max(complained, key=lambda a: a.negative_count)
    return (
        f"Dari {total} ulasan, keluhan terbanyak ada pada "
        f"{top.aspect.value.replace('_', ' ')} - {top.negative_count} ulasan."
    )


def answer_question(context: QnAContext, question: str) -> QnAResponse:
    """Jawab pertanyaan hanya dari data analisis yang bersangkutan."""
    if context.index is None:
        return QnAResponse(
            answer="", citations=[], no_answer=True,
            no_answer_reason=(
                "Pencarian bukti sedang tidak aktif, sehingga jawaban tidak dapat dibuktikan "
                "dengan kutipan. Angka pada hasil analisis tetap lengkap."
            ),
        )

    if is_out_of_domain(question, context.vocabulary):
        return QnAResponse(
            answer="", citations=[], no_answer=True,
            no_answer_reason=(
                "Pertanyaan ini membahas hal yang tidak ada di dalam ulasan Anda, sehingga "
                "tidak dapat dijawab dari data ini. Sistem hanya menjawab pertanyaan seputar "
                "isi ulasan yang Anda unggah."
            ),
        )

    aspect = _detect_aspect(question)
    intent = _detect_intent(question)

    # Kutipan mengikuti BENTUK jawabannya, bukan sekadar topiknya.
    #
    # Pertanyaan prioritas dijawab oleh kartu aksi teratas, jadi buktinya adalah bukti kartu
    # itu - sudah tersaring hanya berisi keluhan, dan sudah dibaca pengguna di laporan. Dua
    # kumpulan kutipan berbeda untuk satu klaim yang sama membuat keduanya terlihat sembarang.
    #
    # Pertanyaan pujian meminta kutipan pujian. Tanpa `positive_only`, pertanyaan "apa yang
    # paling disukai pembeli" dijawab kalimat pujian yang dibuktikan oleh tiga keluhan - dan
    # bukti yang membantah klaimnya sendiri lebih merusak daripada tidak ada bukti.
    citations: list[EvidenceCitation] = []
    if intent == INTENT_PRIORITAS and context.actions:
        citations = list(context.actions[0].evidence_quotes[:MAX_CITATIONS])
        aspect = context.actions[0].aspect
    if not citations:
        citations = context.index.retrieve(
            query=question,
            aspect=aspect,
            top_k=MAX_CITATIONS,
            positive_only=intent == INTENT_POSITIF,
        )

    # Tanpa kutipan, tidak ada yang dapat diperiksa pengguna - dan jawaban yang tidak dapat
    # diperiksa adalah persis yang produk ini hindari.
    if not citations:
        return QnAResponse(
            answer="", citations=[], no_answer=True,
            no_answer_reason=(
                "Tidak ada ulasan Anda yang cukup relevan dengan pertanyaan ini, sehingga "
                "jawabannya tidak dapat dibuktikan. Coba tanyakan hal lain yang memang dibahas "
                "pembeli Anda."
            ),
        )

    by_aspect = {a.aspect: a for a in context.aggregates}
    if intent == INTENT_PRIORITAS:
        answer = _priority_sentence(context.actions, context.aggregates, context.total_reviews)
    elif intent == INTENT_POSITIF:
        answer = _positive_sentence(context.aggregates, context.total_reviews, aspect)
    elif intent == INTENT_KUANTITATIF:
        answer = _quantitative_sentence(
            context.aggregates, context.total_reviews, aspect, context.reviews_with_complaint
        )
    elif aspect is not None and aspect in by_aspect:
        answer = _aspect_sentence(by_aspect[aspect], context.total_reviews)
    else:
        answer = _overall_sentence(context.aggregates, context.total_reviews)

    return QnAResponse(
        answer=f"{answer} Kutipan pendukungnya ada di bawah.",
        citations=citations,
        no_answer=False,
    )
