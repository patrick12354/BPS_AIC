/** Bagian nilai bisnis: besaran masalahnya, celah di pasar, dan kenapa gratisnya bertahan.
 *
 * Bagian ini pernah dua kali salah bentuk sebelum sampai ke bentuk sekarang, dan keduanya
 * dicatat supaya tidak diulang.
 *
 * Versi pertama menggambar penggaris harga logaritmik. Idenya benar - celah paling jujur
 * digambar sebagai jarak - pelaksanaannya tidak: ketiga produk berbayar menumpuk di 40% kanan
 * penggaris sementara 60% kirinya kosong, dan labelnya bertabrakan sampai perlu diturunkan
 * bertingkat.
 *
 * Versi kedua menggantinya dengan lima baris seragam di satu daftar. Tabrakannya hilang,
 * tetapi bentuk itu memaksa dua pertanyaan yang berbeda dijawab dengan satu tata letak:
 * lawan yang gratis pertanyaannya "apa yang tidak bisa dilakukannya", lawan yang berbayar
 * pertanyaannya "berapa". Kolom harga pada baris Shopee dan Tokopedia cuma berisi kata
 * "Gratis" dua kali, dan kolom keterangan pada baris Yotpo memuat kalimat panjang yang tidak
 * sejajar dengan apa pun.
 *
 * Sekarang keduanya dipisah menurut pertanyaannya:
 *
 *   1. MATRIKS KEMAMPUAN untuk yang sama-sama gratis. Tabel betulan - kemampuan sebagai
 *      baris, tiga produk sebagai kolom - karena di sinilah perbandingannya per butir.
 *      Barisnya dikelompokkan tiga: yang ketiganya punya, yang cuma Ulasin punya, dan yang
 *      Ulasin BELUM punya. Kelompok ketiga bukan basa-basi kejujuran; tabel yang seluruh
 *      kolomnya menang terbaca sebagai brosur, dan pembaca berhenti mempercayainya.
 *   2. KARTU HARGA untuk yang berbayar. Di sini yang dibandingkan angka, jadi angkanya yang
 *      diberi ukuran terbesar dan posisi yang sama di tiap kartu.
 *
 * Celah di antara keduanya tetap digambar sebagai celah: satu pita bertanda, bukan jarak
 * kosong. Ruang kosong terbaca sebagai jeda tata letak, sedangkan yang harus terbaca di sini
 * adalah ketiadaan.
 *
 * Seluruh angka dan klaim kemampuan di berkas ini punya sumber di docs/BUSINESS_VALUE.md §3
 * dan README §3.2. Yang belum tervalidasi ditandai di layar, bukan hanya di dokumen - halaman
 * pemasaran adalah tempat paling menggoda untuk membulatkan angka, dan produk ini tidak
 * melakukannya.
 */

const KOLOM = [
  {
    nama: "Ulasin",
    pendek: "Ulasin",
    harga: "Gratis",
    ket: "rencana berlangganan Rp39.000 - masih hipotesis",
    kami: true,
  },
  { nama: "Shopee Seller Centre", pendek: "Shopee", harga: "Gratis", ket: "bawaan platform" },
  { nama: "Tokopedia Seller Dashboard", pendek: "Tokopedia", harga: "Gratis", ket: "bawaan platform" },
];

