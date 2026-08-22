# Model Card

> **Angka yang berlaku ada di §4** (iterasi kedua, setelah labeling function diperbaiki).
> §3 dipertahankan sebagai jejak proses: ia memperlihatkan bagaimana kesimpulan berubah ketika
> metrik silver yang sirkular akhirnya diuji terhadap label independen.
>
> **Aturan pengisian:** setiap angka di dokumen ini WAJIB berasal dari script/notebook evaluasi
> yang benar-benar dijalankan dan dapat ditelusuri balik (blueprint bagian 40). Tidak ada target,
> asumsi, atau angka dari literatur yang ditulis seolah hasil pengukuran tim.

## 1. Ringkasan model

| Komponen | Model | Status |
| --- | --- | --- |
| Text Intelligence (NLP-01) | IndoBERT-base, fine-tuned | **terlatih** - lihat §4 untuk angka yang berlaku |
| Text fallback | TF-IDF + Logistic Regression | **terlatih (baseline Fase 1)** |
| Visual Intelligence (VIS-01) | CLIP ViT-B/32 zero-shot, frozen | belum dievaluasi |
| Embedding (RET-01) | BGE-M3 | **terintegrasi** (fallback E5 → TF-IDF) |
| Orchestrator | SEA-LION quantized | belum diintegrasikan |

## 2. Data training
_Diisi dari hasil Fase 1 - lihat [DATASET_CARD.md](DATASET_CARD.md)._

## 3. Metrik evaluasi - model teks (bagian 33.1)

### 3.1 Baseline TF-IDF + Logistic Regression (Fase 1, sudah dijalankan)

Script: `ml/text/baseline.py` · seed 42 · hasil mentah: `ml/evaluation/baseline_results.json`
· log: `ml/evaluation/experiment_log.md` E02–E03.

**Cara membaca angka di bawah - penting.** Label aspek dan sebagian label sentimen dihasilkan
labeling function (ADR-015), bukan manusia. Karena itu:

| Kolom | Artinya |
| --- | --- |
| `silver_test` | Kecocokan model terhadap **labeling function**, BUKAN akurasi sebenarnya |
| `silver_test_unseen` | Sama, tetapi hanya pada klausa yang teksnya tak pernah muncul di train |
| `stress_challange` | Sentimen pada `challange.json` - label **independen** dari LF kita |

| Task | silver_test | silver_test_unseen | stress_challange |
| --- | --- | --- | --- |
| Sentimen (macro F1, 3 kelas) | 0,563 | 0,561 | **0,720** |
| Aspek (macro F1, multi-label 11 kelas) | 0,938 | 0,923 | tidak berlaku (tanpa label aspek) |

**Angka aspek 0,938 TIDAK boleh dibaca sebagai akurasi 94%.** Model TF-IDF hanya berhasil
memulihkan aturan leksikon yang membuat labelnya - ini persis risiko sirkularitas yang dicatat
pada ADR-015. Angka aspek yang bermakna baru ada setelah gold test set selesai dilabeli.

**Temuan sentimen:** kelas `netral` runtuh pada label silver (F1 0,113, support 256) namun jauh
lebih baik pada label independen (F1 0,609, support 1.223). Diagnosisnya: aturan silver untuk
netral terlalu jarang memicu, bukan modelnya yang gagal. Perlu diperbaiki sebelum Fase 2.

