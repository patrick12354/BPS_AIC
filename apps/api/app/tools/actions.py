"""ACT-01 - penyusunan Action Card (blueprint bagian 22.1, 22.3).

Ini novelty inti produk: jembatan dari skor aspek ke keputusan bisnis konkret.

Modul ini menghasilkan versi TEMPLATE DETERMINISTIC dari narasi Action Card - yaitu jalur yang
dipakai saat FALLBACK MODE aktif (ADR-014). Pada FULL MODE, orchestrator menyusun ulang kalimat
`recommended_action` dari ANGKA YANG SAMA; seluruh angka, skor, dan struktur kartu tetap berasal
dari sini, tidak pernah dari LLM.

Prinsip anti-generik (bagian 22.3): setiap template WAJIB menyisipkan angka konkret hasil
perhitungan. Kalimat rekomendasi tanpa angka dianggap cacat, bukan gaya penulisan.
"""

from __future__ import annotations

from ..schemas import (
    ActionCard,
    ActionCategory,
    Aspect,
    AspectAggregate,
    BenchmarkRecord,
    EvidenceCitation,
    MultimodalEvidence,
    Severity,
    Trend,
)
from .priority import PriorityResult

# Pemetaan aspek -> kategori tindakan (bagian 22.3). Kategori menentukan bentuk saran, siapa
# yang mengerjakannya, dan seberapa besar ongkosnya.
ASPECT_TO_CATEGORY = {
    Aspect.UKURAN_VARIAN: ActionCategory.LISTING_CONTENT,
    Aspect.KESESUAIAN_DESKRIPSI: ActionCategory.LISTING_CONTENT,
    Aspect.KUALITAS_PRODUK: ActionCategory.PRODUCT_QUALITY,
    Aspect.RASA_KUALITAS_MAKANAN: ActionCategory.PRODUCT_QUALITY,
    Aspect.KEASLIAN: ActionCategory.PRODUCT_QUALITY,
    Aspect.KEMASAN: ActionCategory.PACKAGING,
    Aspect.PENGIRIMAN: ActionCategory.PACKAGING,
    Aspect.PELAYANAN_PENJUAL: ActionCategory.SERVICE,
    Aspect.HARGA_VALUE: ActionCategory.PRICING_REVIEW,
    Aspect.KELENGKAPAN: ActionCategory.PRODUCT_QUALITY,
    Aspect.KEMUDAHAN_PENGGUNAAN: ActionCategory.CUSTOMER_COMMUNICATION,
}

ASPECT_LABEL = {
    Aspect.KUALITAS_PRODUK: "kualitas produk",
    Aspect.KESESUAIAN_DESKRIPSI: "kesesuaian dengan deskripsi",
    Aspect.HARGA_VALUE: "harga",
    Aspect.KEMASAN: "kemasan",
    Aspect.PENGIRIMAN: "pengiriman",
    Aspect.PELAYANAN_PENJUAL: "pelayanan penjual",
    Aspect.UKURAN_VARIAN: "ukuran atau varian",
    Aspect.RASA_KUALITAS_MAKANAN: "rasa",
    Aspect.KELENGKAPAN: "kelengkapan isi",
    Aspect.KEASLIAN: "keaslian produk",
    Aspect.KEMUDAHAN_PENGGUNAAN: "kemudahan pemakaian",
}

