"""Arsip analisis dan perbandingan antar-periode (L5) - tanpa database.

Baris "riwayat antar-sesi" ada di Roadmap sejak awal dan selalu tertahan di sana: memenuhinya
dengan cara biasa berarti menyimpan hasil pengguna di server, dan itu melanggar batasan MVP
sekaligus membatalkan janji privasi di layar pertama.

Modul ini memenuhinya dengan membalik siapa yang menyimpan. Pengguna mengunduh sekeping JSON
berisi agregat, lalu mengunggahnya kembali di sesi berikutnya sebagai pembanding. Server tetap
tidak menyimpan apa pun; yang bertambah cuma satu bentuk data dan satu fungsi aritmetika.

Hasil sampingannya justru memperkuat cerita produknya. "Kami tidak menyimpan apa pun" berhenti
menjadi keterbatasan yang harus dimaklumi dan menjadi bentuk kepemilikan: arsipnya milik
pengguna, ada di komputernya, dan ia yang memutuskan kapan dibandingkan.

**Satu disiplin yang mengikat seluruh berkas ini.** Selisih dua persentase TIDAK pernah
ditampilkan begitu saja. Dua proporsi yang masing-masing bermargin kesalahan menghasilkan
selisih yang marginnya lebih lebar dari keduanya, dan "keluhan pengiriman turun 19% ke 8%"
pada dua batch tiga puluhan ulasan bisa seluruhnya derau. Pemilik toko yang membacanya akan
menyimpulkan pergantian kurirnya berhasil, lalu mengambil keputusan bisnis atas dasar itu.
Aturan yang sama sudah dipakai pada perbandingan baseline kategori; ia berlaku di sini karena
alasannya identik, bukan demi keseragaman.
"""

from __future__ import annotations

import math

from ..schemas import (
    AnalysisArchive,
    ArchiveComparison,
    ArchiveAspect,
    AspectAggregate,
    AspectDelta,
    Category,
)

SCHEMA_VERSION = "ulasin-archive-1"

Z_95 = 1.96

# Di bawah jumlah ini, perbandingan antar-periode tidak dilaporkan sebagai temuan sama sekali.
# Angkanya sama dengan ambang benchmark, dan itu bukan kebetulan: keduanya menanyakan hal yang
# sama - apakah proporsi dari sampel sekecil ini cukup rapat untuk dibandingkan.
MIN_REVIEWS_FOR_COMPARISON = 30


def build_archive(
    analysis_id: str,
    aggregates: list[AspectAggregate],
    total_reviews: int,
    reviews_with_complaint: int,
    category: Category,
    period_start=None,
    period_end=None,
    model_versions: dict[str, str] | None = None,
    confidence_calibrated: bool = False,
) -> AnalysisArchive:
    """Susun arsip dari hasil analisis yang sudah jadi.

    Penyebut `pct_negative_of_reviews` adalah JUMLAH ULASAN, bukan jumlah sebutan aspek itu.
    Bedanya menentukan: proporsi terhadap sebutan tidak dapat dibandingkan antar sesi, karena
    penyebutnya sendiri ikut berubah. "12% ulasan saya mengeluhkan pengiriman" berarti hal yang
    sama bulan lalu dan bulan ini; "40% dari yang membahas pengiriman" tidak.
    """
    return AnalysisArchive(
        schema_version=SCHEMA_VERSION,
        analysis_id=analysis_id,
        total_reviews=total_reviews,
        reviews_with_complaint=reviews_with_complaint,
        category=category,
        period_start=period_start,
        period_end=period_end,
        aspects=[
            ArchiveAspect(
                aspect=a.aspect,
                total_mentions=a.total_mentions,
                negative_count=a.negative_count,
                positive_count=a.positive_count,
                pct_negative_of_reviews=round(
                    a.negative_count / total_reviews if total_reviews else 0.0, 4
                ),
            )
            for a in aggregates
        ],
        model_versions=dict(model_versions or {}),
        confidence_calibrated=confidence_calibrated,
    )


def _margin_of_difference(p1: float, n1: int, p2: float, n2: int) -> float:
    """Margin kesalahan 95% untuk SELISIH dua proporsi independen.

    Bukan margin masing-masing, dan bukan yang lebih besar di antara keduanya: ragam selisih
    adalah jumlah kedua ragam, sehingga marginnya selalu lebih lebar daripada margin mana pun
    yang menyusunnya. Memakai margin salah satu sisi akan membuat perubahan tampak dapat
    dibedakan dari nol jauh lebih sering daripada yang sebenarnya.
    """
    if n1 <= 0 or n2 <= 0:
        return 1.0
    var = max(p1 * (1.0 - p1), 0.0) / n1 + max(p2 * (1.0 - p2), 0.0) / n2
    return round(Z_95 * math.sqrt(var), 4)