// Nilai tiap sel berurutan mengikuti KOLOM. Sumbernya README §3.2 untuk sisi platform dan
// LIMITATIONS.md untuk sisi Ulasin - termasuk kelompok ketiga, yang isinya persis daftar
// batasan yang sudah tercatat di sana.
// Tiga baris di kelompok ketiga sempat menyatakan ketiadaan yang sebenarnya cuma belum
// disurfacekan: statistik per produk dan sebaran bintang sudah dapat dihitung dari kolom yang
// memang diunggah pengguna, dan perbandingan antar bulan sudah ada di dalam berkas ekspor yang
// lazimnya membentang berbulan-bulan. Ketiganya kini dibangun, jadi barisnya pindah - tetapi
// pindah ke kelompok PERTAMA, bukan kedua: Shopee dan Tokopedia sama-sama punya keduanya, dan
// menaruhnya di "cuma ada di Ulasin" akan menukar satu klaim keliru dengan klaim keliru lain.
//
// Yang benar-benar cuma ada di sini adalah lapisan di atasnya - keluhan apa yang menghuni tiap
// pita bintang, dan aspek mana yang bergerak antar bulan - jadi itulah yang jadi baris baru di
// kelompok kedua.
//
// Kelompok ketiga sengaja tetap berisi. Tabel yang seluruh kolomnya menang terbaca sebagai
// brosur, dan pembaca berhenti mempercayainya; mengosongkannya untuk merayakan dua fitur baru
// akan merusak justru bagian yang membuat tabel ini layak dipercaya.
const KEMAMPUAN = [
  {
    judul: "Yang ketiganya sudah punya",
    baris: [
      { apa: "Rating rata-rata dan daftar ulasan yang masuk", nilai: ["ada", "ada", "ada"] },
      { apa: "Statistik per produk dan sebaran bintang", nilai: ["ada", "ada", "ada"] },
      { apa: "Perbandingan antar bulan", nilai: ["ada", "ada", "ada"] },
    ],
  },
  {
    judul: "Yang cuma ada di Ulasin",
    baris: [
      { apa: "Keluhan dikelompokkan per aspek, bukan per bintang", nilai: ["ada", "tidak", "tidak"] },
      { apa: "Keluhan apa yang ada di balik tiap bintang", nilai: ["ada", "tidak", "tidak"] },
      { apa: "Aspek mana yang bergerak antar bulan, bukan cuma ratingnya", nilai: ["ada", "tidak", "tidak"] },
      { apa: "Urutan mana yang paling mendesak diperbaiki", nilai: ["ada", "tidak", "tidak"] },
      { apa: "Tiap rekomendasi membawa kutipan ulasan aslinya", nilai: ["ada", "tidak", "tidak"] },
      { apa: "Shopee dan Tokopedia terbaca dalam satu layar", nilai: ["ada", "tidak", "tidak"] },
      { apa: "Tanya jawab bebas atas isi ulasan sendiri", nilai: ["ada", "tidak", "tidak"] },
    ],
  },
  {
    judul: "Yang belum ada di Ulasin",
    baris: [
      { apa: "Riwayat tersimpan sendiri, tanpa unggah ulang tiap kali", nilai: ["tidak", "ada", "ada"] },
      { apa: "Membalas ulasan langsung ke pembelinya", nilai: ["tidak", "ada", "ada"] },
      { apa: "Menarik ulasan otomatis tanpa ekspor manual", nilai: ["tidak", "ada", "ada"] },
    ],
  },
];

// Harga masuk termurah, per bulan. Sumbernya halaman harga publik tiap vendor, 2026, dengan
// kurs Rp16.000/USD - lihat docs/BUSINESS_VALUE.md bagian 3.
const TARIF = [
  {
    nama: "Yotpo",
    rupiah: 1_264_000,
    asli: "dari USD 79 per bulan",
    batas: "Alat mengumpulkan dan menampilkan ulasan, bukan menganalisis keluhan. Tanpa urutan prioritas tindakan.",
  },
  {
    nama: "Birdeye",
    rupiah: 4_784_000,
    asli: "USD 299 per bulan, per lokasi",
    batas: "Manajemen reputasi untuk bisnis multi-cabang. Dihitung per lokasi, bukan per penjual.",
    ikat: "Kontrak 12 bulan + onboarding USD 500-1.500",
  },
  {
    nama: "Thematic",
    rupiah: 32_000_000,
    asli: "dari USD 2.000 per bulan, 3 pengguna",
    batas: "Benar-benar mengekstrak tema - satu-satunya di daftar ini yang melakukannya. Model temanya tidak dilatih untuk ragam informal Bahasa Indonesia.",
  },
];

