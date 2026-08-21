"""Test S1 - draf balasan penjual.

Yang diuji di sini bukan keindahan kalimatnya melainkan empat janji yang membuat fitur ini
boleh ada: deterministik, tidak pernah menjanjikan uang atas nama pengguna, tidak pernah
menyalin kalimat pembeli ke dalam balasan yang terbit atas nama toko, dan selalu bersandar
pada ulasan yang memang mendukung kartunya.
"""

from __future__ import annotations

from app.schemas import (
    ActionCard,
    ActionCategory,
    Aspect,
    EvidenceCitation,
    Severity,
    Trend,
    Urgency,
)
from app.tools.replies import KATA_RUJUKAN, build_reply_draft, build_reply_drafts


def _cite(review_id="r1", quote="paketnya telat seminggu", rating=2) -> EvidenceCitation:
    return EvidenceCitation(
        citation_id=f"c-{review_id}", review_id=review_id, quote=quote,
        relevance_score=0.7, aspect=Aspect.PENGIRIMAN, rating=rating,
    )


def _card(aspect=Aspect.PENGIRIMAN, severity=Severity.SEDANG, quotes=None) -> ActionCard:
    return ActionCard(
        action_id="ACT-001",
        title="Tinjau proses pengiriman pesanan",
        one_line_summary="8 dari 40 ulasan (20%) menyebut masalah pada pengiriman",
        aspect=aspect,
        frequency=8,
        frequency_total=10,
        severity=severity,
        confidence=0.8,
        trend=Trend.STABIL,
        priority_score=42.5,
        urgency=Urgency.SEDANG,
        evidence_quotes=quotes if quotes is not None else [_cite()],
        priority_reasoning="8 dari 40 ulasan (20%) menyebut masalah pada aspek ini.",
        recommended_action="Tinjau cara Anda mengemas dan mengirim pesanan.",
        action_category=ActionCategory.PACKAGING,
        expected_outcome="Keluhan menurun",
        estimated_effort="rendah",
        suggested_owner="pemilik toko",
        risk_if_not_done="Keluhan berulang",
        risk_if_recommendation_wrong="Periksa dulu kutipannya",
    )


# ---------------------------------------------------------------- determinisme


def test_draf_sama_persis_pada_pemanggilan_berulang():
    """Sifat yang hilang begitu ada `random` atau LLM di jalurnya."""
    a = build_reply_draft(_cite(), Aspect.PENGIRIMAN, Severity.SEDANG)
    b = build_reply_draft(_cite(), Aspect.PENGIRIMAN, Severity.SEDANG)
    assert a.draft == b.draft
    assert a.template_id == b.template_id


def test_ulasan_berbeda_tidak_dibalas_dengan_kalimat_yang_sama():
    """Dua puluh balasan identik terbaca sebagai bot, dan itu merusak kepercayaan pembaca."""
    drafts = {
        build_reply_draft(_cite(f"r{i}"), Aspect.PENGIRIMAN, Severity.SEDANG).draft
        for i in range(12)
    }
    assert len(drafts) > 1


def test_varian_slot_tidak_bergerak_serempak():
    """Tanpa nama slot ikut di-hash, bank frasanya menyusut jadi tiga balasan tetap.

    Dua digit terakhir `template_id` adalah indeks pengakuan dan indeks langkah. Kalau
    keduanya selalu bergerak bersama, yang muncul hanya kombinasi diagonal - 00, 11, 22 -
    dan tiga varian per slot berhenti berarti apa pun.
    """
    kombinasi = {
        build_reply_draft(_cite(f"r{i}"), Aspect.KEMASAN, Severity.SEDANG).template_id[-2:]
        for i in range(30)
    }
    assert len(kombinasi) > 3, sorted(kombinasi)


# ---------------------------------------------------------------- batas wewenang


def test_keputusan_uang_tidak_pernah_ditulis_sistem():
    draft = build_reply_draft(_cite(), Aspect.KUALITAS_PRODUK, Severity.TINGGI)
    assert draft.decision_slots
    assert "[keputusan Anda:" in draft.draft
    # Tidak ada satu pun janji yang berdiri sendiri tanpa tanda kurung keputusan.
    for kata in ["kami ganti barangnya", "kami refund", "uang Anda kami kembalikan"]:
        assert kata not in draft.draft.lower()


def test_slot_keputusan_hanya_muncul_pada_keluhan_berat():
    """Menawarkan refund untuk keluhan ringan menciptakan biaya yang tidak diminta siapa pun."""
    ringan = build_reply_draft(_cite(), Aspect.KUALITAS_PRODUK, Severity.RENDAH)
    assert ringan.decision_slots == []
    assert "[keputusan Anda:" not in ringan.draft


def test_aspek_tanpa_jalan_keluar_barang_tidak_diberi_slot():
    """Harga tidak punya bentuk "ganti barang"; memasang slotnya berarti mengarang pilihan."""
    draft = build_reply_draft(_cite(), Aspect.HARGA_VALUE, Severity.TINGGI)
    assert draft.decision_slots == []


# ---------------------------------------------------------------- isi balasan


def test_balasan_menyebut_hal_yang_benar_benar_dikeluhkan():
    """Dipakai kemasan, bukan pengiriman: kalimat pengakuan pengiriman sudah menyebut
    keterlambatan pada sebagian variannya, sehingga penjaga pengulangan menahan rujukannya -
    perilaku yang benar, tetapi membuat aspek itu tidak cocok sebagai contoh di sini."""
    draft = build_reply_draft(_cite(quote="dusnya penyok parah"), Aspect.KEMASAN,
                              Severity.SEDANG)
    assert KATA_RUJUKAN[Aspect.KEMASAN]["penyok"] in draft.draft


