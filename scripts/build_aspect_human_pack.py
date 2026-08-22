"""Susun paket validasi aspek oleh MANUSIA INDEPENDEN - penutup celah terakhir klaim model.

Kenapa ini ada. Gold set 500 klausa (ADR-017) berasal dari pra-anotasi LLM yang ditinjau tim:
jauh lebih bermakna daripada label silver, tetapi seluruh labelnya lahir dari satu sumber
pembacaan. Pada gold itu IndoBERT (0,766) tampak setara leksikon (0,770) untuk aspek, sementara
pada data sentimen berlabel manusia independen ia unggul jelas. Selisih arah ini bisa berarti
dua hal yang sangat berbeda - modelnya memang tidak unggul pada aspek, ATAU gold-nya yang
membawa bias sumber - dan hanya anotasi manusia dari nol yang dapat membedakannya.

Paket ini membuat anotasi itu semurah mungkin tanpa mengorbankan kesahihannya:

* 200 klausa: 150 diambil BERTINGKAT dari gold (setiap aspek terwakili, termasuk yang langka)
  + 50 klausa SEGAR dari ulasan Shopee asli yang tidak pernah masuk gold maupun data latih.
* Dua berkas identik (A dan B) dengan urutan acak berbeda, untuk dua pelabel yang bekerja
  TERPISAH - kesepakatan antar-pelabel (Cohen's kappa) adalah bukti bahwa labelnya bukan selera
  satu orang.
* Label gold LAMA sengaja TIDAK disertakan di berkas pelabel. Melihat tebakan sebelumnya
  menjangkarkan jawaban, dan yang ingin diukur justru independensinya.
* Alat pelabelan HTML lokal (tanpa server, tanpa jaringan) dengan kotak centang per aspek,
  supaya pelabel tidak mengetik 1/0 di 11 kolom spreadsheet - itu sumber salah-geser yang
  paling sering.

Setelah kedua pelabel selesai:
    python ml/text/evaluate_aspect_human.py

Jalankan:
    python scripts/build_aspect_human_pack.py
    -> data/annotation/aspect_human_A.csv, aspect_human_B.csv, label_aspek.html,
       PANDUAN_ANOTASI_ASPEK.md
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "ml" / "text"))

from lexicon import ALL_ASPECTS  # noqa: E402
from preprocess import normalize, split_clauses  # noqa: E402

ANNOT = REPO / "data" / "annotation"
GOLD = ANNOT / "gold_labels.csv"
FRESH_SRC = REPO / "data" / "samples" / "demo_shopee_asli.csv"

N_FROM_GOLD = 150
N_FRESH = 50
SEED = 42

# Aspek yang sedikit contohnya di gold diberi jatah minimum supaya kappa per aspek bisa dihitung
# sama sekali - tanpa ini, sampel acak 150 dari 500 hampir pasti hanya memuat 2-3 klausa
# "kemudahan_penggunaan", dan F1 pada 2 contoh bukan angka, itu lemparan koin.
MIN_PER_ASPECT = 8

ASPECT_LABELS = {
    "kualitas_produk": "Kualitas produk",
    "kesesuaian_deskripsi": "Kesesuaian dengan deskripsi/foto",
    "harga_value": "Harga / kesepadanan nilai",
    "ukuran_varian": "Ukuran / varian (porsi untuk F&B)",
    "rasa_kualitas_makanan": "Rasa / kualitas makanan",
    "kemasan": "Kemasan / packing",
    "pengiriman": "Pengiriman / kurir / kecepatan kirim",
    "pelayanan_penjual": "Pelayanan penjual / respons chat",
    "kelengkapan": "Kelengkapan isi paket",
    "keaslian": "Keaslian / orisinalitas",
    "kemudahan_penggunaan": "Kemudahan penggunaan / pemasangan",
}


def _clause_id(text: str, prefix: str) -> str:
    return f"{prefix}_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:10]}"


def sample_from_gold(rows: list[dict], rng: random.Random, n: int) -> list[dict]:
    """Sampel bertingkat: jatah minimum per aspek dulu, sisanya acak - tanpa duplikat."""
    chosen: dict[str, dict] = {}
    for aspect in ALL_ASPECTS:
        pool = [r for r in rows if r.get(f"asp_{aspect}") == "1" and r["clause_id"] not in chosen]
        rng.shuffle(pool)
        for r in pool[:MIN_PER_ASPECT]:
            chosen[r["clause_id"]] = r
    rest = [r for r in rows if r["clause_id"] not in chosen]
    rng.shuffle(rest)
    for r in rest:
        if len(chosen) >= n:
            break
        chosen[r["clause_id"]] = r
    return list(chosen.values())[:n]


def fresh_clauses(rng: random.Random, n: int, exclude_texts: set[str]) -> list[dict]:
    """Klausa dari ulasan Shopee asli yang belum pernah dilihat gold maupun data latih."""
    if not FRESH_SRC.exists():
        return []
    out: list[dict] = []
    seen: set[str] = set()
    with FRESH_SRC.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for clause in split_clauses(normalize(row.get("ulasan") or "")):
                c = clause.strip()
                # Klausa terlalu pendek ("ok", "mantap") tidak memberi informasi aspek apa pun
                # dan hanya menambah baris "tanpa aspek" yang sudah cukup terwakili.
                if len(c.split()) < 3 or c in seen or c in exclude_texts:
                    continue
                seen.add(c)
                out.append({"clause_id": _clause_id(c, "fresh"), "clause_text": c,
                            "category_produk": "fashion", "sumber": "shopee_asli"})
    rng.shuffle(out)
    return out[:n]


def build_pack(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    with GOLD.open(encoding="utf-8") as fh:
        gold_rows = list(csv.DictReader(fh))
    picked = sample_from_gold(gold_rows, rng, N_FROM_GOLD)
    base = [
        {"clause_id": r["clause_id"], "clause_text": r["clause_text"],
         "category_produk": r.get("category_produk", ""), "sumber": "gold"}
        for r in picked
    ]
    base += fresh_clauses(rng, N_FRESH, {r["clause_text"] for r in gold_rows})
    return base


def annotator_csv(pack: list[dict], path: Path, seed: int) -> None:
    """Satu berkas pelabel: urutan diacak dengan seed berbeda, kolom label kosong."""
    rows = list(pack)
    random.Random(seed).shuffle(rows)
    fields = ["clause_id", "clause_text", "category_produk"] + [f"asp_{a}" for a in ALL_ASPECTS] + [
        "sentimen", "catatan_pelabel",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({"clause_id": r["clause_id"], "clause_text": r["clause_text"],
                        "category_produk": r["category_produk"]})


def guide_md() -> str:
    bullets = "\n".join(f"- `asp_{k}` - {v}" for k, v in ASPECT_LABELS.items())
    return f"""# Panduan Anotasi Aspek - Validasi Manusia Independen