def compare_archives(
    previous: AnalysisArchive,
    current: AnalysisArchive,
) -> ArchiveComparison:
    """Bandingkan arsip lama dengan analisis yang sedang dibuka.

    Aspek yang hanya ada di salah satu sisi tetap dilaporkan, dengan nol di sisi yang tidak
    punya. Menghilangkannya akan menyembunyikan justru perubahan yang paling menarik: keluhan
    yang muncul dari ketiadaan, atau yang hilang sama sekali.
    """
    warnings: list[str] = []

    if previous.schema_version != SCHEMA_VERSION:
        warnings.append(
            f"Arsip dibuat dengan format {previous.schema_version}, sedangkan sistem ini "
            f"memakai {SCHEMA_VERSION}. Angka yang dibandingkan bisa tidak sepadan."
        )
    if previous.category is not current.category:
        warnings.append(
            f"Kategori berbeda: arsip lama {previous.category.value}, sesi ini "
            f"{current.category.value}. Perbandingannya tetap sah karena tidak melibatkan "
            f"baseline kategori, tetapi periksa apakah keduanya memang toko yang sama."
        )
    if previous.analysis_id == current.analysis_id:
        warnings.append(
            "Arsip ini berasal dari analisis yang sedang Anda buka, jadi seluruh selisihnya "
            "nol. Unggah arsip dari sesi sebelumnya."
        )

    # Periode yang tumpang tindih membuat sebagian ulasan dihitung di KEDUA sisi, sehingga
    # perubahan yang sebenarnya teredam - dan peredaman itu tidak terlihat di angka mana pun.
    if (
        previous.period_end is not None
        and current.period_start is not None
        and previous.period_end > current.period_start
    ):
        warnings.append(
            "Rentang tanggal kedua analisis tumpang tindih. Sebagian ulasan yang sama "
            "kemungkinan terhitung di kedua sisi, sehingga perubahannya tampak lebih kecil "
            "dari yang sebenarnya."
        )

    tipis = (
        previous.total_reviews < MIN_REVIEWS_FOR_COMPARISON
        or current.total_reviews < MIN_REVIEWS_FOR_COMPARISON
    )
    if tipis:
        warnings.append(
            f"Salah satu sisi punya kurang dari {MIN_REVIEWS_FOR_COMPARISON} ulasan "
            f"({previous.total_reviews} lalu, {current.total_reviews} sekarang). Selisih pada "
            f"jumlah sekecil itu sulit dibedakan dari kebetulan."
        )

    lama = {a.aspect: a for a in previous.aspects}
    baru = {a.aspect: a for a in current.aspects}

    deltas: list[AspectDelta] = []
    for aspect in sorted(set(lama) | set(baru), key=lambda a: a.value):
        a_lama = lama.get(aspect)
        a_baru = baru.get(aspect)
        p1 = a_lama.pct_negative_of_reviews if a_lama else 0.0
        p2 = a_baru.pct_negative_of_reviews if a_baru else 0.0
        c1 = a_lama.negative_count if a_lama else 0
        c2 = a_baru.negative_count if a_baru else 0

        margin = _margin_of_difference(p1, previous.total_reviews, p2, current.total_reviews)
        selisih = round(p2 - p1, 4)
        berarti = abs(selisih) > margin and not tipis

        if not berarti:
            arah = "tetap"
        elif selisih < 0:
            arah = "membaik"
        else:
            arah = "memburuk"

        deltas.append(
            AspectDelta(
                aspect=aspect,
                before_count=c1,
                after_count=c2,
                before_pct=round(p1, 4),
                after_pct=round(p2, 4),
                delta_pct=selisih,
                margin_of_error=margin,
                significant=berarti,
                direction=arah,
            )
        )

    # Perubahan terbesar yang BERARTI - bukan perubahan terbesar. Menyebut angka terbesar tanpa
    # syarat itu berarti kalimat kepala laporan justru menjadi tempat derau paling mudah lolos.
    deltas.sort(key=lambda d: abs(d.delta_pct), reverse=True)
    berarti = [d for d in deltas if d.significant]
    if berarti:
        d = berarti[0]
        nama = d.aspect.value.replace("_", " ")
        kata = "turun" if d.delta_pct < 0 else "naik"
        headline = (
            f"Keluhan {nama} {kata} dari {d.before_pct:.0%} ke {d.after_pct:.0%} "
            f"({abs(d.delta_pct):.0%} poin, di luar margin +-{d.margin_of_error:.0%})."
        )
    else:
        headline = (
            "Tidak ada aspek yang berubah cukup besar untuk dibedakan dari kebetulan. "
            "Itu sendiri sebuah temuan: yang Anda kerjakan belum terlihat efeknya di ulasan."
        )

    return ArchiveComparison(
        previous_total=previous.total_reviews,
        current_total=current.total_reviews,
        previous_period_end=previous.period_end,
        current_period_start=current.period_start,
        deltas=deltas,
        headline=headline,
        warnings=warnings,
    )
