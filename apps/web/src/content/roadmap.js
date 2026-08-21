/** Isi layar Roadmap.
 *
 * Layar ini ada supaya batas versi sekarang terbaca sebagai keputusan, bukan sebagai
 * kekurangan yang disembunyikan. Karena itu tiap butir menyebut ALASAN teknisnya, bukan
 * sekadar "coming soon". Sumbernya docs/LIMITATIONS.md dan docs/SCOPE_FREEZE.md - kalau
 * salah satu berubah, berkas ini ikut diperbarui.
 *
 * `stage` menentukan letaknya pada rel: butir bertahap dari yang paling pasti ke yang paling
 * belum tentu. Urutan larik ini ADALAH urutan tampilnya - jangan disortir ulang di komponen,
 * karena urutan itu memuat informasi (butir kedua menunggu butir pertama).
 */

/** Perhentian pada rel, berurutan dari yang paling dekat. */
export const ROADMAP_STAGES = [
  ["aktif", "Sedang dikerjakan"],
  ["menunggu", "Menunggu prasyarat"],
  ["antre", "Dalam antrean"],
  ["kandidat", "Masih dipertimbangkan"],
];

export const ROADMAP = [
  {
    id: "visual",
    stage: "aktif",
    title: "Kesimpulan otomatis dari foto ulasan",
    status: "Diuji, belum lolos",
    body:
      "Foto yang Anda unggah sudah bisa dibaca teksnya, tetapi menyimpulkan kondisi barang dari gambarnya belum. Pengujian pada 97 foto ulasan asli menempatkan model di bawah tebakan sepele, dan 61% foto yang sebenarnya normal salah ditandai bermasalah. Menyalakannya sekarang berarti mengirim Anda memeriksa barang yang tidak apa-apa. Batas itu kini dijaga kode, bukan ingatan: sistem menolak menyalakan jalur foto selama pengujiannya belum lolos, siapa pun yang mencoba.",
  },
  {
    id: "kontradiksi",
    stage: "menunggu",
    title: "Deteksi otomatis saat foto membantah teksnya",
    status: "Belum bisa dimulai",
    blockedBy: "Kesimpulan otomatis dari foto ulasan",
    body:
      "Menandai ulasan yang menulis “barangnya bagus” tetapi melampirkan foto barang rusak. Mesin pembandingnya sudah ada di backend; yang belum ada adalah sisi foto yang cukup dapat dipercaya untuk dijadikan pembanding.",
  },
  {
    id: "riwayat",
    stage: "aktif",
    title: "Riwayat antar-sesi",
    status: "Ada, dengan cara yang berbeda",
    body:
      "Kami tetap tidak menyimpan apa pun di server. Gantinya, halaman hasil punya tombol unduh arsip - sekeping berkas berisi angka saja, tanpa teks ulasan - yang bisa Anda unggah kembali bulan depan untuk melihat apa yang berubah. Arsipnya milik Anda dan ada di komputer Anda; kalau hilang, riwayatnya ikut hilang, dan itu memang konsekuensi dari tidak menyimpan apa pun.",
  },
  {
    id: "kalibrasi",
    stage: "menunggu",
    title: "Angka keyakinan model yang benar-benar terukur",
    status: "Alatnya siap, angkanya belum",
    body:
      "Laporan sempat menampilkan “keyakinan model 80%”. Angka itu tidak pernah diukur - ia nilai tetap yang dipasang sementara, dan sama saja untuk semua aspek. Ia dicabut dari layar alih-alih dibiarkan, karena angka tetap yang berdiri di antara angka-angka hasil hitungan akan terbaca sebagai hasil hitungan juga. Penggantinya sudah dibangun dan tinggal dijalankan pada data uji terpisah; angkanya kembali ke layar dengan sendirinya begitu benar-benar terukur, tanpa ada yang perlu menyalakannya.",
  },
  {
    id: "multitoko",
    stage: "kandidat",
    title: "Multi-toko dan pembagian akses tim",
    status: "Belum komitmen",
    body:
      "Satu akun untuk beberapa toko sekaligus, dengan hak akses berbeda per anggota tim. Butuh akun dan penyimpanan permanen, dua hal yang sengaja tidak ada pada versi ini.",
  },
  {
    id: "koneksi",
    stage: "kandidat",
    title: "Tarik ulasan langsung dari marketplace",
    status: "Belum komitmen",
    body:
      "Menghapus langkah ekspor-lalu-unggah. Status legal pengambilan data otomatis masih setengah terverifikasi, jadi versi ini hanya bekerja dari berkas yang Anda ekspor sendiri.",
  },
];
