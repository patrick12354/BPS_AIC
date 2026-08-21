"""VisionModelAdapter - jalur visual VIS-01b (L3), lengkap dengan gerbangnya sendiri.

Berkas ini menyelesaikan satu hal yang selama ini menganga: gerbang go/no-go modul visual
diputuskan, ditulis di dokumen, lalu **dijalankan oleh kedisiplinan manusia**. Tidak ada satu
baris kode pun yang mencegah seseorang menyalakan model visual yang belum lolos - yang
mencegahnya cuma ingatan bahwa ia belum lolos.

Di sini vonis itu menjadi syarat yang dieksekusi. Artefak probe membawa medan `keputusan`
hasil `ml/visual/linear_probe.py`, dan adapter ini **menolak aktif** kalau isinya NO-GO. Alasan
penolakannya keluar lewat `/readiness`, jalur yang sama dengan kegagalan checkpoint teks,
sehingga keadaan "jalur visual mati dan inilah sebabnya" selalu terbaca dari luar.

Tiga sifat lain yang mengikat:

- **Abstention adalah bawaan, bukan tambahan.** Ambangnya datang dari artefak - nilai yang
  dikalibrasi di dalam fold latih saat evaluasi - sehingga produksi memakai ambang yang sama
  dengan yang angkanya dilaporkan. Di bawah ambang itu, hasilnya `abstain=True` dengan alasan,
  bukan tebakan berkeyakinan rendah (bagian 19.2).
- **Perumusannya biner: "perlu diperiksa" atau tidak.** Empat kelas adalah bentuk yang dikunci
  Fase 0 dan tetap ada di taksonomi, tetapi dua di antaranya hanya punya segelintir label.
  Yang dikirim ke pengguna adalah keputusan yang benar-benar dibutuhkannya - foto ini perlu
  Anda lihat sendiri atau tidak - dan label `produk_rusak` dipakai sebagai penanda antrean
  periksa, bukan sebagai diagnosis kondisi barang.
- **Encoder tidak pernah dilatih.** CLIP beku, probe linear di atasnya. Tidak ada yang dapat
  dihafal encoder karena tidak ada yang diajarkan kepadanya.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..schemas import VisualLabel, VisualPrediction

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PROBE = REPO_ROOT / "models" / "visual-probe" / "probe.npz"

# Vonis gerbang yang boleh menyalakan jalur ini. "CONDITIONAL GO" ikut, dan konsekuensinya
# tertulis di `putuskan()` pada linear_probe.py: hasilnya boleh tampil sebagai fitur pendukung
# yang menyertakan keterbatasannya, tidak boleh disebut kapabilitas terbukti.
GERBANG_LOLOS = {"GO", "CONDITIONAL GO"}

# Kelas positif probe dipetakan ke label taksonomi mana. `PRODUK_RUSAK` dipakai sebagai
# penanda "ada indikasi masalah fisik" - bukan klaim bahwa barangnya memang rusak. Perumusan
# empat kelas tidak pernah punya cukup label untuk membedakan rusak, salah kirim, dan kemasan
# rusak, dan menebak di antara ketiganya akan mengarang kepastian yang tidak ada.
POSITIF = "perlu_diperiksa"


class VisionModelAdapter:
    """Memuat probe linear di atas CLIP beku; nonaktif bila gerbangnya belum lolos."""

    def __init__(self, probe_path: Path | None = None, device: str | None = None):
        self.probe_path = probe_path or DEFAULT_PROBE
        self.active = False
        self.meta: dict = {}
        self.model_version = "visual-nonaktif"
        self.min_confidence = 0.5
        # Alasan jalur ini mati, atau None bila ia hidup. Dibaca /readiness - keadaan "visual
        # mati" harus terbaca dari luar, bukan hanya diketahui orang yang membaca kode.
        self.inactive_reason: str | None = None
        self._clip = None
        self._processor = None
        self._device = device
        self._load()

    def _load(self) -> None:
        if not self.probe_path.exists():
            self.inactive_reason = (
                f"artefak probe visual tidak ada di {self.probe_path} - jalankan "
                "ml/visual/linear_probe.py --simpan setelah foto berlabel tersedia"
            )
            return
        try:
            import numpy as np  # noqa: PLC0415

            bundle = np.load(self.probe_path, allow_pickle=False)
            self.meta = json.loads(str(bundle["meta"]))
            keputusan = self.meta.get("keputusan", "NO-GO")

            # Gerbang dijalankan DI SINI, sebelum apa pun dimuat. Menolak setelah model
            # terlanjur hidup akan menyisakan jalan bagi seseorang untuk melewatinya.
            if keputusan not in GERBANG_LOLOS:
                self.inactive_reason = (
                    f"gerbang visual berstatus {keputusan} - jalur visual sengaja tidak "
                    f"dinyalakan. {self.meta.get('alasan', '')}".strip()
                )
                return

            self._coef = bundle["coef"]
            self._intercept = bundle["intercept"]
            self._classes = [str(c) for c in bundle["classes"]]
            self.min_confidence = float(self.meta.get("min_confidence", 0.5))
            self.model_version = (
                f"clip-probe@{self.meta.get('encoder', '?')}"
                f"+conf{round(self.min_confidence, 2)}"
            )
            self.active = True
        except Exception as exc:  # pragma: no cover - jalur degradasi
            # Kegagalan jalur visual TIDAK boleh menjatuhkan analisis (bagian 20, ADR-014).
            self.inactive_reason = f"{type(exc).__name__}: {exc}"
            self.active = False

    def _encoder(self):
        """Muat CLIP saat pertama dibutuhkan, bukan saat startup.

        Berbeda dari model teks yang sengaja dimuat di awal: model teks dipakai setiap
        analisis, sedangkan sebagian besar batch tidak membawa foto sama sekali. Membayar
        beberapa ratus megabyte memori untuk jalur yang tidak dilewati adalah harga yang tidak
        perlu dibayar setiap deployment.
        """
        if self._clip is None:
            import torch  # noqa: PLC0415
            from transformers import CLIPModel, CLIPProcessor  # noqa: PLC0415

            nama = self.meta.get("encoder", "openai/clip-vit-base-patch32")
            self._torch = torch
            self._clip = CLIPModel.from_pretrained(nama).eval()
            self._processor = CLIPProcessor.from_pretrained(nama)
            self._device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
            self._clip = self._clip.to(self._device)
        return self._clip, self._processor

    def _probabilitas(self, fitur):
        """Softmax dari probe linear. Ditulis tangan supaya sklearn tidak menjadi dependensi
        runtime image API - ia hanya dibutuhkan saat MELATIH."""
        import numpy as np  # noqa: PLC0415

        skor = fitur @ self._coef.T + self._intercept
        if skor.shape[1] == 1:  # regresi logistik biner sklearn menyimpan satu baris koefisien
            skor = np.concatenate([-skor, skor], axis=1)
        skor = skor - skor.max(axis=1, keepdims=True)
        exp = np.exp(skor)
        return exp / exp.sum(axis=1, keepdims=True)

    def classify(self, images: list[tuple[str, str, bytes]]) -> list[VisualPrediction]:
        """classify_review_image() - tool contract bagian 27.3.

        Args:
            images: daftar (image_ref, review_id, byte gambar). Byte, bukan path: gambar tidak
                pernah menyentuh cakram (ADR-010, kebijakan session-only).

        Returns:
            Satu VisualPrediction per gambar. Daftar KOSONG bila adapter nonaktif - itu bukan
            error dan tidak boleh diperlakukan sebagai error oleh pemanggilnya.
        """
        if not self.active or not images:
            return []

        import io  # noqa: PLC0415

        import numpy as np  # noqa: PLC0415
        from PIL import Image  # noqa: PLC0415

        model, processor = self._encoder()
        torch = self._torch

        refs = [(ref, rid) for ref, rid, _ in images]
        pil = [Image.open(io.BytesIO(b)).convert("RGB") for _, _, b in images]

        with torch.no_grad():
            pix = processor(images=pil, return_tensors="pt").to(self._device)
            fitur = model.get_image_features(**pix)
            fitur = fitur / fitur.norm(dim=-1, keepdim=True)
            fitur = fitur.cpu().numpy().astype(np.float32)

        probs = self._probabilitas(fitur)
        i_positif = self._classes.index(POSITIF) if POSITIF in self._classes else 1

        hasil: list[VisualPrediction] = []
        for (ref, review_id), row in zip(refs, probs):
            atas = float(row.max())
            positif = int(row.argmax()) == i_positif
            if atas < self.min_confidence:
                hasil.append(
                    VisualPrediction(
                        image_ref=ref, review_id=review_id, label=None, abstain=True,
                        confidence=round(atas, 4),
                        abstain_reason=(
                            f"keyakinan {atas:.0%} di bawah ambang {self.min_confidence:.0%} - "
                            "sistem sengaja tidak menebak"
                        ),
                        model_version=self.model_version,
                    )
                )
                continue
            hasil.append(
                VisualPrediction(
                    image_ref=ref, review_id=review_id,
                    # Penanda antrean periksa, bukan diagnosis. Lihat catatan pada POSITIF.
                    label=VisualLabel.PRODUK_RUSAK if positif else VisualLabel.NORMAL,
                    abstain=False, confidence=round(atas, 4),
                    model_version=self.model_version,
                )
            )
        return hasil
