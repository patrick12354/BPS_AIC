"""TextModelAdapter - pembungkus model teks NLP-01 (blueprint bagian 27.2).

Adapter memisahkan service layer dari model konkret, sehingga mengganti kandidat model
(bagian 17.2) tidak menyentuh logika bisnis. Ia juga tempat FALLBACK deterministic dipasang:
jika checkpoint neural gagal dimuat, sistem turun ke jalur leksikon, bukan gagal total.

Model dimuat SEKALI saat startup, bukan per-request (bagian 27.2 model warm-up).
Inferensi berjalan CPU-only secara default - GPU hanya dipakai bila kebetulan tersedia.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from ..schemas import (
    Aspect,
    AspectPrediction,
    ProcessedReview,
    Sentiment,
    Severity,
    TextPrediction,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CHECKPOINT = REPO_ROOT / "models" / "indobert-nlp01" / "model.pt"
ML_TEXT = REPO_ROOT / "ml" / "text"

SENTIMENTS = ["negatif", "netral", "positif"]

# Klausa dipotong di 32 token, jadi batch besar pun tetap ringan; 64 cukup untuk menelan
# seluruh batch ulasan biasa dalam beberapa lintasan saja.
NEURAL_BATCH_SIZE = 64

# Keyakinan untuk jalur leksikon. Angka tetap, dan sengaja dibiarkan tetap: leksikon tidak
# menghasilkan probabilitas, jadi tidak ada yang bisa dilaporkan. Ia tidak pernah tampil di
# layar karena `TextModelAdapter.calibrated` selalu False pada jalur ini.
LEXICON_CONFIDENCE = 0.60


@dataclass(frozen=True)
class Prediction:
    """Hasil satu klausa: aspek apa saja, sentimennya, dan seberapa yakin.

    Menggantikan tuple `(aspects, sentiment)` yang dipakai sebelumnya. Tuple tiga elemen masih
    mungkin, tetapi `hasil.confidence` dapat dibaca tanpa menghitung posisi - dan yang ketiga
    inilah yang paling mudah tertukar diam-diam saat urutannya berubah.
    """

    aspects: list[Aspect]
    sentiment: Sentiment
    confidence: float


def _segment(text: str) -> list[str]:
    """Segmentasi klausa memakai modul yang sama dengan pipeline training.

    Memakai ulang kode training di sini disengaja: perbedaan sekecil apa pun antara cara teks
    dipecah saat latih dan saat inferensi akan menggeser distribusi input model.
    """
    if str(ML_TEXT) not in sys.path:
        sys.path.insert(0, str(ML_TEXT))
    from preprocess import normalize, split_clauses  # noqa: PLC0415

    return split_clauses(normalize(text))


def _severity_from(sentiment: Sentiment, rating: int | None) -> Severity:
    """Heuristik severity yang sama dengan pelabelan Fase 1 - konsisten latih vs inferensi."""
    if sentiment != Sentiment.NEGATIF:
        return Severity.RENDAH
    if rating is None:
        return Severity.SEDANG
    if rating <= 2:
        return Severity.TINGGI
    if rating == 3:
        return Severity.SEDANG
    return Severity.RENDAH


class TextModelAdapter:
    """Memuat checkpoint IndoBERT dua head; jatuh ke leksikon bila gagal."""

    def __init__(self, checkpoint: Path | None = None, device: str | None = None):
        self.checkpoint_path = checkpoint or DEFAULT_CHECKPOINT
        self.model = None
        self.tokenizer = None
        self.threshold = 0.5
        self.model_version = "lexicon-fallback"
        self.mode = "fallback"
        # Suhu kalibrasi (L1). 1,0 berarti belum dikalibrasi - membagi dengan satu tidak
        # mengubah apa pun, jadi jalur inferensinya sama persis dengan sebelum fitur ini ada.
        self.sentiment_temperature = 1.0
        self.aspect_temperature = 1.0
        # Penentu apakah angka keyakinan boleh sampai ke layar. Dibaca dari isi bundle, bukan
        # dari saklar konfigurasi: checkpoint yang belum dikalibrasi tidak bisa "dianggap"
        # terkalibrasi karena seseorang lupa mematikan sesuatu.
        self.calibrated = False
        # Alasan turun ke leksikon, atau None bila model neural memang aktif. Ini dibaca
        # /readiness dan ditampilkan sebagai peringatan. Sebelumnya kegagalan hanya dicetak
        # ke stdout: sistem menjawab "siap" tanpa peringatan apa pun sementara model yang
        # menjadi inti produk tidak pernah dimuat - persis yang terjadi pada image Docker,
        # dan tidak ketahuan sampai keluaran `/models` diperiksa manual.
        self.fallback_reason: str | None = None
        self._device = device
        self._load()

    def _load(self) -> None:
        if not self.checkpoint_path.exists():
            self.fallback_reason = (
                f"checkpoint tidak ditemukan di {self.checkpoint_path} - "
                "jalankan scripts/download_checkpoint.py"
            )
            return
        try:
            import torch  # noqa: PLC0415
            from transformers import AutoTokenizer  # noqa: PLC0415

            if str(ML_TEXT) not in sys.path:
                sys.path.insert(0, str(ML_TEXT))
            from model import DualHeadClassifier  # noqa: PLC0415

            bundle = torch.load(self.checkpoint_path, map_location="cpu", weights_only=False)
            model = DualHeadClassifier(bundle["base_model"])
            model.load_state_dict(bundle["state_dict"])
            model.eval()

            device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
            self.model = model.to(device)
            self._torch = torch
            self._device = device
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.checkpoint_path.parent))
            self.threshold = float(bundle.get("aspect_threshold", 0.5))
            self.aspects = [Aspect(a) for a in bundle["aspects"]]

            # Suhu kalibrasi diambil bila bundle-nya membawanya (ditulis ml/text/calibrate.py).
            #
            # Ambangnya ikut ditukar dengan versi yang sudah digeser bersama suhunya. Tanpa
            # penukaran itu, kalibrasi yang seharusnya hanya menyentuh angka keyakinan akan
            # diam-diam mengubah aspek mana yang terdeteksi - dan seluruh evaluasi aspek yang
            # sudah dilaporkan berhenti berlaku.
            suhu_sentimen = float(bundle.get("sentiment_temperature") or 1.0)
            suhu_aspek = float(bundle.get("aspect_temperature") or 1.0)
            if suhu_sentimen > 0 and suhu_sentimen != 1.0:
                self.sentiment_temperature = suhu_sentimen
                self.aspect_temperature = suhu_aspek if suhu_aspek > 0 else 1.0
                self.threshold = float(
                    bundle.get("aspect_threshold_calibrated", self.threshold)
                )
                self.calibrated = True

            versi = f"indobert-nlp01@thr{round(self.threshold, 4)}"
            self.model_version = (
                f"{versi}+cal{self.sentiment_temperature}" if self.calibrated else versi
            )
            self.mode = "full"
        except Exception as exc:  # pragma: no cover - jalur degradasi
            # Kegagalan memuat model TIDAK boleh menjatuhkan sistem (prinsip failure-tolerant).
            print(f"[TextModelAdapter] checkpoint gagal dimuat, memakai leksikon: {exc}")
            self.model = None
            self.mode = "fallback"
            self.fallback_reason = f"{type(exc).__name__}: {exc}"

    def _predict_neural(self, clauses: list[str]) -> list[Prediction]:
        """Inferensi atas klausa dari SELURUH batch sekaligus, bukan per ulasan.

        Sebelumnya `classify()` memanggil fungsi ini sekali per ulasan, sehingga 66 ulasan
        berarti 66 forward pass terpisah - masing-masing berisi 2-4 klausa. Ongkos tetap satu
        panggilan (tokenisasi, penyusunan tensor, penjadwalan thread) karenanya dibayar 66
        kali untuk pekerjaan yang muat dalam beberapa batch.

        Padding tidak menjadi masalah di sini seperti pada embedding: klausa dipotong di 32
        token dan panjangnya seragam. Hasilnya identik dengan versi per-ulasan - `attention_mask`
        menutup padding dan mean pooling di DualHeadClassifier hanya menjumlah token non-padding.

        Keyakinan yang dikembalikan adalah **probabilitas sentimen terkalibrasi**, bukan
        probabilitas aspek dan bukan gabungan keduanya. Pilihan itu punya alasan yang dapat
        dipertahankan: ECE diukur untuk head sentimen (ml/text/calibrate.py), sehingga hanya
        angka inilah yang punya galat kalibrasi terukur di sampingnya. Probabilitas aspek sudah
        habis perannya begitu ia melewati ambang - ia menentukan apakah prediksi ini ADA, bukan
        seberapa yakin isinya - dan mengalikan keduanya akan mengarang asumsi independensi
        antar head yang tidak pernah diuji.
        """
        torch = self._torch
        out: list[Prediction] = []

        with torch.no_grad():
            for start in range(0, len(clauses), NEURAL_BATCH_SIZE):
                enc = self.tokenizer(
                    clauses[start : start + NEURAL_BATCH_SIZE],
                    truncation=True,
                    max_length=32,
                    padding=True,
                    return_tensors="pt",
                ).to(self._device)
                aspect_logits, sentiment_logits = self.model(
                    enc["input_ids"], enc["attention_mask"]
                )
                # Suhu dibagikan di sini, satu baris, persis seperti dijanjikan L1. Pada
                # checkpoint yang belum dikalibrasi suhunya 1,0 dan operasinya tidak berefek.
                aspect_probs = torch.sigmoid(
                    aspect_logits / self.aspect_temperature
                ).cpu().numpy()
                sentiment_probs = torch.softmax(
                    sentiment_logits / self.sentiment_temperature, dim=-1
                ).cpu().numpy()

                for a_row, s_row in zip(aspect_probs, sentiment_probs):
                    aspects = [a for a, p in zip(self.aspects, a_row) if p >= self.threshold]
                    idx = int(s_row.argmax())
                    out.append(
                        Prediction(
                            aspects=aspects,
                            sentiment=Sentiment(SENTIMENTS[idx]),
                            # Angka ini hanya boleh sampai ke layar bila `self.calibrated`.
                            # Softmax mentah dari jaringan yang belum dikalibrasi terkenal
                            # terlalu percaya diri, dan temuan Fase 8 mengukurnya pada model
                            # ini: 113 dari 128 negatif yang terlewat diprediksi dengan
                            # P(negatif) di bawah 0,10. Yakin, dan salah.
                            confidence=float(s_row[idx]),
                        )
                    )

        return out

    def _predict_lexicon(self, clauses: list[str]) -> list[Prediction]:
        """Jalur fallback deterministic (bagian 17.1) - akurasi lebih rendah, tetap berjalan.

        Jalur ini tidak menghasilkan probabilitas sama sekali - ia menghitung selisih jumlah
        kata positif dan negatif. `confidence` karenanya tetap penanda tetap di sini, dan
        `self.calibrated` tetap False, sehingga angkanya tidak pernah sampai ke layar.
        Memaksakan skor leksikon menjadi angka 0-1 yang terlihat seperti probabilitas justru
        mengarang persis hal yang sedang diperbaiki fitur ini.
        """
        if str(ML_TEXT) not in sys.path:
            sys.path.insert(0, str(ML_TEXT))
        from lexicon import ASPECT_PATTERNS, FALLBACK_ASPECT, FALLBACK_PATTERN  # noqa: PLC0415
        from preprocess import polarity_score  # noqa: PLC0415

        results: list[Prediction] = []
        for clause in clauses:
            aspects = [Aspect(a) for a, pat in ASPECT_PATTERNS.items() if pat.search(clause)]
            if not aspects and FALLBACK_PATTERN.search(clause):
                aspects = [Aspect(FALLBACK_ASPECT)]
            pos, neg = polarity_score(clause)
            sentiment = (
                Sentiment.POSITIF if pos > neg else Sentiment.NEGATIF if neg > pos else Sentiment.NETRAL
            )
            results.append(
                Prediction(aspects=aspects, sentiment=sentiment, confidence=LEXICON_CONFIDENCE)
            )
        return results

    def classify(self, reviews: list[ProcessedReview]) -> list[TextPrediction]:
        """classify_text_aspects() - tool contract bagian 27.3.

        Seluruh ulasan disegmentasi lebih dulu, klausanya digabung menjadi satu daftar datar,
        lalu SATU kali inferensi dijalankan atas daftar itu. Pemetaan balik ke ulasan asalnya
        memakai rentang indeks yang dicatat saat penggabungan.
        """
        segments = [_segment(r.clean_text) for r in reviews]

        flat: list[str] = []
        spans: list[tuple[int, int]] = []
        for clauses in segments:
            spans.append((len(flat), len(flat) + len(clauses)))
            flat.extend(clauses)

        if flat:
            per_clause = (
                self._predict_neural(flat) if self.model is not None
                else self._predict_lexicon(flat)
            )
        else:
            per_clause = []

        predictions: list[TextPrediction] = []
        for review, clauses, (start, end) in zip(reviews, segments, spans):
            items: list[AspectPrediction] = []
            for clause, hasil in zip(clauses, per_clause[start:end]):
                for aspect in hasil.aspects:
                    items.append(
                        AspectPrediction(
                            aspect=aspect,
                            sentiment=hasil.sentiment,
                            severity=_severity_from(hasil.sentiment, review.rating),
                            confidence=hasil.confidence,
                            source_sentence=clause,
                        )
                    )
            predictions.append(
                TextPrediction(review_id=review.review_id, predictions=items,
                               model_version=self.model_version)
            )

        return predictions
