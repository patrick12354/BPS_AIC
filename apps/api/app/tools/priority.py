"""calculate_priority_score() - tool contract bagian 27.3, formula bagian 22.2.

Skor dihitung DETERMINISTIC di sini, bukan oleh LLM (ADR-011). Ini yang membuat angka pada
Action Card dapat diaudit dan konsisten antar run.

Formula final (bagian 22.2 - hasil kajian ulang, BUKAN perkalian mentah enam faktor):

    score = frequency_norm x severity_norm
            x (1 + w_recency x recency_norm + w_benchmark x benchmark_gap_norm)

Dua faktor pertama adalah PENGALI INTI; recency dan benchmark gap hanya MODIFIER. Alasannya:
sebuah masalah tidak menjadi prioritas hanya karena sedang naik - ia harus sering dan parah
lebih dulu. `Business Relevance` sengaja dihapus sebagai faktor terpisah karena tumpang tindih
dengan Severity.

`confidence_norm` pernah menjadi pengali inti ketiga dan DIKELUARKAN dari rumus. Nilainya
adalah rata-rata probabilitas softmax klausa yang belum terkalibrasi (0,96-0,999 pada
checkpoint saat ini) - angka yang tidak dikarang tetapi juga belum bermakna sebagai keyakinan.
Mengalikan skor dengan angka semacam itu berarti menyisipkan faktor yang sengaja tidak
ditampilkan di layar ke dalam urutan kartu yang ditampilkan. Ia tetap DILAPORKAN di `factors`
dan di jejak perhitungan supaya pembaca melihat nilainya beserta statusnya, tetapi tidak
mengalikan apa pun sampai kalibrasi (temperature scaling, lihat docs/LIMITATIONS.md) selesai
dan `confidence_calibrated` bernilai True.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas import AspectAggregate, BenchmarkRecord, Severity, Trend, Urgency

# Bobot modifier - [REQUIRES VALIDATION] bagian 22.2: wajib diuji sensitivity +-50% pada
# Fase 8 sebelum dianggap final. Diekspos sebagai parameter supaya pengujian itu dapat
# dijalankan tanpa mengubah kode.
DEFAULT_W_RECENCY = 0.3
DEFAULT_W_BENCHMARK = 0.2

SEVERITY_NORM = {Severity.RENDAH: 0.34, Severity.SEDANG: 0.67, Severity.TINGGI: 1.0}

# Tren dipetakan ke 0-1. `tidak_cukup_data` diberi 0, BUKAN nilai tengah: tanpa bukti tren,
# sistem tidak boleh menaikkan prioritas atas dasar dugaan.
TREND_NORM = {
    Trend.MENINGKAT: 1.0,
    Trend.STABIL: 0.3,
    Trend.MENURUN: 0.0,
    Trend.TIDAK_CUKUP_DATA: 0.0,
}

# Gap benchmark dinormalisasi terhadap selisih 20 poin persentase. Gap negatif (toko lebih
# baik dari baseline) tidak menurunkan skor di bawah nol - ia hanya tidak memberi dorongan.
BENCHMARK_GAP_SCALE = 0.20

# Ambang urgensi - PROVISIONAL, dikalibrasi ulang pada Fase 8 (bagian 22.2).
# Nilai ini diturunkan dari distribusi skor pada dataset demo, bukan angka karangan, tetapi
# belum divalidasi terhadap penilaian manusia.
DEFAULT_URGENCY_THRESHOLDS = {"tinggi": 12.0, "sedang": 5.0}

# Di bawah jumlah ulasan ini, urgensi dibatasi maksimal "Sedang" (bagian 22.2) - formula tidak
# valid secara statistik pada volume sangat kecil, dan sistem tidak boleh terdengar pasti.
MIN_REVIEWS_FOR_HIGH_URGENCY = 15


@dataclass(frozen=True)
class PriorityResult:
    score: float
    urgency: Urgency
    reasoning: str
    factors: dict[str, float]
    capped_by_small_data: bool


# Ambang "menonjol" per faktor, bukan satu ambang seragam - skala tiap faktor berbeda arti.
# Severity hanya disebut tinggi pada nilai maksimalnya; menyebut nilai "sedang" (0,67) sebagai
# "keparahan tinggi" akan melebihkan apa yang sebenarnya diukur.
_FACTOR_LABELS = {
    "frequency_norm": (0.15, "frekuensi keluhan tinggi"),
    "severity_norm": (1.0, "tingkat keparahan tinggi"),
    "recency_norm": (1.0, "tren meningkat"),
    "benchmark_gap_norm": (0.65, "jauh di atas baseline kategori"),
}


def _notable_factors(factors: dict[str, float]) -> list[str]:
    """Faktor mana yang menonjol - BUKAN "faktor dominan" tunggal.

    Tiga faktor inti masuk formula sebagai perkalian, sehingga secara matematis tidak ada
    satu pun yang dapat disebut dominan: elastisitas skor terhadap masing-masing sama besar.
    Menyebut satu "dominan" akan mengarang keunggulan yang tidak ada, dan pada praktiknya
    menghasilkan penjelasan seragam di semua Action Card - persis yang dilarang prinsip
    anti-generik (bagian 22.3).

    `confidence_norm` sengaja tidak pernah disebut: keyakinan model bukan alasan bisnis untuk
    memprioritaskan sesuatu - dan sejak dikeluarkan dari rumus ia memang tidak memengaruhi
    skor sama sekali.
    """
    return [
        label
        for key, (threshold, label) in _FACTOR_LABELS.items()
        if factors.get(key, 0.0) >= threshold
    ]


def calculate_priority_score(
    aggregate: AspectAggregate,
    total_reviews: int,
    benchmark: BenchmarkRecord | None = None,
    w_recency: float = DEFAULT_W_RECENCY,
    w_benchmark: float = DEFAULT_W_BENCHMARK,
    urgency_thresholds: dict[str, float] | None = None,
) -> PriorityResult:
    """Hitung skor prioritas 0-100 beserta label urgensi dan penjelasannya.

    Args:
        aggregate: keluaran calculate_aspect_statistics() untuk satu aspek
        total_reviews: jumlah ulasan pada sesi - penyebut frequency_norm
        benchmark: opsional; tanpa ini modifier benchmark bernilai nol
        w_recency, w_benchmark: bobot modifier, diekspos untuk sensitivity analysis
        urgency_thresholds: ambang pemetaan skor ke label urgensi

    Returns:
        PriorityResult - `reasoning` selalu dihasilkan TEMPLATE, bukan LLM (bagian 22.2).
    """
    thresholds = urgency_thresholds or DEFAULT_URGENCY_THRESHOLDS

    # Seluruh faktor dinormalisasi ke 0-1 SEBELUM dikalikan (bagian 22.2 isu "Normalisasi").
    frequency_norm = min(aggregate.negative_count / total_reviews, 1.0) if total_reviews else 0.0
    severity_norm = SEVERITY_NORM[aggregate.dominant_severity]
    confidence_norm = aggregate.avg_confidence
    recency_norm = TREND_NORM[aggregate.trend]
    benchmark_gap_norm = 0.0
    # `preliminary` berarti selisihnya tidak dapat dibedakan dari nol pada data sekecil ini.
    # Selisih yang tidak layak DITAMPILKAN juga tidak layak MENAIKKAN prioritas - kalau
    # dibiarkan, angka yang sengaja disembunyikan dari layar tetap bekerja diam-diam di
    # belakang urutan kartu, dan itu bentuk ketidakjujuran yang lebih buruk daripada
    # menampilkannya.
    if benchmark is not None and not benchmark.preliminary:
        benchmark_gap_norm = max(0.0, min(benchmark.gap / BENCHMARK_GAP_SCALE, 1.0))

    # confidence_norm sengaja TIDAK ikut dikalikan - lihat docstring modul.
    core = frequency_norm * severity_norm
    modifier = 1.0 + w_recency * recency_norm + w_benchmark * benchmark_gap_norm
    score = round(min(core * modifier * 100.0, 100.0), 2)

    capped = total_reviews < MIN_REVIEWS_FOR_HIGH_URGENCY
    if score >= thresholds["tinggi"]:
        urgency = Urgency.TINGGI
    elif score >= thresholds["sedang"]:
        urgency = Urgency.SEDANG
    else:
        urgency = Urgency.RENDAH
    if capped and urgency == Urgency.TINGGI:
        urgency = Urgency.SEDANG

    factors = {
        "frequency_norm": round(frequency_norm, 4),
        "severity_norm": severity_norm,
        "confidence_norm": round(confidence_norm, 4),
        "recency_norm": recency_norm,
        "benchmark_gap_norm": round(benchmark_gap_norm, 4),
    }

    pct = aggregate.negative_count / total_reviews if total_reviews else 0.0
    parts = [
        f"{aggregate.negative_count} dari {total_reviews} ulasan ({pct:.0%}) "
        f"menyebut masalah pada aspek ini"
    ]
    if aggregate.trend == Trend.MENINGKAT:
        parts.append("dan tren keluhannya meningkat dalam 30 hari terakhir")
    if benchmark is not None and benchmark.gap > 0 and not benchmark.preliminary:
        parts.append(
            f"serta {benchmark.gap:.0%} poin di atas baseline kategori "
            f"(n={benchmark.baseline_sample_size})"
        )
    reasoning = ", ".join(parts) + "."
    notable = _notable_factors(factors)
    if notable:
        reasoning += f" Yang menonjol: {', '.join(notable)}."
    if capped:
        reasoning += (
            " Urgensi dibatasi maksimal Sedang karena data sesi kurang dari "
            f"{MIN_REVIEWS_FOR_HIGH_URGENCY} ulasan."
        )

    return PriorityResult(
        score=score,
        urgency=urgency,
        reasoning=reasoning,
        factors=factors,
        capped_by_small_data=capped,
    )
