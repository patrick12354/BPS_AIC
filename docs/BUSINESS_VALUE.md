# Business Value

Dokumen ini menjawab pertanyaan yang tidak dijawab dokumen teknis mana pun di repositori:
**siapa yang membayar, berapa ongkosnya, dan apakah ini layak dipakai di luar demo lomba.**
Sisi tata kelola - privasi, pengawasan manusia, risiko AI, bias, regulasi - ada di
[RESPONSIBLE_AI.md](RESPONSIBLE_AI.md) dan tidak diulang di sini.

## 0. Aturan bukti yang dipakai dokumen ini

Setiap angka di bawah membawa penanda asalnya. Ini konvensi yang sama dengan
[`docs/reference/AIC_RESEARCH_DOSSIER.md`](reference/AIC_RESEARCH_DOSSIER.md), dan dipakai
karena dokumen bisnis adalah tempat paling mudah menyelundupkan angka yang enak dibaca tetapi
tidak berdasar.

| Penanda | Artinya |
| --- | --- |
| `[TERUKUR]` | Diukur sendiri pada sistem ini, angkanya dapat direproduksi dari repositori |
| `[STATISTIK RESMI]` | Lembaga resmi (BPS, Kementerian UMKM, Bank Indonesia, OJK) |
| `[LAPORAN INDUSTRI]` | Laporan industri atau harga publik vendor |
| `[TURUNAN]` | Hitungan dari angka bertanda lain; rumusnya ditulis supaya dapat diperiksa |
| `[ASUMSI]` | **Belum divalidasi.** Ditulis eksplisit supaya dapat dibantah |
| `[DATA GAP]` | Angkanya dibutuhkan tetapi tidak ada sumber publiknya; dibiarkan kosong, tidak ditaksir |

Kurs yang dipakai sepanjang dokumen: **Rp16.000 per USD** `[ASUMSI]`. Angka rupiah hasil
konversi ikut berubah kalau kursnya berubah; angka USD-nya yang asli.

---

## 1. Masalahnya dalam angka

| Angka | Nilai | Sumber |
| --- | --- | --- |
| Unit usaha e-commerce di Indonesia (2024) | **4,40 juta**, naik 15,3% setahun dan 86% dalam empat tahun, mayoritas usaha mikro | `[STATISTIK RESMI]` BPS, Statistik E-Commerce 2024 |
| Populasi UMKM (2025) | ~66 juta unit, >60% PDB, ~97% penyerapan tenaga kerja | `[STATISTIK RESMI]` Kementerian Koperasi dan UKM |
| UMKM yang aktif memakai platform digital | ~30% | `[LAPORAN INDUSTRI]` gabungan, perlu verifikasi silang |
| GMV e-commerce Indonesia (2025) | ~USD 71 miliar, tumbuh >14% | `[LAPORAN INDUSTRI]` e-Conomy SEA 2025 |
| Biaya platform berlapis yang ditanggung penjual | 15-20% dari harga jual (komisi 2,5-10%, gratis ongkir 4-4,5%, promosi 1-2%, iklan 3-5%) | `[LAPORAN INDUSTRI]` Kompas.com 2026 |
| Pengaduan konsumen BPKN (2024) | 1.733, naik 200% dari 926 pada 2023; e-commerce sektor teratas setelah jasa keuangan | `[STATISTIK RESMI]` BPKN |

Dua angka terakhir yang membuat masalah ini mendesak, bukan sekadar besar. Margin penjual sudah
tergerus 15-20% sebelum satu rupiah pun masuk kantong, **dan** keluhan konsumen sedang naik
tajam. Dalam kondisi itu, setiap keluhan berulang yang tidak terdeteksi adalah dua kerugian
sekaligus: penjualan yang hilang, dan biaya iklan yang dibakar untuk mendatangkan pembeli ke
masalah yang belum diperbaiki.

### Kenapa ulasannya tidak dibaca

Bukan karena pemiliknya malas. [Persona "Bu Rina"](reference/AIC_RESEARCH_DOSSIER.md) - UMKM
fesyen mikro, dua karyawan, jualan di tiga kanal - membalas chat manual di tiga aplikasi dan
"membaca ulasan sesekali saat sempat". Kendalanya waktu dan volume, bukan niat.