Berkas: `aspect_human_A.csv` (pelabel A) dan `aspect_human_B.csv` (pelabel B). Isinya SAMA,
urutannya berbeda. **Kerjakan terpisah, jangan berdiskusi sampai keduanya selesai** - yang
diukur adalah seberapa sepakat dua orang yang tidak saling memengaruhi.

Paling mudah: buka `label_aspek.html` di browser (berjalan lokal, tidak mengirim apa pun),
pilih berkas Anda, centang aspek yang dibicarakan tiap klausa, lalu tekan **Unduh hasil**.
Simpan sebagai `aspect_human_A_done.csv` / `aspect_human_B_done.csv` di folder ini.

## Aturan

1. **Labeli apa yang TERTULIS di klausa itu**, bukan yang Anda duga dari konteks ulasan
   utuh. Klausa dipotong sengaja.
2. Satu klausa boleh punya **beberapa aspek**, boleh juga **tidak punya aspek sama sekali**
   ("makasih kak", "sudah diterima") - itu label yang sah, bukan kesalahan.
3. Aspek adalah TOPIK yang dibicarakan, terlepas dari positif/negatifnya. "pengiriman cepat"
   dan "pengiriman lama" sama-sama `asp_pengiriman`.
4. Isi `sentimen` (positif / negatif / netral) - ini dipakai sebagai pembanding tambahan.
5. Ragu? Tetap putuskan, lalu tulis di `catatan_pelabel`. Baris yang Anda dan pelabel lain
   tidak sepakat akan diputuskan orang ketiga - jadi keraguan Anda tidak hilang.

## Aspek

{bullets}

Definisi resminya di `configs/taxonomy.yaml` (FROZEN). Batas yang paling sering rancu:

| Klausa | Aspek | Bukan |
| --- | --- | --- |
| "dusnya penyok, untung isinya aman" | kemasan | kualitas_produk - barangnya sendiri aman |
| "jahitannya lepas" | kualitas_produk | kemasan |
| "warnanya beda dari foto" | kesesuaian_deskripsi | kualitas_produk - barangnya tidak rusak, hanya tidak sesuai |
| "pesan L datang M" | ukuran_varian | kesesuaian_deskripsi - ini soal varian yang dikirim |
| "paketnya telat seminggu" | pengiriman | pelayanan_penjual |
| "seller slow respon" | pelayanan_penjual | pengiriman |
| "kabelnya tidak ada" | kelengkapan | kualitas_produk |
| "harganya murah tapi kualitas segini ya wajar" | harga_value + kualitas_produk | - |