const juta = (n) => n.toLocaleString("id-ID", { maximumFractionDigits: 2 });

const HITUNGAN = [
  { nilai: "66 ulasan / 88 detik", ket: "terukur pada CPU dua inti, tanpa kartu grafis" },
  { nilai: "648 penjual per mesin", ket: "kalau tiap penjual menganalisis 300 ulasan sebulan" },
  { nilai: "≈ Rp1.330", ket: "ongkos melayani satu penjual, per bulan", hasil: true },
];

/** Isi satu sel matriks.
 *
 * Ketiadaan digambar sebagai setrip, bukan silang merah. Silang merah pada kolom pesaing
 * terbaca sebagai penilaian; setrip terbaca sebagai fakta - dan setrip yang sama dipakai di
 * kolom sendiri pada kelompok ketiga, yang tidak mungkin dilakukan kalau lambangnya menuduh.
 *
 * Tiap sel membawa teksnya sendiri untuk pembaca layar: ikon dan setrip tidak punya nama, dan
 * tabel yang selnya kosong bagi pembaca layar bukan tabel perbandingan sama sekali.
 */
function Sel({ nilai, kami, kolom }) {
  const kelas = `sel sel--${nilai} ${kami ? "sel--kami" : ""}`;
  if (nilai === "ada") {
    return (
      <td className={kelas} role="cell" data-kolom={kolom}>
        <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
          <path
            d="M3.4 8.5 6.4 11.5 12.7 5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="sr-only">Ada</span>
      </td>
    );
  }
  if (nilai === "rencana") {
    return (
      <td className={kelas} role="cell" data-kolom={kolom}>
        <span className="sel__rencana" aria-hidden="true">
          rencana
        </span>
        <span className="sr-only">Belum ada, masuk rencana tingkat berbayar</span>
      </td>
    );
  }
  return (
    <td className={kelas} role="cell" data-kolom={kolom}>
      <span className="sel__strip" aria-hidden="true" />
      <span className="sr-only">Tidak ada</span>
    </td>
  );
}

function Matriks() {
  return (
    <table className="matriks" role="table">
      <caption className="sr-only">
        Perbandingan kemampuan Ulasin dengan dashboard bawaan Shopee dan Tokopedia. Ketiganya
        gratis.
      </caption>
      <thead role="rowgroup">
        <tr role="row">
          <th className="matriks__sudut" scope="col" role="columnheader">
            <span className="sr-only">Kemampuan</span>
          </th>
          {KOLOM.map((k) => (
            <th
              key={k.nama}
              className={`matriks__kepala ${k.kami ? "matriks__kepala--kami" : ""}`}
              scope="col"
              role="columnheader"
            >
              <span className="matriks__merek">{k.nama}</span>
              <span className="matriks__harga">{k.harga}</span>
              <span className="matriks__ket">{k.ket}</span>
            </th>
          ))}
        </tr>
      </thead>

      {KEMAMPUAN.map((grup) => (
        <tbody key={grup.judul} role="rowgroup">
          <tr className="matriks__grup" role="row">
            <th colSpan={KOLOM.length + 1} scope="colgroup" role="columnheader">
              {grup.judul}
            </th>
          </tr>
          {grup.baris.map((b) => (
            <tr key={b.apa} role="row">
              <th className="matriks__apa" scope="row" role="rowheader">
                {b.apa}
              </th>
              {b.nilai.map((n, i) => (
                <Sel key={KOLOM[i].nama} nilai={n} kami={KOLOM[i].kami} kolom={KOLOM[i].pendek} />
              ))}
            </tr>
          ))}
        </tbody>
      ))}
    </table>
  );
}

