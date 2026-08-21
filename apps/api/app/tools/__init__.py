"""Sepuluh tool contract (blueprint bagian 27.3).

Tool di paket ini adalah SATU-SATUNYA sumber angka dalam sistem. Foundation model tidak pernah
menghitung sendiri - ia memanggil tool ini dan menyusun narasi dari hasilnya (ADR-011).

Status implementasi:
    preprocess_reviews()            - selesai
    redact_personal_data()          - selesai
    classify_text_aspects()         - Fase 5 (adapter ke model Fase 2)
    classify_review_image()         - Fase 5 (adapter ke model Fase 3)
    retrieve_evidence()             - selesai
    calculate_aspect_statistics()   - selesai
    calculate_priority_score()      - selesai
    compare_category_baseline()     - selesai
    generate_action_recommendations() - selesai (template); versi LLM pada Fase 5
    answer_review_question()        - Fase 5

Empat tool tambahan di luar sepuluh yang dikontrakkan blueprint. Semuanya membelah keluaran
tool di atas menurut kolom yang sudah dibawa ulasannya sendiri, dan tidak satu pun melibatkan
model - aturan ADR-011 tetap utuh:

    build_rating_breakdown()        - sebaran bintang + keluhan di dalam tiap pita
    summarize_products()            - ringkasan per produk
    build_period_history()          - riwayat antar periode dari satu berkas
    detect_category()               - menebak kategori, menggantikan pertanyaan di layar unggah
    build_reply_drafts()            - draf balasan penjual, deterministik dari template
    build_action_trace()            - rantai klausa -> agregat -> skor untuk satu kartu
    build_archive()                 - ringkasan agregat yang aman dibawa keluar sesi
    compare_archives()              - selisih antar-periode, tanpa database
"""

from .actions import build_action_card, has_concrete_numbers
from .archive import build_archive, compare_archives
from .benchmark import compare_category_baseline, load_baseline
from .category import detect_category
from .fusion import fuse_all, fuse_review
from .ingestion import PreprocessResult, preprocess_reviews
from .periods import build_period_history
from .privacy import redact_personal_data
from .opportunity import find_opportunities, score_data_quality
from .qna import QnAContext, QnAStore, answer_question
from .replies import build_reply_draft, build_reply_drafts
from .priority import PriorityResult, calculate_priority_score
from .retrieval import EvidenceIndex, retrieve_evidence
from .segments import build_rating_breakdown, summarize_products
from .statistics import calculate_aspect_statistics
from .trace import build_action_trace

__all__ = [
    "build_action_card",
    "build_action_trace",
    "build_archive",
    "build_period_history",
    "build_rating_breakdown",
    "build_reply_draft",
    "build_reply_drafts",
    "detect_category",
    "summarize_products",
    "fuse_all",
    "fuse_review",
    "has_concrete_numbers",
    "calculate_aspect_statistics",
    "calculate_priority_score",
    "compare_archives",
    "compare_category_baseline",
    "load_baseline",
    "PriorityResult",
    "EvidenceIndex",
    "retrieve_evidence",
    "find_opportunities",
    "QnAContext",
    "QnAStore",
    "answer_question",
    "score_data_quality",
    "preprocess_reviews",
    "PreprocessResult",
    "redact_personal_data",
]
