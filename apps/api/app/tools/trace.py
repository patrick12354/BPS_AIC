"""build_action_trace() - rantai perhitungan satu Action Card (fitur S2, "Mode Juri").

Tidak ada satu pun angka baru di berkas ini. Semua yang dirangkai di sini sudah dihitung tool
lain dan sudah ada di dalam memori proses; yang belum ada adalah JALAN KELUARNYA.

Kenapa itu penting. Klaim inti produk berbunyi "angka kami tidak dikarang" - dan sampai
sekarang klaim itu hanya dapat dipercaya, tidak dapat diperiksa. Prediksi per klausa hidup di
`TextPrediction` dan tidak pernah keluar dari backend. Komponen skor hidup di
`PriorityResult.factors` dan berhenti di sana; yang sampai ke pengguna hanya kalimat
`priority_reasoning` yang sudah jadi. Kutipan tampil di kartu tanpa hubungan terlihat dengan
angka di atasnya. Tiga potongan yang, satu per satu, tidak membuktikan apa pun.

Dirangkai berurutan, ketiganya menjadi hal yang berbeda: seorang pembaca skeptis dapat
menelusuri sendiri dari klausa mentah "paketnya telat seminggu" sampai ke angka 34,8 di pojok
kartu, dan berhenti di titik mana pun yang ia curigai. Perbedaan antara "percayalah" dan
"periksa sendiri" adalah seluruh perbedaan yang ingin dibuat produk ini.

Payload normal tidak membawanya. Trace hanya terbit saat diminta (`?trace=1` atau endpoint
jejak), karena yang memintanya sedang memeriksa, bukan sedang bekerja - dan orang yang sedang
bekerja tidak perlu membayar ongkos payload untuk sesuatu yang tidak ia buka.
"""

from __future__ import annotations

from ..schemas import (
    ActionTrace,
    Aspect,
    AspectAggregate,
    AspectPrediction,
    EvidenceCitation,
    Sentiment,
    TextPrediction,
    TraceClause,
    TraceFactor,
)
from .priority import (
    BENCHMARK_GAP_SCALE,
    DEFAULT_W_BENCHMARK,
    DEFAULT_W_RECENCY,
    MIN_REVIEWS_FOR_HIGH_URGENCY,
    PriorityResult,
)

# Klausa yang dibawa ke dalam trace dibatasi. Aspek yang disebut 300 kali menghasilkan payload
# beberapa ratus kilobyte kalau seluruhnya diangkut, dan tidak ada manusia yang memeriksa 300
# baris satu per satu. Yang diperiksa adalah beberapa contoh, lalu jumlah totalnya - jadi
# `clauses_total` di bawah bukan hiasan, ia yang membuat pemotongan ini jujur.
MAX_TRACE_CLAUSES = 12

FORMULA = (
    "skor = frekuensi x keparahan x keyakinan x "
    f"(1 + {DEFAULT_W_RECENCY} x tren + {DEFAULT_W_BENCHMARK} x selisih_baseline) x 100"
)

_LABEL = {
    "frequency_norm": ("Frekuensi", "pengali inti"),
    "severity_norm": ("Keparahan", "pengali inti"),
    "confidence_norm": ("Keyakinan model", "pengali inti"),
    "recency_norm": ("Tren 30 hari", "modifier"),
    "benchmark_gap_norm": ("Selisih baseline", "modifier"),
}


def _explain(
    key: str, value: float, aggregate: AspectAggregate, total_reviews: int,
    calibrated: bool = False,
) -> str:
    """Terjemahkan satu angka menjadi kalimat yang dapat dihitung ulang pembacanya sendiri.

    Bukan penjelasan umum melainkan aritmetikanya: "0,1500 = 6 keluhan / 40 ulasan". Angka
    telanjang tidak dapat diperiksa - yang dapat diperiksa adalah cara ia terbentuk.
    """
    if key == "frequency_norm":
        return (
            f"{aggregate.negative_count} ulasan berkeluhan / {total_reviews} ulasan sesi ini"
        )
    if key == "severity_norm":
        return (
            f"keparahan tipikal '{aggregate.dominant_severity.value}' pada aspek ini; "
            f"diturunkan dari rating ulasan yang memuat keluhannya"
        )
    if key == "confidence_norm":
        if calibrated:
            return (
                "rata-rata probabilitas sentimen terkalibrasi pada klausa pendukung "
                "(temperature scaling, ECE dilaporkan di MODEL_CARD)"
            )
        return (
            "rata-rata keyakinan prediksi klausa. Nilai ini BELUM terkalibrasi (lihat "
            "docs/LIMITATIONS.md) - ia konstan untuk seluruh aspek, sehingga tidak mengubah "
            "urutan kartu"
        )
    if key == "recency_norm":
        return f"tren keluhan '{aggregate.trend.value}' dalam 30 hari terakhir"
    if key == "benchmark_gap_norm":
        if value == 0.0:
            return (
                "tidak ada dorongan dari baseline - entah tokonya tidak lebih buruk dari "
                f"rata-rata kategori, atau perbandingannya masih berstatus indikasi awal"
            )
        return (
            f"selisih terhadap baseline kategori, dinormalisasi terhadap "
            f"{BENCHMARK_GAP_SCALE * 100:.0f} poin persentase"
        )
    return ""


