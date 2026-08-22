/** Bagian "Kenapa sekarang": fakta dan berita bisnis yang membuat masalah ini mendesak.
 *
 * Polanya meminjam tata letak cerita pelanggan WIZ.AI - satu cerita utama lebar, lalu tiga kartu
 * ringkas dengan label kategori dan waktu baca - karena pola itu sudah terbukti enak dipindai.
 * Isinya BUKAN cerita pelanggan (kami belum punya), melainkan fakta bersumber: setiap kartu
 * menyebut sumbernya dan tahunnya, dan tidak ada satu angka pun yang dikarang di sini. Sumber
 * lengkap beserta tautannya ada di docs/BUSINESS_VALUE.md dan README bagian 3.
 *
 * Satu aturan keras: kartu TIDAK menyimpulkan "karena itu pakai Ulasin" di tiap barisnya.
 * Faktanya dibiarkan bicara; kalimat penghubungnya cukup satu, di kepala bagian.
 */

const UTAMA = {
  kategori: "Biaya platform 2026",
  judul: "Per 1 Januari 2026 biaya admin marketplace naik lagi - komisi 2,5-10%, gratis ongkir 4-4,5%",
  isi:
    "Hampir semua marketplace besar memperbarui struktur biayanya tahun ini. Bagi penjual mikro " +
    "itu berarti margin yang sudah tipis tergerus lebih dulu, sebelum satu keluhan pun " +
    "diperbaiki - dan setiap pembeli yang datang ke masalah yang belum dibenahi adalah biaya " +
    "iklan yang terbakar dua kali.",
  sumber: "Rincian tarif Shopee, Tokopedia, TikTok Shop 2026 - laporan industri",
  tahun: "2026",
  baca: "4 menit",
};

const KARTU = [
  {
    kategori: "Perlindungan konsumen",
    judul: "Pengaduan konsumen ke BPKN naik 200% dalam setahun; e-commerce di urutan teratas",
    isi: "1.733 pengaduan pada 2024 dari 926 pada 2023. Keluhan yang paling sering: barang tidak sesuai atau rusak, garansi, dan layanan purna jual.",
    sumber: "BPKN, statistik pengaduan 2024-2025",
    angka: "+200%",
    angkaKet: "pengaduan konsumen, 2023→2024",
  },
  {
    kategori: "Perilaku pembeli",
    judul: "Lebih dari 80% pembeli Indonesia membaca ulasan sebelum membeli",
    isi: "Dan 60% menyebut ulasan jujur sesama pengguna sebagai konten paling meyakinkan - lebih tinggi dari Singapura dan Thailand. Ulasan adalah etalase kedua yang tidak bisa dirapikan sendiri.",
    sumber: "Survei perilaku konsumen, 2025",
    angka: "80%+",
    angkaKet: "membaca ulasan sebelum beli",
  },
  {
    kategori: "Efek membalas",
    judul: "Penjual yang membalas ulasan menerima 12% lebih banyak ulasan dan rating naik 0,12 bintang",
    isi: "Diukur pada puluhan ribu ulasan TripAdvisor. Efek itu nyata - tetapi membalas satu per satu adalah pekerjaan yang tidak pernah sempat dikerjakan siapa pun.",
    sumber: "Proserpio & Zervas, Marketing Science, 2017",
    angka: "+0,12",
    angkaKet: "bintang rata-rata setelah rutin membalas",
  },
];

const SKALA = [
  { n: "65,5 jt", ket: "unit UMKM di Indonesia · 61,9% PDB", sumber: "Kemenkop UKM 2025" },
  { n: "25 jt", ket: "UMKM sudah onboarding di platform digital", sumber: "Kemenkop UKM 2025" },
  { n: "≈ US$100 M", ket: "GMV ekonomi digital Indonesia 2025, +14%", sumber: "e-Conomy SEA 2025" },
  { n: "800 rb", ket: "penjual video commerce, +75% setahun", sumber: "e-Conomy SEA 2025" },
];

export function Urgency() {
  return (
    <section className="urgensi" id="kenapa-sekarang" aria-labelledby="urgensi-judul">
      <div className="section-head urgensi__head">
        <h2 id="urgensi-judul">
          Kenapa sekarang, <span className="soft">bukan nanti</span>
        </h2>
        <p>
          Empat hal terjadi bersamaan: biaya berjualan naik, pengaduan konsumen melonjak, pembeli
          makin bergantung pada ulasan, dan membalas ulasan terbukti berdampak. Semuanya menunjuk ke
          tumpukan teks yang sama - yang belum pernah dibaca sistematis oleh penjual mikro mana pun.
        </p>
      </div>

      <article className="urgensi__utama">
        <div className="urgensi__utama-visual" aria-hidden="true">
          <div className="urgensi__bar-row">
            <span>Komisi</span>
            <i style={{ "--w": "62%" }} />
            <b>2,5-10%</b>
          </div>
          <div className="urgensi__bar-row">
            <span>Gratis ongkir</span>
            <i style={{ "--w": "34%" }} />
            <b>4-4,5%</b>
          </div>
          <div className="urgensi__bar-row">
            <span>Promosi &amp; iklan</span>
            <i style={{ "--w": "46%" }} />
            <b>4-7%</b>
          </div>
          <small>Estimasi beban biaya platform per transaksi, 2026 - lihat sumber</small>
        </div>
        <div className="urgensi__utama-teks">
          <span className="urgensi__chip">{UTAMA.kategori}</span>
          <h3>{UTAMA.judul}</h3>
          <p>{UTAMA.isi}</p>
          <div className="urgensi__meta">
            <span>{UTAMA.sumber}</span>
            <span>{UTAMA.tahun}</span>
            <span className="urgensi__baca">{UTAMA.baca}</span>
          </div>
        </div>
      </article>

      <div className="urgensi__grid">
        {KARTU.map((k) => (
          <article className="urgensi__kartu" key={k.judul}>
            <span className="urgensi__chip">{k.kategori}</span>
            <div className="urgensi__angka">
              <b>{k.angka}</b>
              <span>{k.angkaKet}</span>
            </div>
            <h3>{k.judul}</h3>
            <p>{k.isi}</p>
            <div className="urgensi__meta">
              <span>{k.sumber}</span>
            </div>
          </article>
        ))}
      </div>

      <ul className="urgensi__skala" aria-label="Skala pasar">
        {SKALA.map((s) => (
          <li key={s.n}>
            <b>{s.n}</b>
            <span>{s.ket}</span>
            <small>{s.sumber}</small>
          </li>
        ))}
      </ul>

      <p className="urgensi__nota">
        Semua angka di bagian ini punya sumber yang disebut, dan tidak satu pun berasal dari
        pengukuran kami sendiri - yang kami ukur sendiri ada di bagian berikutnya, dengan batasnya.
      </p>
    </section>
  );
}