# Judul, ongkos, pemilik, dan risiko per kategori. Judul memakai kata kerja yang bisa
# dikerjakan besok pagi - bukan "optimasi listing" yang tidak memberi tahu apa pun.
CATEGORY_TEMPLATE = {
    ActionCategory.LISTING_CONTENT: {
        "title": "Perbaiki keterangan {label} di halaman produk",
        "action": (
            "Periksa kembali keterangan {label} pada halaman produk Anda. "
            "{frequency} dari {total} ulasan ({pct}) menyebut hal ini."
        ),
        "outcome": "Keluhan {label} berkurang dan pembeli lebih jarang salah pilih",
        "effort": "rendah - mengubah teks dan gambar di halaman produk",
        "owner": "pemilik toko atau admin listing",
        "risk_undone": "Keluhan berulang, dan potensi retur ikut naik",
        "risk_wrong": (
            "Jika keterangannya sebenarnya sudah tepat, perubahan ini tidak akan menurunkan "
            "keluhan - periksa dulu beberapa kutipan sebelum mengubah"
        ),
    },
    ActionCategory.PRODUCT_QUALITY: {
        "title": "Periksa {label} pada batch produk terbaru",
        "action": (
            "Periksa {label} pada stok yang sedang dijual. "
            "{frequency} dari {total} ulasan ({pct}) menyebut masalah ini."
        ),
        "outcome": "Keluhan kualitas menurun dan rating produk membaik",
        "effort": "sedang - perlu memeriksa stok atau menghubungi pemasok",
        "owner": "pemilik toko",
        "risk_undone": "Masalah yang sama terus berulang pada pembeli berikutnya",
        "risk_wrong": (
            "Jika masalahnya hanya pada sebagian kecil kiriman, pemeriksaan menyeluruh bisa "
            "memakan waktu tanpa hasil sepadan - mulai dari varian yang paling sering disebut"
        ),
    },
    ActionCategory.PACKAGING: {
        # Judul memuat {label} karena kategori ini mencakup DUA aspek (kemasan dan
        # pengiriman). Judul tetap akan menghasilkan dua kartu berjudul sama pada satu
        # layar hasil, dan itu terbaca sebagai sistem yang rusak.
        "title": "Tinjau proses {label} pesanan",
        "action": (
            "Tinjau cara Anda mengemas dan mengirim pesanan. "
            "{frequency} dari {total} ulasan ({pct}) menyebut masalah {label}."
        ),
        "outcome": "Barang sampai dalam kondisi lebih baik dan keluhan menurun",
        "effort": "rendah - mengganti bahan pengemas atau jasa kirim",
        "owner": "pemilik toko atau staf pengemasan",
        "risk_undone": "Barang rusak di jalan, biaya retur ditanggung toko",
        "risk_wrong": (
            "Jika penyebabnya ada di jasa kirim dan bukan pengemasan, mengganti bahan pengemas "
            "tidak akan menyelesaikannya - periksa apakah keluhannya terpusat pada satu tujuan"
        ),
    },
    ActionCategory.SERVICE: {
        "title": "Tinjau kecepatan dan cara membalas pembeli",
        "action": (
            "Tinjau bagaimana pesan pembeli dibalas. "
            "{frequency} dari {total} ulasan ({pct}) menyebut {label}."
        ),
        "outcome": "Pembeli merasa lebih dilayani dan keluhan pelayanan menurun",
        "effort": "rendah - menyiapkan balasan siap pakai untuk pertanyaan berulang",
        "owner": "pemilik toko atau staf customer service",
        "risk_undone": "Pembeli beralih ke toko lain yang lebih responsif",
        "risk_wrong": (
            "Jika keluhannya soal isi jawaban dan bukan kecepatannya, mempercepat balasan tidak "
            "akan membantu - baca dulu kutipannya"
        ),
    },
    ActionCategory.PRICING_REVIEW: {
        "title": "Tinjau ulang harga varian termurah",
        "action": (
            "Tinjau harga produk Anda. "
            "{frequency} dari {total} ulasan ({pct}) menyebut {label}."
        ),
        "outcome": "Pembeli merasa harganya sepadan dengan yang diterima",
        "effort": "sedang - perlu menghitung ulang margin",
        "owner": "pemilik toko",
        "risk_undone": "Pembeli membandingkan dengan toko lain lalu tidak jadi membeli",
        "risk_wrong": (
            "Menurunkan harga menggerus margin. Keluhan harga sering sebenarnya keluhan "
            "kualitas - pastikan dulu mana yang benar-benar dikeluhkan"
        ),
    },
    ActionCategory.CUSTOMER_COMMUNICATION: {
        "title": "Tambahkan penjelasan cara pakai di halaman produk",
        "action": (
            "Tambahkan penjelasan singkat cara pemakaian pada halaman produk. "
            "{frequency} dari {total} ulasan ({pct}) menyebut {label}."
        ),
        "outcome": "Pertanyaan berulang berkurang dan pembeli lebih puas",
        "effort": "rendah - menambah beberapa kalimat atau gambar",
        "owner": "pemilik toko atau admin listing",
        "risk_undone": "Pertanyaan yang sama terus masuk dan memakan waktu",
        "risk_wrong": "Jika produknya memang rumit, penjelasan saja mungkin belum cukup",
    },
    ActionCategory.INVESTIGATION_NEEDED: {
        "title": "Tinjau manual ulasan yang teks dan fotonya bertentangan",
        "action": (
            "Ada {frequency} ulasan yang teksnya menyebut puas namun fotonya menunjukkan "
            "indikasi masalah. Sistem tidak menyimpulkan mana yang benar - perlu Anda lihat."
        ),
        "outcome": "Ketidaksesuaian terjelaskan, dan pola masalah yang tersembunyi ikut terlihat",
        "effort": "rendah - membuka beberapa ulasan yang ditandai",
        "owner": "pemilik toko",
        "risk_undone": "Masalah nyata tertutup oleh ulasan yang terlihat positif",
        "risk_wrong": "Sebagian mungkin hanya salah unggah foto oleh pembeli",
    },
}