Berapa lama sebenarnya? Angka ini sengaja disajikan sebagai aritmetika terbuka, bukan sebagai
temuan:

```
Membaca 1 ulasan, memahaminya, dan mencatat polanya   ≈ 20 detik   [ASUMSI]
300 ulasan sebulan                                     = 100 menit
Ditambah merekap dan mengurutkan mana yang mendesak    ≈ 60 menit   [ASUMSI]
                                                       ------------
Total                                                  ≈ 2,7 jam/bulan
```

**Dua angka di atas adalah asumsi yang belum divalidasi wawancara**, dan itu disebut di muka.
Yang bukan asumsi adalah sisi sistemnya: 66 ulasan selesai dianalisis dalam **88 detik** pada
CPU dua inti tanpa kartu grafis `[TERUKUR]`, sehingga 300 ulasan memakan sekitar 6,7 menit.

Perbandingan yang jujur karena itu bukan "hemat 2,7 jam", melainkan: **sisi mesinnya terukur,
sisi manusianya belum.** Validasi waktu baca manual masuk daftar riset yang belum dikerjakan
di bagian 9.

---

## 2. Target customer

Tiga segmen, diurutkan dari yang paling siap dilayani versi sekarang.

### Segmen 1 - Penjual mikro-kecil online (fokus utama)

| | |
| --- | --- |
| Profil | Pemilik merangkap operator, 0-5 karyawan, jualan di 1-3 marketplace |
| Volume ulasan | Puluhan sampai ratusan per bulan - cukup untuk berpola, terlalu banyak untuk dibaca |
| Anggaran perkakas | Sangat terbatas; idealnya gratis atau freemium `[STATISTIK RESMI]` mayoritas unit e-commerce adalah mikro, BPS 2024 |
| Kemampuan teknis | Tidak familiar API/coding; mengandalkan aplikasi siap pakai |
| Hambatan kepercayaan | Skeptis terhadap rekomendasi otomatis tanpa penjelasan alasan |

Hambatan terakhir itu yang membentuk produknya, bukan sekadar dicatat: setiap Action Card wajib
membawa kutipan asli dan tombol **Tolak**. Produk yang meminta kepercayaan buta akan ditolak
segmen ini, dan penolakan itu rasional.

### Segmen 2 - Pendamping UMKM (jalur distribusi, bukan sekadar pengguna)

Dinas koperasi dan UKM daerah, inkubator, dan asosiasi pedagang mendampingi ratusan UMKM
sekaligus. Bagi mereka, Ulasin adalah alat kerja pendamping: satu pemasangan melayani banyak
binaan. Ini jalur akuisisi termurah yang tersedia - lihat bagian 7.

### Segmen 3 - Merek menengah dengan banyak SKU (belum dilayani)

Butuh riwayat lintas periode, multi-toko, dan pembagian akses tim. Ketiganya **belum ada**
(lihat [LIMITATIONS.md](LIMITATIONS.md)), jadi segmen ini sengaja tidak dikejar sekarang.

### Sizing yang jujur

| Lapis | Angka | Cara memperolehnya |
| --- | --- | --- |
| Seluruh unit usaha e-commerce | 4,40 juta | `[STATISTIK RESMI]` BPS 2024 |
| Yang punya ulasan cukup untuk berpola | **tidak diketahui** | `[DATA GAP]` tidak ada statistik publik sebaran volume ulasan per penjual |
| Yang dapat dijangkau kanal awal (bagian 7) | **tidak diketahui** | `[DATA GAP]` bergantung kerja sama yang belum ada |

Angka TAM/SAM/SOM sengaja **tidak dikarang**. Dua baris terakhir adalah lubang data yang nyata,
dan mengisinya dengan persentase yang enak dibaca justru akan membuat seluruh dokumen ini
kehilangan kredibilitas - termasuk angka-angka yang benar.

---

## 3. Lanskap solusi existing

