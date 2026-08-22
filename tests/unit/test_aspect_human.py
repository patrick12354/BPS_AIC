"""Test paket validasi aspek manusia (scripts/build_aspect_human_pack.py) dan evaluatornya.

Yang dijaga bukan angkanya - belum ada label manusia saat test ini ditulis - melainkan sifat
yang membuat angka kelak SAH: paket deterministik, tidak bocor, tidak menjangkarkan pelabel;
kappa dihitung benar; baris yang tidak disepakati tidak diam-diam masuk rujukan.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ml" / "text"))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pack_mod = _load(REPO / "scripts" / "build_aspect_human_pack.py", "build_aspect_human_pack")
eval_mod = _load(REPO / "ml" / "text" / "evaluate_aspect_human.py", "evaluate_aspect_human")

GOLD_ADA = (REPO / "data" / "annotation" / "gold_labels.csv").exists()


# ---------------------------------------------------------------- kappa


def test_kappa_sempurna_adalah_satu():
    a = np.array([1, 0, 1, 1, 0, 0, 1, 0])
    assert eval_mod.cohen_kappa(a, a) == 1.0


def test_kappa_kebalikan_total_negatif():
    a = np.array([1, 0, 1, 0, 1, 0])
    assert eval_mod.cohen_kappa(a, 1 - a) < 0


def test_kappa_sesuai_hitungan_tangan():
    """Contoh buku: po=0.7, pe=0.5 -> kappa 0.4."""
    a = np.array([1] * 5 + [0] * 5)
    b = np.array([1, 1, 1, 1, 0, 0, 0, 0, 1, 1])  # sepakat 7 dari 10
    # pa1 = 0.5, pb1 = 0.6 -> pe = 0.5*0.6 + 0.5*0.4 = 0.5 ; po = 0.7 -> (0.7-0.5)/(1-0.5) = 0.4
    assert eval_mod.cohen_kappa(a, b) == pytest.approx(0.4)


def test_kappa_tak_terdefinisi_bila_semua_label_sama():
    """Dua pelabel yang sama-sama tidak pernah memberi label tidak 'sepakat sempurna' - kappa
    tidak terdefinisi, dan melaporkannya 1,0 akan mengarang kesepakatan."""
    assert eval_mod.cohen_kappa(np.zeros(10, int), np.zeros(10, int)) is None


def test_f1_biner_benar():
    y = np.array([1, 1, 0, 0, 1])
    p = np.array([1, 0, 0, 1, 1])  # tp=2 fp=1 fn=1 -> p=2/3 r=2/3 f1=2/3
    assert eval_mod.f1_binary(y, p) == pytest.approx(2 / 3, abs=1e-4)


# ---------------------------------------------------------------- rujukan


def _row(cid, text, aspects, sent="negatif"):
    r = {"clause_id": cid, "clause_text": text, "sentimen": sent}
    for a in eval_mod.ALL_ASPECTS:
        r[f"asp_{a}"] = "1" if a in aspects else ""
    return r


def test_baris_tidak_sepakat_tidak_masuk_rujukan_tanpa_adjudikasi():
    a = {"c1": _row("c1", "paketnya telat", ["pengiriman"]),
         "c2": _row("c2", "dusnya penyok", ["kemasan"])}
    b = {"c1": _row("c1", "paketnya telat", ["pengiriman"]),
         "c2": _row("c2", "dusnya penyok", ["kualitas_produk"])}
    ag = eval_mod.agreement(a, b)
    ref, pending = eval_mod.reference_labels(a, b, ag["ids"], None)
    assert set(ref) == {"c1"}
    assert [p["clause_id"] for p in pending] == ["c2"]
    assert pending[0]["label_A"] == "kemasan" and pending[0]["label_B"] == "kualitas_produk"


def test_keputusan_adjudikator_dipakai_bila_ada():
    a = {"c2": _row("c2", "dusnya penyok", ["kemasan"])}
    b = {"c2": _row("c2", "dusnya penyok", ["kualitas_produk"])}
    adj = {"c2": _row("c2", "dusnya penyok", ["kemasan"])}
    ag = eval_mod.agreement(a, b)
    ref, pending = eval_mod.reference_labels(a, b, ag["ids"], adj)
    assert "c2" in ref and not pending
    assert ref["c2"][eval_mod.ALL_ASPECTS.index("kemasan")] == 1


def test_klausa_yang_belum_diisi_salah_satu_pelabel_dikeluarkan():
    a = {"c1": _row("c1", "x", ["pengiriman"]), "c9": _row("c9", "y", ["kemasan"], sent="")}
    b = {"c1": _row("c1", "x", ["pengiriman"]), "c9": _row("c9", "y", ["kemasan"])}
    assert eval_mod.agreement(a, b)["ids"] == ["c1"]


def test_aspek_dengan_kappa_rendah_ditandai_tidak_dapat_ditafsirkan():
    rows_a, rows_b = {}, {}
    for i in range(40):
        # Sepakat penuh pada 'pengiriman'; pada 'kemasan' B memberi label acak-bergantian.
        rows_a[f"c{i}"] = _row(f"c{i}", "t", ["pengiriman"] + (["kemasan"] if i % 2 == 0 else []))
        rows_b[f"c{i}"] = _row(f"c{i}", "t", ["pengiriman"] + (["kemasan"] if i % 4 == 0 else []))
    per = eval_mod.agreement(rows_a, rows_b)["per_aspect"]
    assert per["pengiriman"]["interpretable"] is False  # kappa tak terdefinisi (semua 1)
    assert per["kemasan"]["kappa"] is not None


# ---------------------------------------------------------------- paket


@pytest.mark.skipif(not GOLD_ADA, reason="gold_labels.csv tidak ada di mesin ini")
def test_paket_deterministik_dan_tanpa_duplikat():
    p1 = pack_mod.build_pack(seed=42)
    p2 = pack_mod.build_pack(seed=42)
    assert [r["clause_id"] for r in p1] == [r["clause_id"] for r in p2]
    ids = [r["clause_id"] for r in p1]
    assert len(ids) == len(set(ids))
    assert len(p1) == pack_mod.N_FROM_GOLD + pack_mod.N_FRESH


@pytest.mark.skipif(not GOLD_ADA, reason="gold_labels.csv tidak ada di mesin ini")
def test_setiap_aspek_terwakili_minimal_jatahnya():
    """Tanpa jatah minimum, aspek langka praktis hilang dan kappa-nya tak dapat dihitung."""
    p = pack_mod.build_pack(seed=42)
    with (REPO / "data" / "annotation" / "gold_labels.csv").open(encoding="utf-8") as fh:
        gold = {r["clause_id"]: r for r in csv.DictReader(fh)}
    for a in pack_mod.ALL_ASPECTS:
        n = sum(1 for r in p if r["sumber"] == "gold" and gold[r["clause_id"]].get(f"asp_{a}") == "1")
        assert n >= pack_mod.MIN_PER_ASPECT, a


@pytest.mark.skipif(not GOLD_ADA, reason="gold_labels.csv tidak ada di mesin ini")
def test_klausa_segar_tidak_berasal_dari_gold():
    p = pack_mod.build_pack(seed=42)
    with (REPO / "data" / "annotation" / "gold_labels.csv").open(encoding="utf-8") as fh:
        gold_texts = {r["clause_text"] for r in csv.DictReader(fh)}
    for r in p:
        if r["sumber"] == "shopee_asli":
            assert r["clause_text"] not in gold_texts


@pytest.mark.skipif(not GOLD_ADA, reason="gold_labels.csv tidak ada di mesin ini")
def test_berkas_pelabel_tidak_memuat_label_lama(tmp_path):
    """Yang ingin diukur adalah independensi; label lama di berkas pelabel menjangkarkannya."""
    p = pack_mod.build_pack(seed=42)
    out = tmp_path / "A.csv"
    pack_mod.annotator_csv(p, out, seed=1)
    with out.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(p)
    for r in rows:
        assert all(r[f"asp_{a}"] == "" for a in pack_mod.ALL_ASPECTS)
        assert r["sentimen"] == ""
    assert "sumber" not in rows[0]


@pytest.mark.skipif(not GOLD_ADA, reason="gold_labels.csv tidak ada di mesin ini")
def test_dua_berkas_pelabel_berurutan_berbeda_tetapi_isinya_sama(tmp_path):
    p = pack_mod.build_pack(seed=42)
    a, b = tmp_path / "A.csv", tmp_path / "B.csv"
    pack_mod.annotator_csv(p, a, seed=43)
    pack_mod.annotator_csv(p, b, seed=44)
    ra = [r["clause_id"] for r in csv.DictReader(a.open(encoding="utf-8"))]
    rb = [r["clause_id"] for r in csv.DictReader(b.open(encoding="utf-8"))]
    assert ra != rb and sorted(ra) == sorted(rb)


# ---------------------------------------------------------------- susunan LLM + manusia


def _row_flag(cid, text, aspects, flag, sent="negatif"):
    r = _row(cid, text, aspects, sent)
    r["catatan_pelabel"] = flag
    return r


def test_pelabel_llm_dikenali_dari_bendera():
    llm = {"c1": _row_flag("c1", "x", ["pengiriman"], "yakin"),
           "c2": _row_flag("c2", "y", ["kemasan"], "RAGU: penyok barang atau dus")}
    manusia = {"c1": _row("c1", "x", ["pengiriman"]), "c2": _row("c2", "y", ["kemasan"])}
    assert eval_mod.is_llm_annotator(llm) is True
    assert eval_mod.is_llm_annotator(manusia) is False


def test_rujukan_pada_susunan_llm_adalah_manusia_bukan_kesepakatan():
    """Label LLM tidak boleh menjadi rujukan walau ia 'yakin' - manusialah rujukannya."""
    a = {"c1": _row_flag("c1", "x", ["kemasan"], "yakin")}
    b = {"c1": _row("c1", "x", ["kualitas_produk"])}
    ag = eval_mod.agreement(a, b)
    ref, pending = eval_mod.reference_labels(a, b, ag["ids"], None, human_only_b=True)
    assert not pending
    assert ref["c1"][eval_mod.ALL_ASPECTS.index("kualitas_produk")] == 1
    assert ref["c1"][eval_mod.ALL_ASPECTS.index("kemasan")] == 0


def test_audit_kontrol_menghitung_kecocokan_yakin_dan_ragu_terpisah():
    a = {"k1": _row_flag("k1", "t", ["pengiriman"], "yakin"),
         "k2": _row_flag("k2", "t", ["kemasan"], "yakin"),
         "r1": _row_flag("r1", "t", ["kualitas_produk"], "RAGU: x")}
    b = {"k1": _row("k1", "t", ["pengiriman"]),
         "k2": _row("k2", "t", ["kualitas_produk"]),
         "r1": _row("r1", "t", ["kualitas_produk"])}
    ag = eval_mod.agreement(a, b)
    au = eval_mod.control_audit(a, b, ag["ids"])
    assert au["n_control_yakin"] == 2 and au["exact_agreement_yakin"] == 1
    assert au["rate_yakin"] == 0.5
    assert au["n_ragu"] == 1 and au["exact_agreement_ragu"] == 1
    lo, hi = au["ci95_yakin"]
    assert lo < 0.5 < hi


def test_selang_wilson_menyempit_dengan_n():
    lo1, hi1 = eval_mod._wilson(5, 10)
    lo2, hi2 = eval_mod._wilson(50, 100)
    assert (hi2 - lo2) < (hi1 - lo1)
    assert eval_mod._wilson(0, 0) == (0.0, 0.0)


@pytest.mark.skipif(not (REPO / "data" / "annotation" / "aspect_human_A_done.csv").exists(),
                    reason="berkas label LLM tidak ada")
def test_berkas_llm_lengkap_dan_subset_manusia_tanpa_label():
    """Berkas A (LLM) harus melabeli semuanya dengan bendera; subset B untuk manusia harus kosong
    labelnya dan memuat SEMUA baris RAGU - manusia wajib memutuskan setiap keraguan LLM."""
    a = eval_mod._read(REPO / "data" / "annotation" / "aspect_human_A_done.csv")
    assert len(a) == 200 and eval_mod.is_llm_annotator(a)
    ragu = {i for i, r in a.items() if r["catatan_pelabel"].startswith("RAGU")}
    sub_path = REPO / "data" / "annotation" / "aspect_human_B_sisa.csv"
    if sub_path.exists():
        sub = eval_mod._read(sub_path)
        assert ragu <= set(sub)
        for r in sub.values():
            assert r["sentimen"] == "" and all(r[c] == "" for c in eval_mod.ASPECT_COLS)
            assert r["catatan_pelabel"] == ""  # bendera LLM tidak bocor ke manusia