## Setelah selesai

```
python ml/text/evaluate_aspect_human.py
```

Skrip itu menghitung kesepakatan antar-pelabel (Cohen's kappa per aspek), membuat daftar baris
yang perlu diputuskan orang ketiga, lalu mengukur leksikon vs TF-IDF vs IndoBERT vs label
gold-LLM pada label manusia - dan menulis hasilnya apa adanya ke `ml/evaluation/`.

## Susunan alternatif: LLM + manusia

Bila pelabel A diisi LLM (`scripts/_llm_aspect_labels_A.py`, dengan bendera RAGU/yakin per
baris), pelabel B manusia cukup melabeli `aspect_human_B_sisa.csv` - seluruh baris RAGU + sampel
kontrol acak dari baris yakin, tanpa diberi tahu mana yang mana. Hasilnya disimpan otomatis
sebagai `aspect_human_B_sisa_done.csv`; skrip evaluasi yang sama mengenali susunan ini, memakai
label **manusia** sebagai satu-satunya rujukan, dan melaporkan label LLM hanya sebagai satu
pembanding beserta taksiran seberapa sering "yakin"-nya cocok dengan manusia. Susunan ini lebih
lemah daripada dua manusia independen, dan dilaporkan demikian.
"""


def tool_html(aspects: dict[str, str]) -> str:
    """Alat pelabelan lokal. Satu berkas, tanpa dependensi, tanpa jaringan."""
    asp_json = json.dumps([{"key": k, "label": v} for k, v in aspects.items()], ensure_ascii=False)
    return """<!doctype html>
<html lang="id"><head><meta charset="utf-8"><title>Label Aspek - Ulasin</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font:15px/1.5 system-ui,sans-serif;margin:0;background:#F7F7F5;color:#1A1D26}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #DEDFDA;padding:10px 18px;display:flex;gap:14px;align-items:center;flex-wrap:wrap;z-index:2}
header b{font-size:16px} header .n{margin-left:auto;color:#5A6070;font-variant-numeric:tabular-nums}
button{font:inherit;padding:7px 12px;border-radius:8px;border:1px solid #2B3A8F;background:#2B3A8F;color:#fff;cursor:pointer}
button.sec{background:#fff;color:#2B3A8F}
main{max-width:900px;margin:0 auto;padding:18px}
.item{background:#fff;border:1px solid #DEDFDA;border-radius:12px;padding:14px 16px;margin:0 0 12px}
.item .t{font-size:17px;margin:0 0 10px}.item .t small{color:#5A6070;font-size:12px;margin-left:8px}
.asp{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:4px 14px;margin:0 0 8px}
.asp label{display:flex;gap:7px;align-items:center;font-size:14px;cursor:pointer}
.sent label{margin-right:14px;cursor:pointer} .cat{width:100%;margin-top:6px;padding:5px 8px;border:1px solid #DEDFDA;border-radius:6px;font:inherit}
.done{border-color:#1F6B4A;background:#F4FAF6}
.hint{color:#5A6070;font-size:13px}
</style></head><body>
<header><b>Label Aspek</b>
<input type="file" id="file" accept=".csv">
<button class="sec" id="reset">Kosongkan progres</button>
<button id="dl">Unduh hasil</button>
<span class="n" id="n"></span></header>
<main>
<p class="hint">Pilih berkas <code>aspect_human_A.csv</code> atau <code>aspect_human_B.csv</code>. Progres tersimpan otomatis di browser ini. Centang SEMUA aspek yang dibicarakan klausa; boleh kosong. Sentimen wajib. Tekan <b>Unduh hasil</b> kapan saja - hasilnya lengkap untuk yang sudah diisi.</p>
<div id="list"></div>
</main>
<script>
const ASPECTS=""" + asp_json + """;
let rows=[],cols=[],key="";
const store=()=>localStorage.setItem(key,JSON.stringify(rows));
function parseCSV(t){const out=[];let row=[],cell="",q=false;for(let i=0;i<t.length;i++){const c=t[i];if(q){if(c=='"'&&t[i+1]=='"'){cell+='"';i++}else if(c=='"'){q=false}else cell+=c}else if(c=='"')q=true;else if(c==','){row.push(cell);cell=""}else if(c=='\\n'||c=='\\r'){if(c=='\\r'&&t[i+1]=='\\n')i++;row.push(cell);out.push(row);row=[];cell=""}else cell+=c}if(cell||row.length){row.push(cell);out.push(row)}return out.filter(r=>r.some(x=>x!==""))}
function esc(v){v=String(v??"");return /[",\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v}
document.getElementById("file").onchange=e=>{const f=e.target.files[0];if(!f)return;key="ulasin-aspek:"+f.name;const r=new FileReader();r.onload=()=>{const p=parseCSV(r.result);cols=p[0];const saved=localStorage.getItem(key);rows=saved?JSON.parse(saved):p.slice(1).map(v=>Object.fromEntries(cols.map((c,i)=>[c,v[i]??""])));render()};r.readAsText(f,"utf-8")};
document.getElementById("reset").onclick=()=>{if(key&&confirm("Hapus progres berkas ini?")){localStorage.removeItem(key);location.reload()}};
document.getElementById("dl").onclick=()=>{if(!rows.length)return;const lines=[cols.map(esc).join(",")].concat(rows.map(r=>cols.map(c=>esc(r[c])).join(",")));const blob=new Blob(["\\ufeff"+lines.join("\\n")],{type:"text/csv;charset=utf-8"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=key.replace("ulasin-aspek:","").replace(".csv","_done.csv");a.click()};
function render(){const L=document.getElementById("list");L.innerHTML="";rows.forEach((r,i)=>{const d=document.createElement("div");d.className="item"+(r.sentimen?" done":"");d.innerHTML=`<p class="t">${i+1}. ${r.clause_text}<small>${r.category_produk||""}</small></p><div class="asp">${ASPECTS.map(a=>`<label><input type="checkbox" data-i="${i}" data-k="asp_${a.key}" ${r["asp_"+a.key]=="1"?"checked":""}> ${a.label}</label>`).join("")}</div><div class="sent">${["positif","negatif","netral"].map(s=>`<label><input type="radio" name="s${i}" data-i="${i}" data-s="${s}" ${r.sentimen==s?"checked":""}> ${s}</label>`).join("")}</div><input class="cat" placeholder="catatan (opsional)" data-i="${i}" value="${(r.catatan_pelabel||"").replace(/"/g,"&quot;")}">`;L.appendChild(d)});count()}
document.addEventListener("change",e=>{const t=e.target;const i=+t.dataset.i;if(Number.isNaN(i))return;if(t.dataset.k){rows[i][t.dataset.k]=t.checked?"1":""}else if(t.dataset.s){rows[i].sentimen=t.dataset.s;t.closest(".item").classList.add("done")}else if(t.classList.contains("cat")){rows[i].catatan_pelabel=t.value}store();count()});
function count(){const n=rows.filter(r=>r.sentimen).length;document.getElementById("n").textContent=rows.length?`${n} / ${rows.length} selesai`:""}
</script></body></html>
"""


def main() -> int:
    if not GOLD.exists():
        print(f"Gold set tidak ditemukan: {GOLD}", file=sys.stderr)
        return 1
    pack = build_pack()
    gold_n = sum(1 for r in pack if r["sumber"] == "gold")
    fresh_n = len(pack) - gold_n
    ANNOT.mkdir(parents=True, exist_ok=True)
    annotator_csv(pack, ANNOT / "aspect_human_A.csv", seed=SEED + 1)
    annotator_csv(pack, ANNOT / "aspect_human_B.csv", seed=SEED + 2)
    (ANNOT / "PANDUAN_ANOTASI_ASPEK.md").write_text(guide_md(), encoding="utf-8")
    (ANNOT / "label_aspek.html").write_text(tool_html(ASPECT_LABELS), encoding="utf-8")
    # Manifest kecil supaya evaluator tahu asal tiap klausa tanpa membocorkannya ke pelabel.
    (ANNOT / "aspect_human_manifest.json").write_text(
        json.dumps({"seed": SEED, "n_gold": gold_n, "n_fresh": fresh_n,
                    "sumber": {r["clause_id"]: r["sumber"] for r in pack}},
                   indent=1, ensure_ascii=False), encoding="utf-8",
    )
    print(f"{len(pack)} klausa: {gold_n} dari gold (bertingkat per aspek), {fresh_n} segar dari Shopee asli")
    print(f"Berkas pelabel : {ANNOT / 'aspect_human_A.csv'}  dan  aspect_human_B.csv")
    print(f"Alat pelabelan : {ANNOT / 'label_aspek.html'}  (buka di browser)")
    print(f"Panduan        : {ANNOT / 'PANDUAN_ANOTASI_ASPEK.md'}")
    print("Setelah selesai: python ml/text/evaluate_aspect_human.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