Bagian ini menyebut nama, bukan kategori. Tabel lengkap beserta kekurangan spesifik ada di
[README bagian 3](../README.md#3-masalah-dan-mengapa-ai-diperlukan); yang relevan di sini
adalah **harganya**.

| Solusi | Harga masuk | Sumber |
| --- | --- | --- |
| Shopee Seller Centre / Tokopedia Seller Dashboard | Gratis (bawaan platform) | - |
| Yotpo Reviews | dari USD 79/bulan (~Rp1,26 juta) | `[LAPORAN INDUSTRI]` harga publik vendor, 2026 |
| Birdeye | USD 299-449/bulan per lokasi, kontrak 12 bulan, onboarding USD 500-1.500 | `[LAPORAN INDUSTRI]` harga publik vendor, 2026 |
| Thematic | dari USD 2.000/bulan untuk 3 pengguna | `[LAPORAN INDUSTRI]` harga publik vendor, 2026 |

Tier termurah Birdeye saja sekitar **Rp4,8 juta per bulan** dengan komitmen setahun. Untuk
penjual yang marginnya sudah dipotong 15-20% biaya platform, angka itu bukan "mahal" - ia
berada di kategori yang berbeda sama sekali. Dan ketiga produk itu dirancang untuk ulasan
berbahasa Inggris, bukan untuk "bahannya oke sih cuma kekecilan bgt, sizechartnya ngaco".

**Celah yang ditempati Ulasin:** di antara yang gratis-tetapi-berhenti-di-rating dan yang
mampu-tetapi-berharga-perusahaan, tidak ada apa pun yang dirancang untuk Bahasa Indonesia
informal pada anggaran UMKM mikro.

---

## 4. Proposisi nilai dan cara mengukurnya

Nilai yang dijanjikan harus dapat dibantah, jadi tiap butir ditulis bersama ukuran yang
membuktikan atau menggugurkannya.

| Yang dijanjikan | Ukuran pembuktinya | Status |
| --- | --- | --- |
| Menghemat waktu membaca ulasan | Waktu analisis sistem vs waktu baca manual, diukur pada peserta yang sama | Sisi sistem `[TERUKUR]` 88 detik / 66 ulasan; sisi manusia **belum diukur** |
| Prioritas yang benar, bukan sekadar terurut | Tingkat penerimaan Action Card (tombol Terima vs Tolak) selama pemakaian nyata | Mekanisme perekamnya ada di UI; **belum ada data lapangan** |
| Rekomendasi dapat diverifikasi | Proporsi rekomendasi yang membawa kutipan pendukung | `[TERUKUR]` 100% menurut kontrak ACT-01 - kartu tanpa bukti tidak diterbitkan |
| Bekerja pada bahasa ulasan sungguhan | Akurasi sentimen pada label manusia | `[TERUKUR]` 0,730 vs leksikon 0,700 dan TF-IDF 0,627 ([MODEL_CARD](MODEL_CARD.md) §4.3) |
| Membalas ulasan memperbaiki reputasi toko (dasar fitur Draf Balasan) | Efek balasan penjual pada rating dan volume ulasan | `[LITERATUR]` Proserpio & Zervas, *Marketing Science* 36(5), 2017 - hotel yang mulai membalas ulasan TripAdvisor menerima +12% ulasan dan rating naik rata-rata +0,12 bintang (diringkas HBR, Feb 2018). Efek pada marketplace Indonesia **belum diukur**; fitur ini memberi draf, bukan klaim efek |

Baris kedua adalah yang paling penting sekaligus paling kosong. Tombol **Terima / Tolak** di
setiap Action Card bukan hiasan tata kelola - ia instrumen pengukuran produk yang paling
langsung, dan versi berikutnya harus merekamnya secara agregat (anonim) supaya klaim
"prioritasnya benar" berhenti menjadi klaim.

---

## 5. Model bisnis

### Bentuknya: freemium, dengan batas yang jujur

| Tingkat | Isi | Harga |
| --- | --- | --- |
| **Gratis** (= versi sekarang) | Analisis sesi ad-hoc, tanpa akun, tanpa riwayat. Seluruh fitur inti: prioritas, bukti, tanya jawab | Rp0 |
| **Berlangganan** (rencana) | Riwayat lintas periode, perbandingan antar-bulan, multi-toko, ekspor PDF/CSV | Rp39.000/bulan `[ASUMSI]` |
| **Lisensi institusi** (rencana) | Pemasangan sendiri untuk pendamping UMKM; satu instans melayani banyak binaan | Per instans, dinegosiasi |

**Tingkat berbayarnya persis daftar roadmap.** Itu bukan kebetulan: fitur yang belum dibangun
adalah fitur yang butuh akun dan penyimpanan permanen, dan justru akun serta penyimpanan itulah
yang membenarkan biaya berulang. Yang gratis tetap utuh sebagai produk - bukan versi lumpuh
yang memaksa upgrade.

> **Rp39.000 adalah hipotesis, bukan keputusan.** Belum ada satu pun wawancara kesediaan
> membayar. Angka itu ditaruh di sini supaya dapat diuji dan dibantah, dan bagian 9 mencatatnya
> sebagai riset yang belum dikerjakan.

### Yang sengaja TIDAK dilakukan

- **Menjual data pengguna.** Ditutup secara arsitektur, bukan secara kebijakan: tidak ada
  penyimpanan permanen (ADR-010), jadi tidak ada aset data yang bisa dijual sekalipun ada
  yang menawar.
- **Iklan di dalam produk.** Perkakas yang menyarankan prioritas kerja kehilangan seluruh
  kredibilitasnya begitu urutannya bisa dibeli.
- **Biaya per analisis.** Menghitung ongkos tiap kali menekan tombol membuat pengguna ragu
  memakainya - persis kebalikan dari yang produk ini butuhkan.

---

## 6. Struktur biaya

### Kapasitas terukur

Seluruh hitungan di bawah berangkat dari satu angka yang diukur sendiri, bukan diperkirakan:
**66 ulasan / 88 detik pada e2-standard-2 (2 vCPU, 8 GB), CPU saja, tanpa GPU** `[TERUKUR]`.

```
Laju                = 66 ulasan / 88 detik      = 0,75 ulasan/detik   [TERUKUR]
Kapasitas per jam   = 0,75 x 3.600              = 2.700 ulasan
Kapasitas per bulan = 2.700 x 24 x 30           = 1.944.000 ulasan    (utilisasi 100%)
Pada utilisasi 10%                              = 194.400 ulasan      [ASUMSI]
Bila 1 penjual = 300 ulasan/bulan               = 648 penjual/instans [ASUMSI]
```

### Ongkos per penjual

| Pos | Nilai bulanan |
| --- | --- |
| VM e2-standard-2, us-central1, on-demand | ~USD 49 (~Rp784.000) `[LAPORAN INDUSTRI]` harga publik GCP |
| Penyimpanan model + disk | ~USD 5 (~Rp80.000) `[LAPORAN INDUSTRI]` |
| Biaya API pihak ketiga | **Rp0** - seluruh model berjalan lokal (ADR-001) |
| **Total per instans** | **~USD 54 (~Rp864.000)** |
| **Ongkos marginal per penjual** | **~Rp1.330** `[TURUNAN]` = Rp864.000 / 648 penjual |

Angka Rp1.330 itulah yang membuat tingkat gratis mungkin, dan ia hasil langsung dari ADR-001
(local-first, bukan API komersial). Kalau lapisan teksnya memanggil API berbayar per ulasan,
ongkos marginalnya akan naik bersama volume dan tingkat gratis menjadi mustahil.

Dua batas yang harus disebut jujur:

1. **Utilisasi 10% adalah asumsi.** Beban nyata menumpuk pada jam kerja, bukan merata 24 jam.
2. **Model bahasa lapisan 5 belum berjalan** (lihat [README §5.2](../README.md#52-lima-lapisan-ai)).
   Menyalakannya menambah 4-6 GB RAM dan menuntut kelas mesin lebih besar, sehingga hitungan
   di atas **hanya berlaku untuk konfigurasi yang benar-benar dijalankan hari ini**.

### Perbandingan

| | Ulasin (hipotesis) | Birdeye (tier masuk) |
| --- | --- | --- |
| Harga bulanan penjual | Rp39.000 | ~Rp4.784.000 |
| Komitmen | Tidak ada | 12 bulan |
| Onboarding | Rp0 | USD 500-1.500 |

Selisihnya sekitar **123 kali** `[TURUNAN]`. Selisih itu tidak datang dari efisiensi ajaib -
ia datang dari cakupan yang jauh lebih sempit dan disengaja: Ulasin mengerjakan satu pekerjaan
(ulasan → prioritas berbukti) untuk satu bahasa, sementara Birdeye adalah rangkaian produk
reputasi multi-lokasi.

---

## 7. Kelayakan adopsi

Hambatan diambil langsung dari persona pada dossier, bukan dikarang, dan tiap baris menyebut
apa yang **sudah** ada di produk versus apa yang masih rencana.

| Hambatan | Jawaban desain | Sudah ada? |
| --- | --- | --- |
| Anggaran perkakas hampir nol | Tingkat gratis yang utuh; ongkos marginal Rp1.330 membuatnya berkelanjutan | ✅ |
| Tidak familiar API/coding | Tempel teks, unggah CSV, atau lampirkan tangkapan layar - tanpa pemasangan, tanpa akun | ✅ |
| Data tersebar sebagai tangkapan layar | Jalur OCR membaca tangkapan layar dan hasilnya masih dapat disunting | ✅ |
| Skeptis pada rekomendasi tanpa alasan | Tiap Action Card membawa kutipan asli + tombol Tolak | ✅ |
| Takut data pelanggannya bocor | Redaksi PII wajib sebelum model apa pun; tanpa penyimpanan permanen | ✅ |
| Ragu apakah berguna sebelum mencoba | Dataset contoh sekali klik | ✅ |
| Ingin melihat perubahan antar-bulan | Riwayat lintas periode | ❌ roadmap |

Enam dari tujuh hambatan sudah terjawab produk yang berjalan. Itu bukan kebetulan - daftar
hambatan ini yang menentukan urutan pengerjaan, bukan sebaliknya.

### Jalur ke pasar

Beriklan ke penjual mikro satu per satu terlalu mahal untuk produk seharga Rp39.000. Jalur yang
masuk akal adalah **lewat pendamping** (Segmen 2): satu dinas koperasi atau asosiasi pedagang
memperkenalkan alat ini ke ratusan binaan sekaligus, dan pendamping itu punya insentif sendiri -
mereka butuh bukti dampak pendampingan.

`[ASUMSI]` Belum ada satu pun kerja sama semacam itu. Ini hipotesis distribusi, bukan rencana
yang sudah berjalan.

---

## 8. Model deployment

| Model | Untuk siapa | Status |
| --- | --- | --- |
| **Demo publik terkelola** | Siapa saja yang ingin mencoba | ✅ berjalan, lihat [DEPLOYMENT.md](DEPLOYMENT.md) |
| **Pemasangan sendiri** via `docker compose up` | Pendamping UMKM, organisasi yang datanya tidak boleh keluar | ✅ berjalan |
| **SaaS multi-penyewa** | Tingkat berlangganan | ❌ butuh akun + penyimpanan permanen |

Bahwa jalur pemasangan sendiri **sudah** berfungsi bukan detail teknis - itu proposisi nilai
tersendiri bagi organisasi yang tidak boleh mengirim data binaannya ke server pihak lain.
Arsitektur local-first (ADR-001) membuatnya mungkin tanpa jalur kode kedua: image yang sama
melayani demo publik dan pemasangan pribadi.

---

## 9. Yang belum divalidasi

Daftar ini ada supaya tidak ada yang perlu menebak bagian mana dari dokumen ini yang berdiri di
atas bukti dan bagian mana yang berdiri di atas asumsi.

| Belum divalidasi | Cara memvalidasinya | Kalau ternyata salah |
| --- | --- | --- |
| Waktu baca ulasan manual (20 detik/ulasan) | Uji waktu pada 5-10 pemilik UMKM | Klaim penghematan waktu harus ditulis ulang |
| Kesediaan membayar Rp39.000/bulan | Wawancara harga pada segmen 1 | Model bisnis bergeser sepenuhnya ke lisensi institusi |
| Utilisasi 10% per instans | Pemantauan beban nyata | Ongkos marginal per penjual naik, tingkat gratis perlu dibatasi |
| 300 ulasan/penjual/bulan | Survei volume ulasan | Seluruh hitungan kapasitas bergeser |
| Pendamping UMKM sebagai kanal distribusi | Uji coba dengan satu dinas atau asosiasi | Butuh kanal akuisisi lain yang belum teridentifikasi |
| Prioritas yang dihasilkan benar-benar berguna | Rekam agregat Terima/Tolak selama pemakaian nyata | Formula skor prioritas ([README §5.4](../README.md#54-formula-skor-prioritas)) perlu dikalibrasi ulang |
| Label aspek model pada penilaian manusia independen | Dua pelabel + adjudikator, kappa per aspek - perangkatnya sudah ada (`scripts/build_aspect_human_pack.py`, `ml/text/evaluate_aspect_human.py`) | Kepala aspek diganti/dilatih ulang; klaim "mengelompokkan keluhan per aspek" harus dibatasi pada aspek yang terbukti |
| Efek Draf Balasan pada marketplace Indonesia | Bandingkan rating/volume ulasan toko sebelum-sesudah rutin membalas (desain sebelum-sesudah dengan pembanding) | Fitur tetap berguna sebagai penghemat waktu, tetapi klaim dampak reputasi dicabut |

Baris terakhir adalah risiko produk terbesar yang diketahui: bobot 0,3 dan 0,2 pada formula
prioritas **belum divalidasi**, dan tidak akan tervalidasi oleh data laboratorium mana pun -
hanya pemakaian nyata yang bisa menjawabnya.

---

## 10. Risiko bisnis

| Risiko | Kemungkinan | Mitigasi yang sudah ada |
| --- | --- | --- |
| Marketplace meluncurkan fitur serupa gratis | Sedang | Jalur pemasangan sendiri dan netralitas lintas kanal tetap bernilai; satu marketplace tidak akan menganalisis ulasan penjualnya di marketplace lain |
| Ulasan palsu mencemari masukan | Sedang | **Belum dimitigasi.** Deteksi ulasan palsu di luar cakupan versi ini dan disebut sebagai batas, bukan diam-diam diabaikan |
| Perubahan format ekspor marketplace | Tinggi | Pemetaan kolom ditebak otomatis dan tetap dapat dikoreksi pengguna, jadi format baru tidak mematahkan alurnya |
| Biaya infrastruktur naik seiring pemakaian | Rendah | Ongkos marginal Rp1.330 memberi ruang besar sebelum ekonominya berbalik |
| Pengguna terlalu percaya pada rekomendasi | Sedang | Tombol Tolak, kutipan wajib, badge "data terbatas" di bawah 15 ulasan; selebihnya lihat [RESPONSIBLE_AI.md](RESPONSIBLE_AI.md) |

---

## 11. Ringkasan satu halaman

- Pasarnya nyata dan terukur resmi: **4,40 juta unit usaha e-commerce**, mayoritas mikro,
  dengan margin yang sudah tergerus 15-20% biaya platform.
- Solusi existing terbelah dua: **gratis tetapi berhenti di rating**, atau **mampu tetapi
  berharga Rp4,8-32 juta per bulan** dan dirancang untuk bahasa Inggris.
- Ongkos marginal melayani satu penjual adalah **~Rp1.330 per bulan** `[TURUNAN]` dari
  benchmark yang diukur sendiri - itulah yang membuat tingkat gratis berkelanjutan, dan itu
  konsekuensi langsung dari keputusan local-first (ADR-001).
- Tingkat berbayarnya persis daftar roadmap, sehingga tidak ada fitur yang perlu ditahan
  demi memaksa upgrade.
- Enam dari tujuh hambatan adopsi yang teridentifikasi sudah terjawab produk yang berjalan
  hari ini.
- **Harga, kesediaan membayar, dan kanal distribusinya belum divalidasi sama sekali** - dan
  itu tertulis di bagian 9, bukan tersembunyi.
