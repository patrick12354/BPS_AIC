# Panduan Anotasi Aspek - Validasi Manusia Independen

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

- `asp_kualitas_produk` - Kualitas produk
- `asp_kesesuaian_deskripsi` - Kesesuaian dengan deskripsi/foto
- `asp_harga_value` - Harga / kesepadanan nilai
- `asp_ukuran_varian` - Ukuran / varian (porsi untuk F&B)
- `asp_rasa_kualitas_makanan` - Rasa / kualitas makanan
- `asp_kemasan` - Kemasan / packing
- `asp_pengiriman` - Pengiriman / kurir / kecepatan kirim
- `asp_pelayanan_penjual` - Pelayanan penjual / respons chat
- `asp_kelengkapan` - Kelengkapan isi paket
- `asp_keaslian` - Keaslian / orisinalitas
- `asp_kemudahan_penggunaan` - Kemudahan penggunaan / pemasangan

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