TREND_PHRASE = {
    Trend.MENINGKAT: " Keluhan ini meningkat dalam 30 hari terakhir.",
    Trend.MENURUN: " Keluhan ini menurun dibanding periode sebelumnya.",
    Trend.STABIL: "",
    Trend.TIDAK_CUKUP_DATA: "",
}


def _summary(aggregate: AspectAggregate, total_reviews: int) -> str:
    pct = aggregate.negative_count / total_reviews if total_reviews else 0.0
    return (
        f"{aggregate.negative_count} dari {total_reviews} ulasan ({pct:.0%}) "
        f"menyebut masalah pada {ASPECT_LABEL[aggregate.aspect]}"
    )


def build_action_card(
    action_id: str,
    aggregate: AspectAggregate,
    priority: PriorityResult,
    total_reviews: int,
    evidence: list[EvidenceCitation] | None = None,
    benchmark: BenchmarkRecord | None = None,
    contradictions: list[MultimodalEvidence] | None = None,
) -> ActionCard:
    """Susun satu Action Card dari angka yang SUDAH dihitung tool lain.

    Fungsi ini tidak menghitung apa pun sendiri - ia hanya merangkai. Pemisahan itu yang
    membuat angka pada kartu dapat diaudit balik ke tool-nya masing-masing.
    """
    contradiction_count = len(contradictions or [])
    category = (
        ActionCategory.INVESTIGATION_NEEDED
        if contradiction_count >= 3
        else ASPECT_TO_CATEGORY[aggregate.aspect]
    )
    template = CATEGORY_TEMPLATE[category]

    label = ASPECT_LABEL[aggregate.aspect]
    pct = aggregate.negative_count / total_reviews if total_reviews else 0.0
    fields = {
        "label": label,
        "frequency": (
            contradiction_count
            if category == ActionCategory.INVESTIGATION_NEEDED
            else aggregate.negative_count
        ),
        "total": total_reviews,
        "pct": f"{pct:.0%}",
    }

    action_text = template["action"].format(**fields) + TREND_PHRASE[aggregate.trend]
    # Perbandingan yang masih berstatus indikasi awal tidak disebut di kalimat rekomendasi.
    # Kalimat itu dibaca sebagai fakta, dan pada data sekecil itu selisihnya belum fakta.
    if benchmark is not None and benchmark.gap > 0 and not benchmark.preliminary:
        action_text += (
            f" Angka ini {benchmark.gap:.0%} poin di atas rata-rata kategori sejenis "
            f"(dari {benchmark.baseline_sample_size} ulasan pembanding)."
        )

    visual_evidence = None
    return ActionCard(
        action_id=action_id,
        title=template["title"].format(**fields),
        one_line_summary=_summary(aggregate, total_reviews),
        aspect=aggregate.aspect,
        frequency=aggregate.negative_count,
        frequency_total=max(aggregate.total_mentions, aggregate.negative_count),
        severity=aggregate.dominant_severity,
        confidence=aggregate.avg_confidence,
        trend=aggregate.trend,
        priority_score=priority.score,
        urgency=priority.urgency,
        evidence_quotes=evidence or [],
        visual_evidence=visual_evidence,
        priority_reasoning=priority.reasoning,
        recommended_action=action_text,
        action_category=category,
        expected_outcome=template["outcome"].format(**fields),
        estimated_effort=template["effort"],
        suggested_owner=template["owner"],
        risk_if_not_done=template["risk_undone"],
        risk_if_recommendation_wrong=template["risk_wrong"],
        user_action=None,  # ADR-013: keputusan selalu milik manusia
    )


def has_concrete_numbers(card: ActionCard) -> bool:
    """Cek anti-generik (bagian 22.3): rekomendasi wajib memuat angka nyata.

    Dipakai sebagai gerbang kualitas, bukan sekadar assertion di test - kartu tanpa angka
    tidak boleh sampai ke pengguna dalam bentuk apa pun.
    """
    return any(ch.isdigit() for ch in card.recommended_action)