def test_kalimat_pembeli_tidak_pernah_disalin_ke_dalam_balasan():
    """Daftar rujukan tertutup: umpatan, tuduhan, dan nama yang lolos redaksi tidak punya
    jalan masuk ke teks yang terbit atas nama toko."""
    kotor = "barangnya zonk parah anjir, si BUDI penjualnya nipu, telat pula"
    draft = build_reply_draft(_cite(quote=kotor), Aspect.PENGIRIMAN, Severity.SEDANG)
    for kata in ["zonk", "anjir", "BUDI", "nipu"]:
        assert kata.lower() not in draft.draft.lower()


def test_ulasan_tanpa_kata_yang_dikenali_tetap_dapat_balasan():
    """Balasannya sedikit lebih umum, dan itu jauh lebih baik daripada menebak topik."""
    draft = build_reply_draft(_cite(quote="hmm ya begitulah"), Aspect.PENGIRIMAN,
                              Severity.SEDANG)
    assert len(draft.draft) > 40
    assert "khususnya soal" not in draft.draft


def test_rujukan_diambil_dari_klausa_negatif_bukan_seluruh_ulasan():
    """Ulasan campuran memuat kata dari kedua sisi; mencari di seluruh teks bisa menangkap
    kata dari bagian yang justru memuji."""
    campuran = "pengiriman cepat banget, cuma dusnya penyok parah"
    draft = build_reply_draft(
        _cite(quote=campuran), Aspect.KEMASAN, Severity.SEDANG,
        clause="cuma dusnya penyok parah",
    )
    assert KATA_RUJUKAN[Aspect.KEMASAN]["penyok"] in draft.draft


def test_rujukan_ditahan_saat_pengakuan_sudah_menyebutnya():
    """"atas keterlambatan pengiriman, khususnya soal keterlambatannya" adalah tanda paling
    khas balasan tempelan - kalimat yang mengulang dirinya sendiri."""
    for i in range(20):
        draft = build_reply_draft(
            _cite(f"r{i}", quote="paketnya telat seminggu"), Aspect.PENGIRIMAN, Severity.SEDANG
        )
        assert draft.draft.lower().count("keterlambatan") <= 1, draft.draft


# ---------------------------------------------------------------- per kartu


def test_satu_draf_untuk_tiap_ulasan_pendukung_kartu():
    card = _card(quotes=[_cite("r1"), _cite("r2"), _cite("r3")])
    drafts = build_reply_drafts(card)
    assert [d.review_id for d in drafts] == ["r1", "r2", "r3"]
    assert all(d.aspect is Aspect.PENGIRIMAN for d in drafts)


def test_kartu_tanpa_bukti_tidak_menghasilkan_draf():
    """Menyusun balasan untuk ulasan yang tidak pernah dilihat pengguna sebagai bukti akan
    terasa datang entah dari mana."""
    assert build_reply_drafts(_card(quotes=[])) == []


def test_keparahan_kartu_menentukan_ada_tidaknya_slot():
    card = _card(aspect=Aspect.KUALITAS_PRODUK, severity=Severity.TINGGI)
    assert build_reply_drafts(card)[0].decision_slots


def test_rujukan_tidak_menyeberang_ke_aspek_lain():
    """Ulasan menyinggung beberapa hal sekaligus; kata pertama yang cocok belum tentu kata
    yang membuat ulasan itu masuk ke kartu ini.

    Terlihat di produksi sebagai "mohon maaf kualitas barangnya belum seperti seharusnya,
    khususnya soal harganya" - dua topik dalam satu kalimat, dan pembaca yang menerimanya tahu
    persis bahwa yang menulisnya tidak membaca ulasannya.
    """
    campuran = "harganya mahal untuk kualitas segini"
    kualitas = build_reply_draft(_cite(quote=campuran), Aspect.KUALITAS_PRODUK, Severity.SEDANG)
    assert "harganya" not in kualitas.draft
    assert "khususnya soal" not in kualitas.draft

    # Kartu harga tetap membicarakan harga - dari kalimat pengakuannya sendiri, dengan atau
    # tanpa rujukan tambahan.
    harga = build_reply_draft(_cite(quote=campuran), Aspect.HARGA_VALUE, Severity.SEDANG)
    assert "harga" in harga.draft.lower()


def test_frasa_panjang_menang_atas_kata_pendek():
    """Tanpa pengurutan menurut panjang, hasilnya bergantung urutan penulisan daftar."""
    draft = build_reply_draft(
        _cite(quote="salah warna yang dikirim, bukan yang dipesan"),
        Aspect.UKURAN_VARIAN, Severity.SEDANG,
    )
    assert KATA_RUJUKAN[Aspect.UKURAN_VARIAN]["salah warna"] in draft.draft


def test_rujukan_yang_cuma_mengulang_nama_aspek_tidak_ada_di_daftar():
    """Daftar dikurasi, bukan dilengkapi: "tidak sesuai" pada kartu kesesuaian deskripsi
    hanyalah nama aspeknya diucapkan ulang."""
    assert "tidak sesuai" not in KATA_RUJUKAN[Aspect.KESESUAIAN_DESKRIPSI]
    assert "kekecilan" not in KATA_RUJUKAN[Aspect.UKURAN_VARIAN]