**Kelemahan baseline per fenomena bahasa** (stress test, macro F1): mixed_sentiment 0,113 ·
negation 0,163 · sarcasm 0,198 · ambiguous 0,237, berbanding typos_informal 0,736 ·
short_vague 0,778 · colloquial_slang 0,789. Baseline menangani variasi permukaan dengan baik
tetapi runtuh pada fenomena komposisional - inilah celah yang harus dibuktikan tertutup oleh
IndoBERT pada Fase 2 (bagian 34 baseline #3).

Catatan kejujuran: `challange.json` labelnya independen dari labeling function kita, tetapi
provenance datasetnya sendiri tidak terdokumentasi di sumbernya (ADR-016). Ia dipakai sebagai
**diagnostik**, bukan sebagai ground truth kompetisi.

### 3.2 Model fine-tuned IndoBERT (Fase 2, sudah dijalankan)

Script: `ml/text/finetune.py` · seed 42 · 3 epoch · batch 32 · lr 2e-5 · AdamW + OneCycleLR ·
112,8 menit pada GTX 1650 · checkpoint terpilih dari epoch 3 berdasar validation F1 (bukan
training loss) · ambang aspek 0,70 disetel dari validation set.

Arsitektur: satu encoder IndoBERT-base dengan dua head terpisah (aspek multi-label 11 kelas,
sentimen 3 kelas), mean pooling atas token non-padding.

#### Perbandingan terhadap baseline

| Metrik | Baseline TF-IDF | Fine-tuned IndoBERT | Selisih |
| --- | --- | --- | --- |
| Aspek - macro F1 (silver) | 0,938 | **0,985** | +0,047 |
| Aspek - macro F1 (silver unseen) | 0,923 | **0,981** | +0,058 |
| Sentimen - macro F1 (silver) | 0,563 | **0,628** | +0,065 |
| Sentimen - macro F1 (stress) | 0,720 | **0,730** | +0,010 |

**Gate Fase 2 terlampaui** (kriteria: macro F1 > baseline). Tetapi angka-angka di atas tidak
boleh dibaca begitu saja - tiga catatan berikut menentukan artinya.

#### Catatan 1 - angka aspek tetap sirkular

Kenaikan 0,938 → 0,985 **bukan bukti akurasi 98%**. Kedua model sedang memulihkan aturan
leksikon yang membuat labelnya; IndoBERT hanya memulihkannya lebih baik. Ini persis risiko yang
dicatat pada ADR-015. Angka aspek yang bermakna baru ada setelah gold test set selesai dilabeli.

#### Catatan 2 - kenaikan pada label independen sangat tipis

Pada stress set yang labelnya tidak berasal dari labeling function kita, kenaikannya hanya
**+0,010** - di dalam rentang derau. Rata-rata itu menyembunyikan pergerakan besar ke dua arah:

| Fenomena | Baseline | Fine-tuned | Selisih |
| --- | --- | --- | --- |
| negation | 0,163 | 0,559 | **+0,397** |
| mixed_sentiment | 0,113 | 0,311 | **+0,198** |
| emotional_exaggeration | 0,825 | 0,987 | +0,162 |
| typos_informal | 0,736 | 0,805 | +0,069 |
| short_vague | 0,778 | 0,825 | +0,048 |
| colloquial_slang | 0,789 | 0,827 | +0,038 |
| comparative | 0,656 | 0,686 | +0,031 |
| aspect_based | 0,552 | 0,571 | +0,019 |
| contextual | 0,608 | 0,589 | −0,019 |
| sarcasm | 0,198 | 0,179 | **−0,018** |
| ambiguous | 0,236 | 0,199 | **−0,037** |
| question_conditional | 0,459 | 0,358 | **−0,101** |

Pembacaan jujurnya: fine-tuning **benar-benar menutup celah negasi** - kenaikan +0,397 pada
fenomena yang secara khusus diargumentasikan tidak dapat ditangani pendekatan permukaan.
Sentimen campuran juga membaik besar meski levelnya masih rendah.

Sebaliknya, **sarkasme tidak membaik sama sekali** (0,198 → 0,179), dan `ambiguous` serta
`question_conditional` justru turun. Ini masuk akal dan tidak disembunyikan: data latih kami
tidak memuat label sarkasme, dan labeling function berbasis leksikon secara desain memberi label
yang SALAH pada kalimat sarkastik ("mantap banget nih ditipu" akan dinilai positif). Model
belajar dari label itu, jadi wajar ia mewarisi kelemahannya.

**Klaim yang boleh dibuat dari data ini:** fine-tuning memberi perbaikan besar dan terukur pada
negasi dan sentimen campuran. **Klaim yang TIDAK boleh dibuat:** bahwa sistem menangani sarkasme,
atau bahwa fine-tuning unggul menyeluruh pada bahasa informal.

#### Catatan 3 - bukti bahwa aturan label sentimen bermasalah

Metrik sentimen distratifikasi menurut asal labelnya:

| Asal label | Macro F1 | Artinya |
| --- | --- | --- |
| `clause_polarity` (klausa punya sinyal polaritas) | **0,993** | Model memulihkan aturan LF nyaris sempurna |
| `review_prior` (klausa tanpa sinyal, mewarisi sentimen ulasan) | **0,564** | Model tidak dapat mempelajarinya |

Jurang 0,43 pada model, distribusi, dan arsitektur yang sama - dibedakan **hanya oleh asal
label** - adalah bukti kuat bahwa aturan `review_prior` menghasilkan label yang tidak dapat
dipelajari, karena memang tidak berkorespondensi dengan isi klausanya. Klausa tanpa muatan
penilaian ("paket sudah diterima") diberi sentimen keseluruhan ulasan secara sewenang-wenang.

Ini menguatkan dugaan Fase 1 yang saat itu belum punya bukti sah. Kelas `netral` tetap rusak
(F1 0,136). **Revisi aturan sentimen ditunda sampai gold test set tersedia** - gold adalah
penengah yang sah, dan retraining sebelum itu berarti menebak dua kali.

#### Aspek per kelas (silver, terendah)

`kelengkapan` 0,926 (support 46) · `ukuran_varian` 0,980 · `kemudahan_penggunaan` 0,983 ·
`rasa_kualitas_makanan` 0,984. Aspek bersupport kecil tetap paling rapuh - konsisten dengan
keterbatasan cakupan kategori pada DATASET_CARD §5.

### 3.3 Evaluasi pada gold test set - **angka yang berlaku**

Script: `ml/text/evaluate_gold.py` · gold: `data/annotation/gold_labels.csv` (500 klausa) ·
hasil mentah: `ml/evaluation/gold_results.json`.

**Asal-usul label gold, dibaca apa adanya (ADR-017).** Label berasal dari pembacaan semantik LLM
atas 500 klausa, ditinjau dan disetujui tim; pada 302 baris yang leksikon dan LLM berbeda, tim
memutuskan kolom LLM yang benar. Ini **bukan** anotasi manusia independen dari nol - seluruh label
berasal dari satu sumber pembacaan yang sama. Angka di bawah mengukur kesesuaian model terhadap
pembacaan itu. Jauh lebih bermakna daripada metrik silver yang sirkular, tetapi tidak setara
dengan gold beranotasi manusia independen, dan harus disebut demikian di proposal.

| Pendekatan | Aspek macro F1 | Aspek micro F1 | Sentimen macro F1 |
| --- | --- | --- | --- |
| Leksikon rule-based | 0,734 | 0,716 | 0,599 |
| TF-IDF + Logistic Regression | **0,744** | **0,726** | **0,676** |
| IndoBERT fine-tuned | 0,733 | 0,716 | 0,668 |

#### Temuan utama: pada ASPEK, fine-tuning tidak menambah apa pun

Bandingkan F1 per kelas antara leksikon dan IndoBERT:

| Aspek | Leksikon | IndoBERT | n |
| --- | --- | --- | --- |
| kualitas_produk | 0,427 | 0,425 | 139 |
| kesesuaian_deskripsi | 0,773 | 0,773 | 76 |
| harga_value | 0,914 | 0,914 | 40 |
| ukuran_varian | 0,817 | 0,817 | 53 |
| kemasan | 0,907 | 0,907 | 44 |
| pengiriman | 0,718 | 0,718 | 72 |
| keaslian | 0,969 | 0,969 | 32 |
| kemudahan_penggunaan | 0,433 | 0,433 | 28 |

Tujuh dari sebelas kelas **identik sampai tiga desimal**. Model tidak memindahkan satu pun
keputusan; ia mereproduksi aturan leksikon. Inilah risiko sirkularitas ADR-015 yang terwujud
hampir sepenuhnya - dan hanya terlihat setelah diukur pada label yang dibuat proses berbeda.

Selisih 0,011 antara TF-IDF dan IndoBERT pada aspek berada dalam rentang derau untuk n=500 dan
**tidak boleh** dilaporkan sebagai "TF-IDF mengalahkan IndoBERT". Yang layak dilaporkan: ketiga
pendekatan setara pada aspek, dan tidak satu pun mengungguli aturan leksikon secara berarti.

#### Pada SENTIMEN, fine-tuning benar-benar bekerja - kecuali kelas netral

| Kelas | Leksikon | TF-IDF | IndoBERT | n |
| --- | --- | --- | --- | --- |
| negatif | 0,555 | 0,733 | **0,805** | 108 |
| positif | 0,810 | 0,891 | **0,917** | 322 |
| netral | 0,433 | 0,403 | **0,282** | 70 |

IndoBERT unggul telak pada dua kelas terbesar - negatif naik 0,25 poin di atas leksikon. Tetapi
kelas `netral` runtuh ke 0,282, dan itu menyeret macro F1-nya ke bawah TF-IDF. Rata-rata makro
menyembunyikan kenyataan bahwa model ini sebenarnya jauh lebih baik pada dua pertiga kasus.

Penyebabnya sudah diketahui dan tercatat sejak Fase 2: 44% label sentimen klausa mewarisi
sentimen tingkat ulasan (`review_prior`) alih-alih berasal dari isi klausanya. Model belajar
bahwa `netral` nyaris tidak pernah benar, lalu berhenti memprediksinya.

#### Gate Fase 2 - **DIREVISI**

Gate Fase 2 semula dinyatakan **GO** berdasarkan metrik silver. Diukur pada gold, verdict itu
tidak bertahan:

| Task | Verdict |
| --- | --- |
| Aspek | **TIDAK LULUS** - setara aturan leksikon, fine-tuning tidak memberi nilai tambah |
| Sentimen | **LULUS sebagian** - jauh lebih baik pada negatif dan positif, gagal pada netral |

Dua akar masalahnya sudah teridentifikasi tepat, dan keduanya ada di **label**, bukan di model:

1. Label aspek 100% keluaran leksikon, sehingga model tidak mungkin melampaui leksikon.
2. Aturan `review_prior` merusak kelas netral.

Dua kelas terlemah - `kualitas_produk` 0,43 dan `kemudahan_penggunaan` 0,43 - persis dua tempat
bug leksikon ditemukan saat adjudikasi (aturan cadangan "barang", dan kata "enak"/"dipakai" yang
memicu aspek keliru).

## 4. Metrik evaluasi - model visual (bagian 33.2)
_Accuracy pada kasus tidak abstain, macro F1, coverage, abstention rate, selective accuracy,
performa per kualitas foto. Belum diukur. **Tidak ada target minimum yang diklaim di muka.**_

## 5. Perbandingan baseline (bagian 34)
_Delapan baseline. Belum dijalankan._

## 6. Go/No-Go gate model visual (bagian 19.3, 26.2)
_Keputusan GO / CONDITIONAL GO / NO-GO diambil di akhir Fase 3 berbasis selective accuracy dan
coverage aktual. **Belum diambil.**_

## 7. Batas kemampuan dan bias yang diketahui
_Diisi setelah error analysis (bagian 26.1 langkah 15). Lihat juga [LIMITATIONS.md](LIMITATIONS.md)._

## 8. Reproducibility
_Seed, hyperparameter, versi model, dan perintah reproduksi dicatat di sini setelah training._


### 3.3b Validasi aspek oleh manusia independen - perangkatnya, dan statusnya

Temuan §3.3 punya dua tafsir yang sangat berbeda: (a) fine-tuning memang tidak menambah apa pun
pada aspek, atau (b) gold ADR-017 - yang seluruh labelnya lahir dari satu sumber pembacaan LLM -
membawa bias yang kebetulan dekat dengan leksikon. Petunjuk ke arah (b): pada sentimen, gold
yang sama memperlihatkan IndoBERT setara TF-IDF, padahal pada PRDECT-ID berlabel manusia
IndoBERT unggul jelas (§3.4). Selisih arah ini tidak bisa diselesaikan dengan lebih banyak
evaluasi pada gold yang sama; ia hanya bisa diselesaikan oleh anotasi manusia dari nol.

Perangkatnya ada di repositori dan dapat dijalankan siapa pun:

| Langkah | Perintah | Keluaran |
| --- | --- | --- |
| Susun paket | `python scripts/build_aspect_human_pack.py` | 200 klausa (150 bertingkat dari gold - tiap aspek minimal 8 contoh - + 50 segar dari ulasan Shopee asli yang tidak pernah masuk gold/latih) → dua berkas pelabel identik berurutan acak, alat pelabelan HTML lokal, panduan dengan contoh batas rancu |
| Labeli | dua orang, terpisah, `data/annotation/label_aspek.html` | `aspect_human_A_done.csv`, `aspect_human_B_done.csv` |
| Ukur | `python ml/text/evaluate_aspect_human.py` | Cohen's kappa per aspek (aspek dengan kappa < 0,40 ditandai **tidak dapat ditafsirkan**, bukan dilaporkan rata); baris tak sepakat → adjudikator ketiga; lalu leksikon / TF-IDF / IndoBERT / **label gold-LLM** dibandingkan pada rujukan manusia yang sama → `ml/evaluation/aspect_human_results.json` |

Baris "label gold-LLM sebagai pendekatan" adalah kuncinya: ia mengukur seberapa jauh gold lama
sendiri cocok dengan manusia, sehingga tafsir (a) dan (b) dapat dibedakan dengan angka.

**Susunan yang dijalankan, dan kenapa ia lebih lemah dari yang ideal.** Pelabel A adalah LLM
(`scripts/_llm_aspect_labels_A.py` - setiap label beserta bendera RAGU/yakin tercatat di kode,
bukan hanya di CSV, dan gold ADR-017 tidak dilihat saat melabeli: 60 RAGU, 140 yakin). Pelabel B
adalah manusia pada **subset 120 klausa: seluruh 60 RAGU + 60 kontrol acak dari yang yakin**,
tanpa melihat label maupun bendera LLM (`aspect_human_B_sisa.csv`). Evaluator mengenali susunan
ini dari bendera dan berperilaku berbeda: **rujukan = label manusia saja**, label LLM dilaporkan
sebagai pendekatan `llm_annotator_a`, dan sampel kontrol menaksir seberapa sering "yakin" LLM
cocok persis dengan manusia - dengan selang kepercayaan Wilson 95%, bukan satu angka.

Ini bukan anotasi dua manusia independen, dan tidak akan disebut demikian. Yang ia berikan:
(1) angka F1 aspek pada 120 klausa **berlabel manusia** untuk leksikon / TF-IDF / IndoBERT /
gold-LLM / LLM-anotator, dan (2) taksiran terukur tentang apakah 80 baris "yakin" yang tidak
diperiksa manusia layak dipercaya. Bila tim punya waktu, jalan yang lebih kuat tetap terbuka:
pelabel B melabeli 200 baris penuh, dan skrip yang sama menghitung ulang tanpa perubahan.

#### Hasil (22 Agustus 2026) - `ml/evaluation/aspect_human_results.json`

Pelabel manusia menyelesaikan 120 klausa. Kesepakatan LLM↔manusia: **kappa gabungan 0,683**
(substansial), kesepakatan baris persis 52,5%. Aspek `kelengkapan` (kappa 0,24) dan
`kemudahan_penggunaan` (kappa −0,03, n=4) **tidak ditafsirkan** - dua manusia pun belum tentu
sepakat di sana, apalagi model.

**Kontrol menjawab pertanyaan pertama dengan tegas:** dari 60 baris yang LLM "yakin", hanya
**32 (53%, CI95 41–65%)** yang cocok persis dengan manusia. Label LLM yang yakin pun tidak layak
menjadi rujukan - keputusan memakai label manusia saja sebagai rujukan terbukti perlu, bukan
formalitas.

**Angka utama - F1 aspek pada 120 klausa berlabel manusia:**

| Pendekatan | Macro F1 | Micro F1 | Pada 89 klausa asal gold (apple-to-apple) |
| --- | --- | --- | --- |
| Leksikon rule-based | 0,581 | 0,620 | 0,581 / 0,627 |
| TF-IDF + LR | 0,585 | 0,598 | 0,571 / 0,609 |
| **IndoBERT fine-tuned** | **0,579** | **0,614** | 0,581 / 0,627 |
| Label gold-LLM ADR-017 | - | - | **0,704 / 0,734** |
| LLM anotator (Claude, zero-shot, pelabel A) | 0,660 | 0,716 | 0,675 / 0,729 |

**Tafsirnya, apa adanya - dan ia menutup pertanyaan §3.3:**

1. **IndoBERT tidak unggul pada aspek, pada label manusia sekalipun** (0,579 vs 0,581 vs 0,585 -
   ketiganya di dalam noise satu sama lain). Tafsir (a) terkonfirmasi; ini bukan artefak gold.
2. **Gold ADR-017 bukan masalahnya.** Pada 89 klausa yang sama, label gold mencapai 0,704
   terhadap manusia - lebih dekat ke manusia daripada model mana pun. Gold itu cukup baik;
   modelnya yang tidak pernah punya sumber untuk melampaui leksikon (§4.3 sudah mengatakan ini,
   sekarang dengan bukti di luar gold).
3. **Pembacaan LLM zero-shot (0,660) mengalahkan model fine-tuned (0,579)** pada aspek. Ini fakta
   yang tidak nyaman untuk ADR-001 (local-first, tanpa API) dan karena itu harus ditulis: untuk
   aspek, pembacaan semantik saat ini lebih baik daripada kepala aspek yang dilatih dari label
   leksikon. Jalan keluar yang konsisten dengan ADR-001 bukan memanggil API saat inferensi,
   melainkan **melatih ulang kepala aspek pada label gold + manusia (distilasi)** - tercatat
   sebagai L0' di `docs/ROADMAP_FINAL.md`.
4. **Per aspek, ketiga model konvensional identik di sebagian besar baris** (harga 0,846,
   kemasan 0,889, keaslian 0,889, rasa 0,800) - model memang memulihkan leksikon. Titik
   terlemahnya nyata dan spesifik: **ukuran_varian 0,174** (n=9) dan **kualitas_produk 0,567**
   (n=38) - dua aspek yang paling sering muncul di ulasan fesyen, yaitu kategori demo utama.

| Aspek (kappa ≥ 0,40) | Leksikon | TF-IDF | IndoBERT | LLM anotator | n manusia |
| --- | --- | --- | --- | --- | --- |
| kualitas_produk | 0,590 | 0,456 | 0,567 | 0,747 | 38 |
| kesesuaian_deskripsi | 0,622 | 0,591 | 0,622 | 0,611 | 22 |
| harga_value | 0,846 | 0,846 | 0,846 | 0,923 | 12 |
| ukuran_varian | **0,174** | 0,320 | **0,174** | 0,552 | 9 |
| rasa_kualitas_makanan | 0,800 | 0,800 | 0,800 | 0,909 | 6 |
| kemasan | 0,889 | 0,889 | 0,889 | 0,875 | 8 |
| pengiriman | 0,667 | 0,640 | 0,667 | 0,750 | 11 |
| pelayanan_penjual | 0,667 | 0,750 | 0,667 | 0,750 | 9 |
| keaslian | 0,889 | 0,889 | 0,889 | 0,889 | 9 |

**Batas angka ini:** 120 klausa, satu pelabel manusia (bukan dua), dan n per aspek kecil (6–38)
- selang kepercayaan per aspek lebar. Yang cukup kuat untuk disimpulkan hanya dua hal: IndoBERT
tidak mengungguli leksikon pada aspek, dan gold ADR-017 bukan penyebabnya. Klaim aspek tetap
**TIDAK LULUS** (§4.3), kini dengan dasar yang lebih kuat daripada sebelumnya.

### 3.3c L0' - kepala aspek dilatih ulang dari label semantik (22 Agustus 2026)

Script: `ml/text/distill_aspect_head.py` · hasil: `ml/evaluation/aspect_head_v2_results.json` ·
artefak: `ml/text/artifacts/aspect_head_v2.pt` (36 KB, dilacak git).

**Protokol, ditulis sebelum angka dilihat.** TEST = 120 klausa berlabel manusia (§3.3b), tidak
pernah ikut latih maupun seleksi. TRAIN = gold ADR-017 dikurangi klausa yang ada di TEST = 411
klausa. Encoder IndoBERT beku (representasinya sudah terbukti pada sentimen); hanya kepala aspek
- satu lapisan linier - dilatih ulang. Hyperparameter dipilih 5-fold CV di TRAIN (kisi kecil,
dinyatakan di muka); TEST dilihat satu kali. Artefak ditulis hanya bila macro F1 di TEST melampaui
kepala lama.

| Kepala aspek, pada 120 klausa manusia | Macro F1 | Micro F1 |
| --- | --- | --- |
| Lama (dilatih dari label leksikon, ambang 0,70) | 0,579 | 0,614 |
| **v2 (dilatih dari gold ADR-017, ambang 0,30)** | **0,585** | **0,636** |
| Leksikon (rujukan) | 0,581 | 0,620 |

| Aspek | Lama → v2 | Aspek | Lama → v2 |
| --- | --- | --- | --- |
| kualitas_produk (n=38) | 0,567 → **0,675** | kemasan (n=8) | 0,889 → 0,800 |
| kesesuaian_deskripsi (n=22) | 0,622 → **0,756** | pengiriman (n=11) | 0,667 → 0,636 |
| harga_value (n=12) | 0,846 → 0,880 | pelayanan_penjual (n=9) | 0,667 → **0,500** |
| ukuran_varian (n=9) | 0,174 → 0,231 | rasa (n=6) | 0,800 → 0,667 |

**Bacaan jujurnya.** Secara makro, v2 **tidak berbeda bermakna** dari kepala lama maupun leksikon
(+0,006 pada 120 klausa - jauh di dalam noise). Yang berubah adalah *distribusinya*: dua aspek
yang paling sering dan paling lemah - kualitas_produk dan kesesuaian_deskripsi - naik 0,11 dan
0,13, dengan harga pelayanan_penjual dan kemasan turun. Karena itu micro F1 (yang menimbang
frekuensi) naik lebih terasa, +0,022. CV di TRAIN mencapai 0,764 - jauh di atas TEST - yang
menggarisbawahi temuan §3.3b: label gold-LLM konsisten di dalam dirinya, tetapi berbeda dari
pelabel manusia ini pada ~30% klausa.

**Keputusan:** v2 dipasang sebagai bawaan (`TextModelAdapter` menimpa bobot DAN ambang kepala
aspek bila artefaknya ada; `ASPECT_HEAD=v1` mengembalikan kepala lama). Alasannya bukan "lebih
baik" - alasannya adalah *lebih baik pada aspek yang paling sering muncul di kategori demo*,
dengan biaya nol pada arsitektur dan jalan kembali satu variabel lingkungan. Klaim gerbang aspek
**tidak berubah: TIDAK LULUS.** Yang akan mengubahnya adalah label latih yang lebih banyak dan
lebih manusiawi (L0' lanjutan di ROADMAP_FINAL), bukan kepala yang lebih pintar.

### 3.4 Evaluasi pada dataset berlabel MANUSIA yang sudah ada - tanpa anotasi tambahan

Script: `ml/text/evaluate_external.py` · hasil: `ml/evaluation/external_results.json`.

Menjawab pertanyaan "apakah cukup memakai data berlabel yang sudah ada?". Untuk **sentimen**:
bisa, dan inilah hasilnya. Untuk **aspek**: tidak - penelusuran delapan variasi kueri di
HuggingFace tidak menemukan dataset ABSA Bahasa Indonesia domain e-commerce berlisensi jelas
(`carant-ai/compiled-absa-indonesian` gated tanpa lisensi; CASA = ulasan mobil, HoASA = hotel,
skema aspeknya tidak sepadan). Validasi aspek tetap bergantung gold set kita.

#### A. In-domain, label manusia - PRDECT-ID split test (n=804)

Label `Sentiment` berlabel manusia dari makalah Data in Brief, **biner** (tanpa kelas netral),
dievaluasi hanya pada split test sehingga produknya terpisah dari data latih.

| Pendekatan | F1 negatif | F1 positif | macro (2 kelas) |
| --- | --- | --- | --- |
| Leksikon rule-based | 0,734 | 0,895 | 0,815 |
| TF-IDF + Logistic Regression | 0,917 | 0,919 | 0,918 |
| **IndoBERT fine-tuned** | **0,952** | **0,952** | **0,952** |

Prediksi `netral` oleh model tetap dihitung salah pada kedua kelas, jadi angka ini sudah memuat
hukuman itu.

**Ini benchmark paling relevan yang kita punya**: domain yang sama dengan produk (ulasan
e-commerce Indonesia), label dibuat manusia, dan sepenuhnya independen dari labeling function
maupun pra-anotasi kita. Di sini fine-tuning terbukti memberi nilai tambah nyata - IndoBERT
unggul 0,034 di atas TF-IDF dan 0,137 di atas leksikon.

#### B. Lintas bahasa - NusaX-senti (expert-generated, CC-BY-SA-4.0, n=400 per bahasa)

Domain media sosial, bukan e-commerce. Mengukur **generalisasi lintas domain**, bukan performa
in-domain - dua hal yang tidak boleh ditukar penyebutannya.

| Bahasa | Leksikon | TF-IDF | IndoBERT |
| --- | --- | --- | --- |
| Indonesia | **0,686** | 0,396 | 0,519 |
| Inggris | 0,298 | 0,336 | **0,411** |
| Jawa | **0,477** | 0,435 | 0,434 |
| Sunda | **0,355** | 0,296 | 0,351 |
| Minang | **0,434** | 0,355 | 0,382 |

Tiga bacaan yang harus disampaikan apa adanya:

1. **Di luar domain, leksikon justru menang.** Model terlatih menyerap gaya bahasa ulasan
   e-commerce dan generalisasinya lebih buruk pada teks media sosial. Ini bukan kegagalan
   produk - domain kita memang e-commerce - tetapi membatalkan klaim apa pun soal keunggulan
   umum model kami di luar domainnya.
2. **Kelas netral runtuh di semua model terlatih** (0,02–0,13 berbanding leksikon 0,43–0,61).
   Akar masalah yang sama dengan §3.2 dan §3.3: aturan `review_prior`.
3. **Bahasa daerah dan Inggris ditangani buruk** oleh semua pendekatan (0,30–0,48). Lihat
   konsekuensinya di LIMITATIONS.

#### C. Yang berubah dari kesimpulan sebelumnya

Pada gold set §3.3 (label dari pra-anotasi LLM), IndoBERT tampak setara TF-IDF. Pada PRDECT
berlabel manusia, IndoBERT unggul jelas. Selisih arah ini adalah **bukti bahwa gold set kami
memang membawa keterbatasan independensi yang dicatat di ADR-017** - label gold berasal dari
pembacaan yang sama dengan yang merancang leksikon, sehingga cenderung menguntungkan pendekatan
bergaya leksikon.

Karena itu **§3.4A adalah angka rujukan utama untuk sentimen**, dan gold set dipakai untuk aspek
(yang memang tidak punya alternatif berlabel manusia).


---

## 4. Setelah perbaikan labeling function (iterasi kedua)

Script sama, label diperbaiki (lihat DATASET_CARD §5). Model dilatih ulang 2 epoch.
Hasil: `ml/evaluation/gold_results.json`, `external_results.json`.

### 4.1 Perbaikan nyata pada data berlabel manusia

**NusaX-senti - expert-generated, 3 kelas, inilah skema label yang sama dengan produk kami:**

| Bahasa | IndoBERT sebelum | IndoBERT sesudah | Selisih |
| --- | --- | --- | --- |
| Indonesia | 0,519 | **0,730** | **+0,211** |
| Jawa | 0,434 | 0,517 | +0,083 |
| Inggris | 0,411 | 0,469 | +0,058 |
| Sunda | 0,351 | 0,388 | +0,037 |
| Minang | 0,382 | 0,468 | +0,086 |

**Kelas netral akhirnya berfungsi.** Pada NusaX Indonesia F1 netral naik dari **0,021 ke 0,645**.
Sebelumnya model praktis tidak pernah memprediksi netral sama sekali; sekarang ia memakainya
dengan benar. Ini menutup masalah yang sudah teridentifikasi sejak Fase 1.

Stress test (sarkasme/negasi/slang) naik 0,730 → **0,770**.

### 4.2 Ongkosnya: PRDECT biner turun - sebagian besar artefak skema label

| Pendekatan | macro-biner sebelum | sesudah |
| --- | --- | --- |
| Leksikon | 0,815 | 0,832 |
| TF-IDF | 0,918 | 0,854 |
| IndoBERT | **0,952** | **0,851** |

Penurunan ini perlu dibaca hati-hati. PRDECT-ID hanya punya dua label - pelabelnya dipaksa
memilih positif atau negatif, tidak ada netral. Model kami kini memprediksi netral pada 13,9%
ulasan, dan pada dataset berskema biner setiap prediksi netral otomatis dihitung salah.

Matriks kebingungan menunjukkan sumbernya:

| gold ↓ / prediksi → | negatif | netral | positif |
| --- | --- | --- | --- |
| negatif | 292 | **91** | 37 |
| positif | 8 | **21** | 355 |

**Pada 692 ulasan yang modelnya benar-benar memutuskan positif atau negatif, akurasinya 93,5%.**
Jadi penurunan itu bukan model menjadi lebih keliru, melainkan model menjadi lebih berhati-hati
pada skema label yang tidak menyediakan pilihan itu.

**Tetapi ada satu hal yang harus diakui sebagai kelemahan nyata, bukan artefak:** dari 112
prediksi netral, **91 di antaranya sebenarnya keluhan** - berbanding hanya 21 pada ulasan
positif. Model kurang berani menyebut sesuatu negatif. Untuk produk ini itu penting, karena
deteksi keluhanlah yang menggerakkan Action Card. Perbaikannya (menurunkan ambang kelas negatif
atau menaikkan bobot kelasnya) belum dikerjakan dan tercatat sebagai pekerjaan Fase 8.

### 4.3 Gate Fase 2 - verdict akhir

| Task | Verdict | Dasar |
| --- | --- | --- |
| **Sentimen** | **LULUS** | Pada data berlabel expert 3 kelas, IndoBERT 0,730 mengungguli leksikon 0,700 dan TF-IDF 0,627; kelas netral pulih dari 0,021 ke 0,645 |
| **Aspek** | **TIDAK LULUS** | Pada gold, IndoBERT 0,766 setara leksikon 0,770; **dikonfirmasi pada 120 klausa berlabel manusia** (§3.3b): 0,579 vs 0,581 vs TF-IDF 0,585 - dan gold bukan penyebabnya (gold 0,704 terhadap manusia) |

Aspek tidak lulus bukan karena kurang usaha, melainkan karena **secara struktural tidak bisa**:
label aspeknya 100% keluaran leksikon, sehingga model tidak punya sumber informasi untuk
melampaui leksikon. Satu-satunya jalan keluar adalah label aspek berlabel manusia dalam volume
latih - dan dataset semacam itu tidak tersedia untuk Bahasa Indonesia domain e-commerce
(sudah ditelusuri, DATASET_CARD §6).

**Konsekuensi jujur untuk proposal:** klaim kustomisasi model teks bertumpu pada **sentimen**,
di mana fine-tuning terbukti memberi nilai tambah pada label independen. Untuk **aspek**, yang
layak diklaim adalah pipeline weak-supervision-nya, bukan keunggulan model atas aturan leksikon.


---

## VIS-01 - hasil gerbang Fase 3

Dijalankan 11 Agustus 2026. **Keputusan: NO-GO.** Bukti lengkap:
[`ml/evaluation/visual_gate.json`](../ml/evaluation/visual_gate.json).

| Aspek | Keterangan |
| --- | --- |
| Model | `openai/clip-vit-base-patch32`, beku, zero-shot dengan prompt ensemble |
| Data uji | 97 foto ulasan Shopee berlabel manusia, 2 produk fesyen, 1 penjual |
| Protokol | Ambang dikalibrasi pada split terpisah; split per ULASAN, bukan per foto |

### Angka

| Ukuran | Nilai |
| --- | --- |
| Selective accuracy (split uji) | 0,786 pada coverage 0,275 |
| Akurasi argmax tanpa abstention | **0,45** |
| Akurasi "selalu tebak `normal`" | **0,61** |
| Foto normal yang salah ditandai bermasalah | 0,61 |
| Abstain pada foto yang manusia tandai sulit | 2 / 2 |

**Selective accuracy 0,786 tidak boleh dikutip.** Dari 14 foto yang dijawab, sebelas kelas
`normal` - angka itu dihasilkan dengan menjawab pada kelas mayoritas dan abstain pada hampir
seluruh foto bermasalah. Pemeriksaan yang menentukan adalah baris berikutnya: akurasi argmax
0,45 **berada di bawah** pembanding sepele 0,61.

Prompt campuran Indonesia+Inggris (0,45) mengungguli prompt Inggris saja (0,37) - berlawanan
dengan dugaan bahwa CLIP berbahasa Inggris lebih cocok dengan prompt Inggris. Keduanya tetap
di bawah pembanding sepele.

### Konsekuensi

Hasil visual **tidak ditampilkan di antarmuka, tidak disebut di proposal, tidak muncul di
video promosi**. Status ini dikunci di
[`configs/visual_classes.yaml`](../configs/visual_classes.yaml). Kode VIS-01 tetap berada di
repositori sebagai komponen yang gracefully degrade dan sebagai bukti bahwa gerbangnya
dijalankan apa adanya.

Batas kesimpulan: 97 foto dari dua produk fesyen satu penjual. NO-GO berlaku untuk kondisi
itu, bukan pernyataan bahwa CLIP tidak dapat dipakai. Encoder lain, prompt lain, atau kategori
produk lain dapat memberi hasil berbeda - dan mengujinya adalah pekerjaan Tier 2.

---

## 9. Kalibrasi keyakinan - temperature scaling (L1)

**Status: pipeline siap, angka menunggu checkpoint.** Kode kalibrasi lengkap dan diuji; yang
belum ada adalah hasil menjalankannya, karena itu menuntut `models/indobert-nlp01/model.pt`
beserta `data/processed/clauses_val.csv` yang tidak ikut di-commit.

```bash
python ml/text/calibrate.py     # menulis suhu ke bundle + ml/evaluation/calibration.json
```

### Masalah yang diselesaikan

`AspectPrediction.confidence` selama ini **konstanta**: 0,80 saat checkpoint aktif, 0,60 saat
leksikon. Ia dipasang sebagai penanda sementara pada Fase 5 dan tidak pernah diganti. Angka itu
sempat tampil di laporan sebagai "Keyakinan model: 80% rata-rata", bersebelahan dengan
persentase yang benar-benar dihitung - di tempat seperti itu ia terbaca sebagai hasil
pengukuran, dan satu angka tetap yang menyamar sebagai pengukuran merusak kepercayaan pada
seluruh angka di sekitarnya.

Softmax mentah bukan penggantinya. Temuan Fase 8 mengukur kenapa: dari 128 ulasan negatif yang
terlewat pada PRDECT-ID, **113 (88,3%) diprediksi dengan P(negatif) di bawah 0,10**, median
0,0006. Model bukan ragu lalu memilih salah - **ia yakin dan salah**. Angka seyakin itu tidak
boleh sampai ke layar tanpa diperiksa lebih dulu seberapa sering ia benar.

### Metode dan alasannya

Temperature scaling (Guo et al., 2017): satu parameter `T` per head, di-fit pada split validasi
dengan NLL, ECE dilaporkan sebelum dan sesudah.

Dipilih di atas isotonic regression dan Platt scaling per kelas karena satu sifat yang
menentukan: **membagi logit dengan skalar positif tidak menggeser argmax**. Akurasi, macro-F1,
dan urutan Action Card karenanya tetap sama persis - yang berubah hanya kejujuran angka
keyakinannya. Metode yang lebih lentur mengubah keputusan, dan itu menuntut evaluasi ulang
penuh untuk sesuatu yang bukan tujuannya.

NLL dipakai sebagai fungsi objektif meski ECE yang dilaporkan: ECE adalah fungsi tangga -
berubah hanya ketika sebuah contoh berpindah bin - sehingga permukaannya datar di hampir semua
tempat. NLL mulus dan proper, mengarah ke tempat yang sama tanpa dataran itu.

Pencariannya bagi-tiga (ternary search) atas rentang [0,05; 10], bukan gradient descent. Fungsi
satu dimensi yang unimodal terhadap T tidak membutuhkan laju belajar maupun titik awal, dan
hasilnya **deterministik** - syarat yang berlaku untuk setiap angka di produk ini.

### Apa yang berubah pada produk

Ambang aspek ikut digeser bersama suhunya (`aspect_threshold_calibrated`), sehingga keputusan
biner "aspek ini disebut atau tidak" tetap identik dengan sebelum kalibrasi. Tanpa penggeseran
itu, kalibrasi yang seharusnya hanya menyentuh angka keyakinan akan diam-diam mengubah aspek
mana yang terdeteksi.

Antarmuka menampilkan angka keyakinan **hanya bila `AnalysisResult.confidence_calibrated`
bernilai true**, dan medan itu dibaca dari isi bundle - bukan dari saklar konfigurasi. Sebuah
checkpoint yang belum dikalibrasi tidak dapat "dianggap" terkalibrasi karena seseorang lupa
mematikan sesuatu.

`ml/text/calibrate.py` **menolak menulis suhu** bila akurasi sebelum dan sesudah berbeda. Itu
tidak mungkin terjadi secara matematis untuk suhu positif - jadi kalau terjadi, yang ada adalah
bug, dan seluruh evaluasi yang sudah dilaporkan ikut tidak berlaku.

---

## 10. Aturan agregasi klausa menjadi dokumen (L2)

**Status: aturan diganti, angka menunggu checkpoint.**

Model bekerja pada **klausa**; dataset berlabel manusia memberi label pada **dokumen**.
Jembatan di antaranya adalah aturan keputusan - dan aturan itu pilihan produk, bukan detail
teknis evaluasi.

### Temuan: skrip evaluasi mengukur sistem yang tidak dikirimkan

Sampai audit ini, `evaluate_external.py` dan `tune_sentiment_threshold.py` memakai **suara
terbanyak** klausa, dan keduanya menuliskannya sendiri-sendiri. Backend memakai aturan yang
sama sekali berbeda: satu klausa negatif ber-aspek sudah cukup untuk menghitung ulasan sebagai
berkeluhan (`tools/segments.py`, `services/analyze.py`).

Akibatnya macro-F1 yang dilaporkan menggambarkan sistem yang tidak pernah sampai ke pengguna.

### Perubahan

Aturannya dipindahkan ke satu sumber, `ml/text/aggregate.py`, dan aturan produksinya menjadi
**asimetris**: satu klausa dengan P(negatif) ≥ 0,5 menegatifkan dokumen, berapa pun jumlah
klausa positif di sekitarnya. Sisi lain tidak disentuh.

Asimetrinya disengaja. Keluhan yang terlewat berarti pemilik toko tidak pernah tahu ada
masalah; pujian yang terlewat berarti satu baris kurang di daftar peluang. Aturan yang
memperlakukan keduanya setara salah menimbang sejak awal.

Ambang 0,5 bukan pilihan selera: pada tiga kelas, probabilitas ≥ 0,5 pasti argmax-nya. Aturan
ini karenanya tidak pernah "menyelamatkan" klausa yang modelnya sendiri ragu - ia berhenti
menenggelamkan klausa yang modelnya SUDAH yakin. Temuan Fase 8 menunjukkan tidak ada yang bisa
dipungut di bawah itu: 113 dari 128 yang terlewat berada di bawah P(negatif) 0,10.

### Kedua aturan dilaporkan berdampingan

`evaluate_external.py` sekarang menghitung **keduanya** dari satu kali inferensi, dan mencetak
recall kelas negatif secara terpisah dari macro-F1.

Aturan asimetris **pasti** menaikkan recall negatif dan **pasti** menurunkan presisinya; yang
tidak diketahui adalah besarannya. Mengganti diam-diam berarti mengklaim perbaikan tanpa
mengukurnya - persis kesalahan yang sudah tercatat sekali di LIMITATIONS (penyetelan ambang
Fase 8, yang "perbaikannya" ternyata berada dalam derau). Angka pertukaran itu diisi di sini
setelah dijalankan pada checkpoint.