export function Value() {
  return (
    <section className="value" id="nilai">
      <div className="section-head value__head">
        <h2>Yang gratis berhenti di rating. Yang bisa lebih, harganya kelas perusahaan.</h2>
        <p>
          Di Indonesia ada <b>4,40 juta unit usaha e-commerce</b>, mayoritas mikro, dan margin
          mereka sudah tergerus <b>15-20%</b> biaya platform sebelum satu rupiah masuk kantong.
          Ketika keluhan yang sama berulang tanpa terdeteksi, kerugiannya dua kali: penjualan
          yang hilang, dan biaya iklan yang dibakar untuk mendatangkan pembeli ke masalah yang
          belum diperbaiki. Dan membalasnya ada harganya: penjual yang rutin membalas ulasan
          menerima lebih banyak ulasan dan rating yang lebih tinggi - terukur pada puluhan ribu
          ulasan (Proserpio &amp; Zervas, <i>Marketing Science</i> 2017) - tetapi membalas satu
          per satu adalah pekerjaan yang tidak sempat dikerjakan siapa pun.
        </p>
      </div>

      <div className="banding">
        <div className="banding__judul">
          <h3>Di antara yang gratis</h3>
          <p>Ketiganya tidak memungut biaya. Yang membedakan bukan harganya.</p>
        </div>
        <div className="banding__bingkai">
          <Matriks />
        </div>

        {/* Celahnya diberi barisnya sendiri, bukan sekadar jarak kosong: ruang kosong terbaca
            sebagai jeda tata letak, sedangkan yang harus terbaca di sini adalah ketiadaan. */}
        <div className="celah">
          <b>Di antara keduanya, tidak ada apa pun</b>
          <p>
            Tidak ada perkakas yang membaca “bahannya oke sih cuma kekecilan bgt, sizechartnya
            ngaco” pada anggaran penjual mikro. Yang berbayar semuanya dirancang untuk ulasan
            berbahasa Inggris.
          </p>
        </div>

        <div className="banding__judul">
          <h3>Di antara yang berbayar</h3>
          <p>
            Harga masuk termurah tiap perkakas, per bulan
            <span> · kurs Rp16.000/USD</span>
          </p>
        </div>
        <ul className="tarif">
          {TARIF.map((t) => (
            <li className="tarif__kartu" key={t.nama}>
              <p className="tarif__nama">{t.nama}</p>
              <p className="tarif__angka">
                <b>Rp{juta(t.rupiah / 1_000_000)}</b>
                <span>
                  juta<i>/bln</i>
                </span>
              </p>
              <p className="tarif__asli">{t.asli}</p>
              <p className="tarif__batas">{t.batas}</p>
              {t.ikat && <p className="tarif__ikat">{t.ikat}</p>}
            </li>
          ))}
        </ul>
      </div>

      {/* Pertanyaan yang selalu muncul setelah kata "gratis" adalah "lalu apa tangkapannya".
          Menjawabnya dengan hitungan terbuka lebih meyakinkan daripada menjanjikan selamanya. */}
      <div className="ongkos">
        <h3>Kenapa gratisnya bisa bertahan</h3>
        <p className="ongkos__lead">
          Bukan karena dibiayai investor. Seluruh model berjalan di mesin yang menjalankan
          aplikasi ini, bukan lewat API berbayar per ulasan, jadi ongkosnya tidak naik bersama
          jumlah pemakaian.
        </p>

        <ol className="ongkos__hitung">
          {HITUNGAN.map((h) => (
            <li key={h.nilai} className={h.hasil ? "ongkos__hasil" : ""}>
              <b>{h.nilai}</b>
              <span>{h.ket}</span>
            </li>
          ))}
        </ol>

        <p className="ongkos__nota">
          Angka 88 detik itu terukur. Sisanya turunan dengan asumsi yang ditulis terbuka -
          hitungan lengkapnya, termasuk enam hal yang belum divalidasi, ada di berkas
          BUSINESS_VALUE di repositori.
        </p>
      </div>
    </section>
  );
}
