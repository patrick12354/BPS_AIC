"""Kepala aspek v2 (L0') - artefak, pemasangannya di adapter, dan tombol kembalinya.

Yang dijaga: artefaknya konsisten dengan taksonomi; adapter memasang bobot DAN ambangnya
bersama (bukan salah satunya); versi model menyebutnya; dan ASPECT_HEAD=v1 benar-benar
mengembalikan kepala lama - supaya perbandingan dan rollback selalu mungkin.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ml" / "text"))

ARTIFACT = REPO / "ml" / "text" / "artifacts" / "aspect_head_v2.pt"
CHECKPOINT = REPO / "models" / "indobert-nlp01" / "model.pt"


@pytest.mark.skipif(not ARTIFACT.exists(), reason="artefak kepala v2 tidak ada")
def test_artefak_konsisten_dengan_taksonomi():
    import torch
    from lexicon import ALL_ASPECTS

    v2 = torch.load(ARTIFACT, map_location="cpu", weights_only=False)
    assert list(v2["aspects"]) == list(ALL_ASPECTS)
    assert tuple(v2["aspect_head.weight"].shape) == (len(ALL_ASPECTS), 768)
    assert tuple(v2["aspect_head.bias"].shape) == (len(ALL_ASPECTS),)
    assert 0.0 < float(v2["aspect_threshold"]) < 1.0
    assert "provenance" in v2 and "120" in v2["provenance"]


@pytest.mark.skipif(not (ARTIFACT.exists() and CHECKPOINT.exists()), reason="butuh checkpoint + artefak")
def test_adapter_memasang_bobot_dan_ambang_v2_bersama(monkeypatch):
    import torch
    from app.adapters.text_model import TextModelAdapter

    monkeypatch.delenv("ASPECT_HEAD", raising=False)
    ad = TextModelAdapter()
    v2 = torch.load(ARTIFACT, map_location="cpu", weights_only=False)
    assert ad.mode == "full"
    assert ad.aspect_head_version != "v1"
    assert ad.threshold == pytest.approx(float(v2["aspect_threshold"]))
    assert "asp-v2" in ad.model_version
    w = ad.model.aspect_head.weight.detach().cpu()
    assert torch.allclose(w, v2["aspect_head.weight"], atol=1e-6)


@pytest.mark.skipif(not (ARTIFACT.exists() and CHECKPOINT.exists()), reason="butuh checkpoint + artefak")
def test_aspect_head_v1_mengembalikan_kepala_lama(monkeypatch):
    import torch
    from app.adapters.text_model import TextModelAdapter

    monkeypatch.setenv("ASPECT_HEAD", "v1")
    ad = TextModelAdapter()
    bundle = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    assert ad.aspect_head_version == "v1"
    assert "asp-v2" not in ad.model_version
    assert ad.threshold == pytest.approx(float(bundle.get("aspect_threshold", 0.5)))
    w = ad.model.aspect_head.weight.detach().cpu()
    assert torch.allclose(w, bundle["state_dict"]["aspect_head.weight"], atol=1e-6)


def test_dokumentasi_api_terpasang_di_bawah_prefiks_api():
    """Di belakang nginx hanya /api/ yang diteruskan - dokumentasi di /docs tidak pernah sampai."""
    from app.main import app

    assert app.docs_url == "/api/docs"
    assert app.openapi_url == "/api/openapi.json"