def _clauses_for(
    predictions: list[TextPrediction], aspect: Aspect
) -> tuple[list[TraceClause], int, int]:
    """Kumpulkan klausa yang benar-benar memicu aspek ini, keluhan lebih dulu.

    Urutannya disengaja: yang diperiksa pembaca skeptis adalah dasar KELUHANNYA, dan mengurut
    apa adanya akan menaruh sebutan positif di deretan atas hanya karena ulasannya kebetulan
    masuk lebih dulu.
    """
    negatif: list[TraceClause] = []
    lain: list[TraceClause] = []
    for prediction in predictions:
        item: AspectPrediction
        for item in prediction.predictions:
            if item.aspect is not aspect:
                continue
            baris = TraceClause(
                review_id=prediction.review_id,
                clause=item.source_sentence,
                aspect=item.aspect,
                sentiment=item.sentiment,
                severity=item.severity,
            )
            (negatif if item.sentiment is Sentiment.NEGATIF else lain).append(baris)

    total = len(negatif) + len(lain)
    return (negatif + lain)[:MAX_TRACE_CLAUSES], total, len(negatif)


def build_action_trace(
    action_id: str,
    aspect: Aspect,
    aggregate: AspectAggregate,
    priority: PriorityResult,
    predictions: list[TextPrediction],
    total_reviews: int,
    citations: list[EvidenceCitation] | None = None,
    calibrated: bool = False,
) -> ActionTrace:
    """Rangkai klausa, agregat, dan komponen skor menjadi satu rantai untuk satu kartu."""
    clauses, clauses_total, negatif_total = _clauses_for(predictions, aspect)

    factors = [
        TraceFactor(
            key=key,
            label=_LABEL[key][0],
            value=priority.factors.get(key, 0.0),
            explanation=_explain(
                key, priority.factors.get(key, 0.0), aggregate, total_reviews, calibrated
            ),
            role=_LABEL[key][1],
        )
        for key in _LABEL
        if key in priority.factors
    ]

    core = (
        priority.factors.get("frequency_norm", 0.0)
        * priority.factors.get("severity_norm", 0.0)
        * priority.factors.get("confidence_norm", 0.0)
    )
    modifier = (
        1.0
        + DEFAULT_W_RECENCY * priority.factors.get("recency_norm", 0.0)
        + DEFAULT_W_BENCHMARK * priority.factors.get("benchmark_gap_norm", 0.0)
    )

    # Catatan hanya muncul saat memang berlaku. Penafian yang tampil di setiap trace berhenti
    # dibaca setelah trace kedua, dan yang hilang bersamanya adalah yang benar-benar penting.
    notes: list[str] = []
    if clauses_total > len(clauses):
        notes.append(
            f"Ditampilkan {len(clauses)} dari {clauses_total} klausa yang memicu aspek ini; "
            f"{negatif_total} di antaranya berisi keluhan. Yang berkeluhan didahulukan."
        )
    if priority.capped_by_small_data:
        notes.append(
            f"Urgensi dibatasi maksimal Sedang karena sesi ini kurang dari "
            f"{MIN_REVIEWS_FOR_HIGH_URGENCY} ulasan - pembatasan ini bekerja SETELAH skor "
            f"dihitung, jadi skor di atas tidak ikut berubah."
        )

    return ActionTrace(
        action_id=action_id,
        aspect=aspect,
        clauses=clauses,
        clauses_total=clauses_total,
        negative_clauses_total=negatif_total,
        aggregate=aggregate,
        formula=FORMULA,
        factors=factors,
        core=round(core, 6),
        modifier=round(modifier, 6),
        score=priority.score,
        citations=list(citations or []),
        notes=notes,
    )
