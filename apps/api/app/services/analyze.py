"""AnalyzeService - orkestrasi satu request analisis (blueprint bagian 27.2, sequence 7.5–7.9).

Satu titik orkestrasi per request. Ia memanggil tool sesuai urutan pada sequence diagram dan
TIDAK menghitung apa pun sendiri - seluruh angka berasal dari tool (ADR-011).

Dua sifat yang menentukan bentuk kode ini:

1. **Sinkron.** Tidak ada background job (batas MVP rulebook bagian 2.4). Satu request masuk,
   satu AnalysisResult keluar.
2. **Tidak boleh gagal total.** Kegagalan model visual menurunkan alur ke jalur teks-saja;
   kegagalan orchestrator memicu FALLBACK MODE. Yang menghentikan analisis hanyalah kegagalan
   tool wajib di hulu - dan itupun dengan pesan yang dapat ditindaklanjuti (bagian 25.13).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from ..schemas import (
    AnalysisMode,
    QnAResponse,
    ActionTrace,
    AnalysisArchive,
    ArchiveComparison,
    AnalysisResult,
    AnalysisSummary,
    Category,
    CategoryGuess,
    ContradictionFinding,
    RawReview,
    ReplyDraftResponse,
    Sentiment,
)
from ..tools import (
    EvidenceIndex,
    QnAContext,
    QnAStore,
    answer_question,
    build_action_card,
    build_action_trace,
    build_archive,
    build_reply_drafts,
    build_period_history,
    build_rating_breakdown,
    calculate_aspect_statistics,
    calculate_priority_score,
    compare_archives,
    compare_category_baseline,
    detect_category,
    find_opportunities,
    fuse_all,
    load_baseline,
    preprocess_reviews,
    score_data_quality,
    summarize_products,
)

MAX_ACTION_CARDS = 5
EVIDENCE_PER_CARD = 3


class AnalyzeService:
    """Menjalankan pipeline analisis penuh untuk satu batch ulasan."""

    def __init__(
        self, text_adapter, embedding_adapter=None, orchestrator=None, baseline=None,
        min_similarity: float | None = None, vision_adapter=None, image_source=None,
    ):
        self.text_adapter = text_adapter
        self.embedding_adapter = embedding_adapter
        self.orchestrator = orchestrator
        # Jalur visual (L3/L4). Keduanya opsional dan keduanya bernilai None hari ini.
        #
        # `image_source` adalah cantelan yang mengubah daftar ProcessedReview menjadi daftar
        # (image_ref, review_id, byte). Ia belum punya isi karena BELUM ADA JALAN MASUK bagi
        # foto produk ke dalam analisis - `/ocr` menerima gambar tetapi hanya membaca teksnya,
        # dan `RawReview.image_paths` berisi path yang hanya berarti di mesin klien.
        #
        # Cantelannya tetap dipasang, dan itu bukan kode mati yang optimistis: ia yang membuat
        # sisa jalur visual - adapter, fusion, kartu kontradiksi - dapat diuji sekarang dengan
        # sumber tiruan, alih-alih menunggu satu fitur unggah yang belum boleh dibangun.
        self.vision_adapter = vision_adapter
        self.image_source = image_source
        self.baseline = baseline if baseline is not None else load_baseline()
        # Ambang relevansi bukti dapat dikonfigurasi (configs/config.yaml retrieval.min_similarity)
        # karena nilainya bergantung model embedding yang dipakai - ambang yang cocok untuk
        # BGE-M3 belum tentu cocok untuk fallback TF-IDF.
        self.min_similarity = min_similarity
        # Konteks Q&A hidup di memori proses saja dan kedaluwarsa sendiri (lihat tools/qna.py).
        self.qna_store = QnAStore()

    def answer(self, analysis_id: str, question: str) -> QnAResponse:
        """QNA-01 - jawab hanya dari analisis yang bersangkutan, tidak dari batch lain."""
        context = self.qna_store.get(analysis_id)
        if context is None:
            return QnAResponse(
                answer="", citations=[], no_answer=True,
                no_answer_reason=(
                    "Hasil analisis ini sudah tidak tersimpan. Jalankan analisis ulang untuk "
                    "dapat bertanya lagi."
                ),
            )
        return answer_question(context, question)

    # ----------------------------------------------------------------------------------
    # Permintaan lanjutan atas satu analisis
    # ----------------------------------------------------------------------------------
    # Keduanya membaca dari konteks sesi yang sama dengan Q&A, dan keduanya mengembalikan
    # None saat analisisnya sudah kedaluwarsa. Tidak ada jalan menghitung ulang: `predictions`
    # dan indeks bukti hidup selama request analisis saja, sesuai janji sesi sekali-pakai
    # (ADR-010). Yang benar dilakukan adalah mengatakannya, bukan memulihkannya diam-diam.

    def trace_for(self, analysis_id: str, action_id: str) -> ActionTrace | None:
        """Rantai perhitungan satu kartu - fitur S2 ("Bagaimana angka ini dihitung?")."""
        context = self.qna_store.get(analysis_id)
        if context is None:
            return None
        return context.traces.get(action_id)

    def archive_for(self, analysis_id: str) -> AnalysisArchive | None:
        """Ringkasan agregat yang aman dibawa keluar sesi - fitur L5.

        Disusun dari konteks sesi, bukan dari `AnalysisResult` yang sudah dikirim: hasil itu
        milik klien dan boleh berbeda dari yang dipegang server (pengguna dapat mengganti
        kategori pembanding di layar hasil). Arsip harus menggambarkan analisis yang benar-benar
        dijalankan.
        """
        context = self.qna_store.get(analysis_id)
        if context is None:
            return None
        return build_archive(
            analysis_id=analysis_id,
            aggregates=context.aggregates,
            total_reviews=context.total_reviews,
            reviews_with_complaint=context.reviews_with_complaint or 0,
            category=context.category,
            period_start=context.period_start,
            period_end=context.period_end,
            model_versions={
                "text": self.text_adapter.model_version,
                "embedding": getattr(self.embedding_adapter, "model_name", "tidak aktif"),
            },
            confidence_calibrated=bool(getattr(self.text_adapter, "calibrated", False)),
        )

    def compare_with_archive(
        self, analysis_id: str, previous: AnalysisArchive
    ) -> ArchiveComparison | None:
        """Selisih antar-periode terhadap arsip yang diunggah pengguna - fitur L5."""
        current = self.archive_for(analysis_id)
        if current is None:
            return None
        return compare_archives(previous, current)

    def reply_drafts(self, analysis_id: str, action_id: str) -> ReplyDraftResponse | None:
        """Draf balasan untuk seluruh ulasan pendukung satu kartu - fitur S1."""
        context = self.qna_store.get(analysis_id)
        if context is None:
            return None
        card = next((c for c in context.actions if c.action_id == action_id), None)
        if card is None:
            return None

        clauses = {
            review_id: clause
            for (review_id, aspect), clause in context.negative_clauses.items()
            if aspect == card.aspect.value
        }
        drafts = build_reply_drafts(card, clauses_by_review=clauses)
        return ReplyDraftResponse(
            action_id=card.action_id,
            aspect=card.aspect,
            drafts=drafts,
            note=(
                "Draf, bukan balasan jadi. Sunting dulu sebelum dikirim - sistem tidak tahu "
                "apa yang sudah Anda janjikan lewat chat, dan tidak pernah menuliskan "
                "keputusan ganti barang atau refund untuk Anda."
            ),
        )

    def _classify_images(self, reviews) -> list:
        """Prediksi visual untuk foto yang dibawa ulasan sesi ini - kosong bila jalurnya mati.

        Kegagalan di sini TIDAK PERNAH menghentikan analisis (bagian 20, ADR-014): jalur visual
        adalah lapisan tambahan di atas jalur teks, dan teks berdiri sendiri. Yang terjadi saat
        ia gagal adalah hasil teks-saja, persis seperti saat memang tidak ada foto.
        """
        adapter = self.vision_adapter
        if adapter is None or not getattr(adapter, "active", False):
            return []
        gambar = self.image_source(reviews) if self.image_source else []
        if not gambar:
            return []
        try:
            return adapter.classify(gambar)
        except Exception:  # pragma: no cover - jalur degradasi
            return []

    def _contradiction_findings(self, fused, reviews, visual_predictions) -> list:
        """Susun temuan L4: ulasan yang teks dan fotonya berlawanan arah.

        Kedua bukti dibawa berdampingan dan tidak ada yang dinyatakan menang. Sistem tidak tahu
        apakah pembelinya sungkan menulis keluhan, salah unggah foto, atau memfoto barang lain -
        yang diketahuinya cuma bahwa keduanya tidak cocok (bagian 20.3).
        """
        if not visual_predictions:
            return []

        teks_by_review = {r.review_id: r for r in reviews}
        visual_by_review: dict[str, list] = {}
        for v in visual_predictions:
            visual_by_review.setdefault(v.review_id, []).append(v)

        temuan: list[ContradictionFinding] = []
        for f in fused:
            if not f.contradiction_flag:
                continue
            review = teks_by_review.get(f.review_id)
            kandidat = [v for v in visual_by_review.get(f.review_id, []) if not v.abstain]
            if review is None or not kandidat:
                continue
            temuan.append(
                ContradictionFinding(
                    review_id=f.review_id,
                    # Teks yang SUDAH diredaksi, sama dengan yang dipakai indeks bukti.
                    quote=review.clean_text,
                    rating=review.rating,
                    text_says_problem="menyebut ada masalah" in (f.display_note or ""),
                    visual=max(kandidat, key=lambda v: v.confidence),
                    display_note=f.display_note or "",
                    combined_confidence=f.combined_confidence,
                )
            )
        return temuan

    def _dominant_category(self, reviews) -> Category:
        if not reviews:
            return Category.OTHER
        counts: dict[Category, int] = {}
        for r in reviews:
            counts[r.category] = counts.get(r.category, 0) + 1
        return max(counts, key=counts.get)

    def _resolve_category(self, reviews) -> tuple[Category, CategoryGuess]:
        """Tentukan kategori sesi ini, dan bawa serta dasarnya.

        Kategori yang datang bersama ulasan tetap menang bila pengguna benar-benar menyebutkan
        satu - itu keterangan langsung, dan tebakan tidak boleh menimpanya. Deteksi baru
        berjalan saat seluruh batch masuk sebagai `other`, yang sejak layar unggah tidak lagi
        menanyakan kategori adalah keadaan yang biasa, bukan kekecualian.
        """
        dominant = self._dominant_category(reviews)
        guess = detect_category(reviews)
        if dominant is not Category.OTHER:
            # Pengguna (atau berkasnya) sudah menyatakan kategori; tebakan tetap dilaporkan
            # supaya layar hasil dapat menyebut keduanya kalau berbeda.
            return dominant, guess
        return guess.category, guess

    def _benchmarks_for_every_category(self, aggregates, total_reviews) -> dict:
        """Baseline untuk KELIMA kategori, bukan hanya yang terpilih.

        `compare_category_baseline()` cuma aritmetika atas tabel JSON yang sudah dimuat ke
        memori saat startup - kelimanya bersama-sama masih di bawah satu milidetik. Yang dibeli
        dengan biaya itu adalah koreksi kategori yang seketika di layar hasil: pengguna yang
        melihat tebakan kami salah tidak perlu menunggu analisis ulang berpuluh detik hanya
        untuk menukar tabel pembanding.
        """
        return {
            category.value: compare_category_baseline(
                aggregates, category, total_reviews, baseline=self.baseline
            )
            for category in Category
        }

    def _build_evidence_index(self, reviews, predictions) -> EvidenceIndex | None:
        if self.embedding_adapter is None:
            return None
        aspects_by_review = {
            p.review_id: [item.aspect.value for item in p.predictions] for p in predictions
        }
        negative_by_review = {
            p.review_id: [
                item.aspect.value for item in p.predictions if item.sentiment.value == "negatif"
            ]
            for p in predictions
        }
        positive_by_review = {
            p.review_id: [
                item.aspect.value for item in p.predictions if item.sentiment.value == "positif"
            ]
            for p in predictions
        }
        index = (
            EvidenceIndex(self.embedding_adapter, min_similarity=self.min_similarity)
            if self.min_similarity is not None
            else EvidenceIndex(self.embedding_adapter)
        )
        index.build([
            {
                "review_id": r.review_id,
                "text": r.clean_text,
                "aspects": aspects_by_review.get(r.review_id, []),
                "negative_aspects": negative_by_review.get(r.review_id, []),
                "positive_aspects": positive_by_review.get(r.review_id, []),
                "rating": r.rating,
                "timestamp": r.timestamp,
            }
            for r in reviews
        ])
        return index

    def _executive_summary(self, aggregates, total: int, mode: AnalysisMode) -> str:
        """Ringkasan eksekutif. Pada FALLBACK MODE disusun template dari angka yang sama."""
        if not aggregates:
            return f"Dari {total} ulasan, belum ditemukan pola masalah yang cukup jelas."
        top = aggregates[0]
        pct = top.negative_count / total if total else 0.0
        base = (
            f"Dari {total} ulasan, {len([a for a in aggregates if a.negative_count])} aspek "
            f"memuat keluhan. Yang paling sering adalah {top.aspect.value.replace('_', ' ')} "
            f"- {top.negative_count} ulasan ({pct:.0%})."
        )
        if self.orchestrator is not None and mode == AnalysisMode.FULL:
            try:
                return self.orchestrator.summarize(aggregates, total)
            except Exception:
                pass  # jatuh ke template; mode sudah ditandai FALLBACK oleh pemanggil
        return base

    def analyze(
        self,
        raw_reviews: list[RawReview],
        now: datetime | None = None,
        trace: bool = False,
    ) -> AnalysisResult:
        pre = preprocess_reviews(raw_reviews, now=now)
        reviews = pre.reviews
        warnings = list(pre.warnings)

        if not reviews:
            return AnalysisResult(
                analysis_id=f"an_{uuid.uuid4().hex[:12]}",
                summary=AnalysisSummary(
                    total_reviews=0, reviews_with_image=0,
                    executive_summary_text="Tidak ada ulasan yang dapat dianalisis dari data ini.",
                ),
                warnings=warnings + ["data_kosong"],
                mode=AnalysisMode.FALLBACK,
                model_versions={},
            )

        predictions = self.text_adapter.classify(reviews)

        # Jalur visual dilewati bila tidak ada foto ATAU adapter visualnya nonaktif - keduanya
        # keadaan normal, bukan error. Nonaktif hari ini adalah keadaan yang benar: gerbang
        # go/no-go modul visual belum lolos, dan `VisionModelAdapter` menolak menyala sendiri
        # (lihat adapters/vision_model.py). Selama itu, `contradictions` di bawah selalu kosong
        # dan bagiannya tidak dirender - lebih baik tidak ada daripada ada tetapi menebak.
        visual_predictions: list = self._classify_images(reviews)
        fused = fuse_all(predictions, visual_predictions)
        contradictions = [f for f in fused if f.contradiction_flag]

        reference = now or max(
            (r.timestamp for r in reviews if r.timestamp), default=datetime.now()
        )
        aggregates = calculate_aspect_statistics(predictions, reviews, now=reference)

        category, category_guess = self._resolve_category(reviews)
        benchmark_by_category = self._benchmarks_for_every_category(aggregates, len(reviews))
        benchmarks = benchmark_by_category[category.value]
        benchmark_by_aspect = {b.aspect: b for b in benchmarks}

        index = self._build_evidence_index(reviews, predictions)

        scored = [
            (a, calculate_priority_score(a, len(reviews), benchmark_by_aspect.get(a.aspect)))
            for a in aggregates
            if a.negative_count > 0
        ]
        scored.sort(key=lambda x: x[1].score, reverse=True)

        mode = AnalysisMode.FULL if self.orchestrator is not None else AnalysisMode.FALLBACK
        cards = []
        traces: dict[str, ActionTrace] = {}
        for rank, (aggregate, priority) in enumerate(scored[:MAX_ACTION_CARDS], start=1):
            evidence = []
            if index is not None:
                evidence = index.retrieve(
                    query=aggregate.aspect.value.replace("_", " "),
                    aspect=aggregate.aspect,
                    top_k=EVIDENCE_PER_CARD,
                    negative_only=True,  # kartu keluhan wajib dibuktikan kutipan keluhan
                )
            action_id = f"ACT-{rank:03d}"
            cards.append(
                build_action_card(
                    action_id=action_id,
                    aggregate=aggregate,
                    priority=priority,
                    total_reviews=len(reviews),
                    evidence=evidence,
                    benchmark=benchmark_by_aspect.get(aggregate.aspect),
                    contradictions=contradictions,
                )
            )
            # Jejak dibangun SEKARANG, bukan saat diminta. `predictions` hidup selama request
            # ini saja; menyusunnya belakangan berarti menjalankan inferensi kedua atas data
            # yang sudah dilepas - beberapa puluh detik untuk menjawab satu klik "bagaimana
            # angka ini dihitung?". Ongkosnya di sini murni aritmetika atas objek yang sudah
            # ada di memori.
            traces[action_id] = build_action_trace(
                action_id=action_id,
                aspect=aggregate.aspect,
                aggregate=aggregate,
                priority=priority,
                predictions=predictions,
                total_reviews=len(reviews),
                citations=evidence,
                calibrated=bool(getattr(self.text_adapter, "calibrated", False)),
            )

        # OPP-01 - aspek yang justru dipuji, disajikan sebagai sinyal untuk materi promosi.
        positive_evidence = {}
        if index is not None:
            for agg in aggregates:
                if agg.positive_count >= 5:
                    positive_evidence[agg.aspect] = index.retrieve(
                        query=agg.aspect.value.replace("_", " "), aspect=agg.aspect, top_k=2,
                        # Kartu peluang mengklaim aspek ini DIPUJI; buktinya wajib pujian.
                        positive_only=True,
                    )
        opportunities = find_opportunities(aggregates, len(reviews), positive_evidence)

        # Segmentasi. Ketiganya membelah `predictions` yang sudah jadi menurut kolom yang
        # dibawa ulasannya sendiri - tidak ada inferensi model tambahan, jadi biayanya
        # aritmetika saja dan tidak menyentuh waktu tunggu pengguna.
        ratings = build_rating_breakdown(reviews, predictions)
        products = summarize_products(reviews, predictions)
        period_history = build_period_history(reviews, predictions)

        dates = [r.timestamp for r in reviews if r.timestamp is not None]

        data_quality = score_data_quality(
            total_uploaded=len(raw_reviews),
            used=len(reviews),
            skipped=pre.skipped,
            with_rating=sum(1 for r in reviews if r.rating is not None),
            with_timestamp=sum(1 for r in reviews if r.timestamp is not None),
            pii_redacted=pre.pii_redacted_count,
        )

        if mode == AnalysisMode.FALLBACK:
            warnings.append("mode_sederhana")

        # Dihitung per ulasan, bukan per sebutan - lihat catatan di AnalysisSummary.
        reviews_with_complaint = sum(
            1 for p in predictions if any(i.sentiment.value == "negatif" for i in p.predictions)
        )

        # Klausa negatif per (ulasan, aspek) - bahan kalimat pengakuan pada draf balasan.
        # Diambil dari `source_sentence` yang memang sudah dicatat tiap prediksi untuk
        # keterlacakan; tidak ada segmentasi ulang di sini.
        negative_clauses: dict[tuple[str, str], str] = {}
        for p in predictions:
            for item in p.predictions:
                if item.sentiment is Sentiment.NEGATIF:
                    negative_clauses.setdefault(
                        (p.review_id, item.aspect.value), item.source_sentence
                    )

        analysis_id = f"an_{uuid.uuid4().hex[:12]}"
        self.qna_store.put(
            analysis_id,
            QnAContext(
                index=index,
                aggregates=aggregates,
                total_reviews=len(reviews),
                traces=traces,
                negative_clauses=negative_clauses,
                # Kartu aksi ikut disimpan supaya pertanyaan "apa yang harus saya perbaiki
                # duluan?" dijawab dari urutan prioritas yang SAMA dengan yang dibaca pengguna
                # di laporan, bukan dari perhitungan kedua yang bisa berbeda hasilnya.
                actions=cards,
                reviews_with_complaint=reviews_with_complaint,
                category=category,
                period_start=min(dates, default=None),
                period_end=max(dates, default=None),
            ),
        )

        return AnalysisResult(
            analysis_id=analysis_id,
            summary=AnalysisSummary(
                total_reviews=len(reviews),
                reviews_with_image=sum(1 for r in reviews if r.has_image),
                reviews_with_complaint=reviews_with_complaint,
                period_start=min(dates, default=None),
                period_end=max(dates, default=None),
                executive_summary_text=self._executive_summary(aggregates, len(reviews), mode),
            ),
            # Jejak hanya ikut terbit bila diminta. Kartu yang disimpan di konteks sesi tetap
            # ramping - salinannya di sini yang membawa trace, bukan yang di penyimpanan.
            top_actions=(
                [c.model_copy(update={"trace": traces.get(c.action_id)}) for c in cards]
                if trace
                else cards
            ),
            aspect_aggregates=aggregates,
            visual_findings=visual_predictions,
            contradictions=self._contradiction_findings(
                fused, reviews, visual_predictions
            ),
            benchmark=benchmarks,
            opportunities=opportunities,
            data_quality=data_quality,
            ratings=ratings,
            products=products,
            period_history=period_history,
            category_guess=category_guess,
            benchmark_by_category=benchmark_by_category,
            warnings=warnings,
            mode=mode,
            confidence_calibrated=bool(getattr(self.text_adapter, "calibrated", False)),
            model_versions={
                "text": self.text_adapter.model_version,
                "embedding": getattr(self.embedding_adapter, "model_name", "tidak aktif"),
                "orchestrator": "tidak aktif" if self.orchestrator is None else "aktif",
            },
        )
