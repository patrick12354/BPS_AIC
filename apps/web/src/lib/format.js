/** Label dan pemformat yang dipakai lintas layar.
 *
 * Semuanya dikumpulkan di sini karena label yang sama muncul di kartu aksi, tabel
 * benchmark, grafik aspek, dan jawaban tanya jawab - kalau tersebar, tiga di antaranya
 * pasti tertinggal saat ada istilah yang diubah.
 */

export const URGENCY_LABEL = { tinggi: "Tinggi", sedang: "Sedang", rendah: "Rendah" };

export const QUALITY_LABEL = { baik: "Baik", cukup: "Cukup", terbatas: "Terbatas" };

const ASPECT_LABEL = {
  kualitas_produk: "kualitas produk",
  kesesuaian_deskripsi: "kesesuaian deskripsi",
  harga_value: "harga",
  kemasan: "kemasan",
  pengiriman: "pengiriman",
  pelayanan_penjual: "pelayanan penjual",
  ukuran_varian: "ukuran/varian",
  rasa_kualitas_makanan: "rasa",
  kelengkapan: "kelengkapan",
  keaslian: "keaslian",
  kemudahan_penggunaan: "kemudahan pemakaian",
};

export const VISUAL_LABEL = {
  produk_rusak: "Produk rusak",
  kemasan_rusak: "Kemasan rusak",
  salah_kirim: "Salah kirim",
  produk_berbeda: "Produk berbeda dari pesanan",
  produk_normal: "Produk terlihat normal",
  normal: "Tidak ada masalah visual",
};

export const WARNING_TEXT = {
  data_kecil:
    "Data Anda kurang dari 15 ulasan. Anggap hasil ini sebagai indikasi awal, bukan kesimpulan pasti.",
  baris_dilewati: "Sebagian baris dilewati karena kosong atau terduplikasi.",
  pii_diredaksi:
    "Nomor telepon dan data pribadi yang ditemukan sudah disamarkan sebelum dianalisis.",
  // Tidak lagi dikirim backend sejak narasi template diakui sebagai jalur normal; entri
  // dipertahankan agar payload dari versi lama tetap punya teks, dengan kalimat yang netral.
  mode_sederhana: "Narasi disusun dari template deterministik. Seluruh angka dan bukti lengkap.",
  data_kosong: "Tidak ada ulasan yang dapat dianalisis dari data ini.",
};

/** Kategori yang benar-benar dikenal backend (`Category` di apps/api/app/schemas/enums.py
 *  dan `categories` di configs/taxonomy.yaml). Menambah entri di sini tanpa menambahnya di
 *  dua tempat itu membuat analisis ditolak 422 saat tombolnya ditekan. */
export const CATEGORIES = [
  ["fashion", "Fashion"],
  ["electronics", "Elektronik"],
  ["food_beverage", "Makanan & Minuman"],
  ["craft", "Kerajinan Tangan"],
  ["other", "Lainnya"],
];

export const CATEGORY_LABEL = Object.fromEntries(CATEGORIES);

export const TREND_LABEL = {
  meningkat: "keluhan naik",
  menurun: "keluhan turun",
  stabil: "stabil",
  tidak_cukup_data: "data belum cukup",
};

export const SEVERITY_LABEL = { tinggi: "berat", sedang: "sedang", rendah: "ringan" };

export const CONFIDENCE_LABEL = { tinggi: "tinggi", sedang: "sedang", rendah: "rendah" };

export const aspectLabel = (id) => ASPECT_LABEL[id] ?? id;

export const pct = (value) => `${Math.round(value * 100)}%`;

/** Aspek dengan huruf pertama kapital - untuk judul baris, bukan untuk di tengah kalimat. */
export const aspectTitle = (id) => {
  const label = aspectLabel(id);
  return label.charAt(0).toUpperCase() + label.slice(1);
};

/** Angka desimal gaya Indonesia: koma, bukan titik. */
export const desimal = (value, digits = 1) =>
  value == null ? "—" : value.toLocaleString("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits });

const BULAN_PENDEK = [
  "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
  "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
];

/** "Okt 2025 – Agu 2026", atau "Agu 2026" kalau keduanya jatuh di bulan yang sama. */
export function rentangTanggal(mulai, selesai) {
  if (!mulai || !selesai) return null;
  const a = new Date(mulai);
  const b = new Date(selesai);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return null;
  const tulis = (d) => `${BULAN_PENDEK[d.getMonth()]} ${d.getFullYear()}`;
  return tulis(a) === tulis(b) ? tulis(a) : `${tulis(a)} – ${tulis(b)}`;
}
