/** Laporan lengkap - satu gulungan, bukan tab bertumpuk.
 *
 * Sebelumnya hasil dipecah ke empat tab (Hasil, Detail, Tanya Jawab, Roadmap), dan bagian yang
 * ditambahkan sekarang akan menjadikannya tujuh. Tab yang berjumlah tujuh berhenti menjadi
 * navigasi: pengguna tidak lagi memilih, ia mencari - dan mencari di antara tujuh label
 * pendek lebih lambat daripada menggulir satu halaman yang tersusun.
 *
 * Jadi laporan menjadi satu permukaan yang digulir, dengan rel bagian yang menempel di
 * sampingnya. Tiga hal yang tersisa sebagai tab adalah tiga MODE yang berbeda, bukan tiga
 * bagian dari satu laporan: membaca laporan, bertanya kepadanya, dan melihat apa yang belum
 * dibangun.
 *
 * Bagian yang tidak punya data TIDAK dirender, dan namanya juga hilang dari rel. Kerangka
 * kosong berlabel "Per produk" pada berkas yang tidak punya kolom produk terbaca sebagai
 * kerusakan, bukan sebagai ketiadaan - dan rel yang menjanjikan bagian yang tidak ada saat
 * ditekan lebih buruk lagi.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { WARNING_TEXT } from "../../lib/format.js";
import {
  ActionCard,
  BenchmarkCard,
  ContradictionCard,
  DataQualityCard,
  OpportunityCard,
  VisualFindings,
} from "../insight.jsx";
import { ArchivePanel } from "./ArchivePanel.jsx";
import { SummaryHead } from "../report/Figures.jsx";
import { AspectSections } from "../report/Aspects.jsx";
import { PeriodChart } from "../report/Periods.jsx";
import { ProductTable } from "../report/Products.jsx";
import { RatingBands } from "../report/Ratings.jsx";

/** Satu bagian laporan. `id` dipakai rel sebagai sasaran lompatan.
 *
 * `wadah` menentukan apakah ISI bagian dibungkus `.panel` - primitif kontainer yang sudah
 * dipakai di seluruh dashboard (kaca `--glass`, tepi `--glass-edge`, `--r-lg`). Tidak semua
 * bagian boleh mendapatkannya, dan itu justru yang membuat halamannya konsisten:
 *
 *   wadah       untuk isi yang polos - deretan angka, daftar aspek, tabel, grafik. Tanpa ini
 *               mereka melayang langsung di atas kanvas sementara tetangganya berada di dalam
 *               panel, dan halaman terbaca setengah jadi.
 *   tanpa wadah untuk isi yang SUDAH berupa kartu (kartu aksi, kartu peluang) atau yang sudah
 *               membawa panelnya sendiri (benchmark, kualitas data). Membungkusnya lagi
 *               menghasilkan kartu di dalam kartu, yang selalu keliru: dua tepi bersarang
 *               membuat keduanya berhenti menandai batas apa pun.
 *
 * `tabIndex={-1}` supaya rel dapat memindahkan fokus ke sini setelah menggulir. Tanpa itu
 * fokus tertinggal di tombol rel, dan Tab berikutnya membawa pengguna papan ketik ke butir rel
 * sebelah alih-alih ke isi bagian yang baru saja dituju.
 */
function Bagian({ id, judul, ket, wadah = false, children }) {
  return (
    <section className="lap__bagian" id={id} aria-labelledby={`${id}-judul`} tabIndex={-1}>
      <div className="lap__kepala">
        <h3 id={`${id}-judul`}>{judul}</h3>
        {ket && <p className="meta">{ket}</p>}
      </div>
      {wadah ? <div className="panel lap__wadah">{children}</div> : children}
    </section>
  );
}

/** Rel bagian yang menempel.
 *
 * Butirnya `<button>`, BUKAN `<a href="#lap-aspek">`, dan itu bukan pilihan gaya melainkan
 * keharusan: aplikasi ini memakai rute berbasis hash (`#/` untuk halaman pemasaran, `#/analisis`
 * untuk dashboard - lihat `lib/hooks.js`). Tautan jangkar menulis ulang hash menjadi
 * `#lap-aspek`, dan `routeFromHash()` membaca apa pun yang tidak diawali `#/analisis` sebagai
 * halaman pemasaran. Jadi menekan butir rel tidak menggulir ke bagiannya melainkan MELEMPAR
 * pengguna keluar dari laporan yang baru saja ia tunggu satu menit untuk dihitung - dan hasil
 * itu tidak disimpan di mana pun untuk dipulihkan.
 *
 * Hash tidak disentuh sama sekali di sini. Menggulirnya dikerjakan sendiri, dan fokus dipindah
 * ke bagian tujuan supaya pengguna papan ketik ikut berpindah - tanpa itu, tombol rel tetap
 * memegang fokus dan Tab berikutnya kembali ke butir rel di sebelahnya, bukan ke isi bagian
 * yang baru saja dituju.
 *
 * Menyorot bagian yang sedang terbaca dengan IntersectionObserver, bukan dengan menghitung
 * `scrollY` pada setiap peristiwa gulir - penghitungan itu berjalan di utas utama pada tiap
 * frame gulir, dan di ponsel kelas menengah yang menjadi sasaran produk ini biayanya terlihat.
 *
 * `rootMargin` atas -45% membuat bagian dianggap aktif saat kepalanya melewati kira-kira
 * pertengahan layar, bukan saat piksel pertamanya menyentuh tepi atas. Tanpa itu, sorotan
 * melompat ke bagian berikutnya sementara mata masih membaca bagian sebelumnya.
 */
function Rel({ bagian }) {
  const [aktif, setAktif] = useState(bagian[0]?.id);
  const daftar = useRef(null);

  useEffect(() => {
    const nodes = bagian
      .map(({ id }) => document.getElementById(id))
      .filter(Boolean);
    if (!nodes.length) return undefined;

    const pengamat = new IntersectionObserver(
      (entries) => {
        const terlihat = entries.filter((e) => e.isIntersecting);
        if (terlihat.length) setAktif(terlihat[0].target.id);
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 }
    );
    nodes.forEach((n) => pengamat.observe(n));
    return () => pengamat.disconnect();
  }, [bagian]);

  // Di layar sempit relnya menggulir menyamping; butir aktif ditarik ke dalam pandangan
  // supaya ia tidak tertinggal di luar layar saat halaman digulir.
  //
  // Digulir dengan menyetel `scrollLeft` pada relnya sendiri, BUKAN dengan `scrollIntoView`.
  // Bukan selera: `scrollIntoView` menggulir leluhur pertama yang bisa digulir pada sumbu yang
  // diminta, dan di layar lebar relnya tersusun tegak sehingga tidak ada satu pun - yang
  // ditemukan berikutnya adalah dokumen. Akibatnya seluruh halaman bergeser ~22px ke samping
  // lalu terkunci di sana, karena `html { overflow-x: hidden }` menghapus bilah gulir yang
  // bisa dipakai menggeser balik. Menjaganya dengan memeriksa lebar pun tidak cukup: pada
  // render pertama relnya masih bertata letak sempit, jadi pemeriksaannya lolos sekali - satu
  // kali sudah cukup. Menyetel `scrollLeft` tidak punya jalan keluar ke dokumen sama sekali.
  useEffect(() => {
    const ol = daftar.current;
    if (!ol || ol.scrollWidth <= ol.clientWidth) return;
    const butir = ol.querySelector('[aria-current="true"]');
    if (!butir) return;
    const tengah = butir.offsetLeft - (ol.clientWidth - butir.offsetWidth) / 2;
    ol.scrollTo({ left: Math.max(0, tengah), behavior: "smooth" });
  }, [aktif]);

  function lompat(id) {
    const target = document.getElementById(id);
    if (!target) return;
    target.scrollIntoView({ block: "start", behavior: "smooth" });
    // `preventScroll` supaya pemindahan fokus tidak melompati animasi gulir yang baru saja
    // dimulai; gulirnya sudah diurus baris di atas.
    target.focus({ preventScroll: true });
    setAktif(id);
  }

  return (
    <nav className="lap__rel" aria-label="Bagian laporan">
      <ol ref={daftar}>
        {bagian.map(({ id, judul }) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => lompat(id)}
              aria-current={aktif === id ? "true" : undefined}
            >
              {judul}
            </button>
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function ReportPanel({ result, category, rentang, decisions, onDecide, onOpenEvidence }) {
  const punyaProduk = (result.products ?? []).length > 0;
  const punyaRiwayat = Boolean(result.period_history);
  const punyaBintang = Boolean(result.ratings);
  const peluang = result.opportunities ?? [];
  // Kosong selama jalur visual belum lolos gerbangnya. Bagiannya ikut hilang dari rel -
  // bagian berlabel "foto membantah teksnya" yang selalu kosong terbaca sebagai
  // kerusakan, bukan sebagai ketiadaan.
  const kontra = result.contradictions ?? [];
  const benchmark = result.benchmark_by_category?.[category] ?? result.benchmark ?? [];

  // Rel dan isi digambar dari SATU daftar. Dua daftar terpisah adalah cara paling pasti
  // membuat rel menunjuk bagian yang sudah tidak dirender.
  //
  // Dimemo karena `Rel` memakainya sebagai dependensi efek yang memasang IntersectionObserver.
  // Larik yang dibangun ulang tiap render punya identitas baru tiap render, sehingga efeknya
  // membongkar lalu memasang kembali pengamatnya pada SETIAP render - termasuk render yang
  // dipicu pengamat itu sendiri saat menyorot bagian baru.
  const bagian = useMemo(
    () =>
      [
        { id: "lap-ringkas", judul: "Ringkasan", ada: true },
        { id: "lap-prioritas", judul: "Prioritas", ada: true },
        { id: "lap-aspek", judul: "Per aspek", ada: true },
        { id: "lap-produk", judul: "Per produk", ada: punyaProduk },
        { id: "lap-bintang", judul: "Sebaran bintang", ada: punyaBintang },
        { id: "lap-riwayat", judul: "Riwayat", ada: punyaRiwayat },
        { id: "lap-kontra", judul: "Foto vs teks", ada: kontra.length > 0 },
        { id: "lap-peluang", judul: "Peluang", ada: peluang.length > 0 },
        { id: "lap-banding", judul: "Benchmark", ada: benchmark.length > 0 },
        { id: "lap-mutu", judul: "Kualitas data", ada: Boolean(result.data_quality) },
        { id: "lap-arsip", judul: "Simpan & bandingkan", ada: true },
      ].filter((b) => b.ada),
    [
      punyaProduk, punyaBintang, punyaRiwayat, kontra.length, peluang.length,
      benchmark.length, result.data_quality,
    ]
  );

  return (
    <div className="lap">
      <Rel bagian={bagian} />

      <div className="lap__isi">
        <Bagian id="lap-ringkas" judul="Ringkasan" wadah>
          <SummaryHead result={result} category={category} />
          {result.warnings?.map((w) => (
            <div key={w} className="banner-grey">
              {WARNING_TEXT[w] ?? w}
            </div>
          ))}
        </Bagian>

        <Bagian
          id="lap-prioritas"
          judul="Yang perlu dikerjakan lebih dulu"
          ket="Terurut menurut skor prioritas - dihitung dari frekuensi, keparahan, dan selisih terhadap kategori sejenis. Bukan menurut yang paling mudah dikerjakan."
        >
          {result.top_actions.length > 0 ? (
            result.top_actions.map((card, i) => (
              <ActionCard
                key={card.action_id}
                index={i}
                card={card}
                decision={decisions[card.action_id]}
                onDecide={onDecide}
                onOpenEvidence={onOpenEvidence}
              />
            ))
          ) : (
            <div className="banner-grey">
              Tidak ada keluhan yang cukup sering muncul untuk dijadikan prioritas. Itu kabar
              baik, tetapi periksa juga apakah data yang Anda masukkan sudah mewakili seluruh
              ulasan.
            </div>
          )}
        </Bagian>

        <Bagian
          id="lap-aspek"
          judul="Per aspek"
          wadah
          ket="Seluruh aspek yang dikenali sistem, termasuk yang tidak disebut satu ulasan pun. Tekan satu baris untuk melihat dasar angkanya."
        >
          <AspectSections result={result} category={category} />
        </Bagian>

        {punyaProduk && (
          <Bagian
            id="lap-produk"
            judul="Per produk"
            wadah
            ket="Dibaca dari kolom produk pada berkas yang Anda unggah. Tekan judul kolom untuk mengurutkan."
          >
            <ProductTable products={result.products} />
          </Bagian>
        )}

        {punyaBintang && (
          <Bagian
            id="lap-bintang"
            judul="Sebaran bintang"
            wadah
            ket="Bukan sekadar berapa banyak per bintang - juga keluhan apa yang ada di dalam tiap pita."
          >
            <RatingBands ratings={result.ratings} />
          </Bagian>
        )}

        {punyaRiwayat && (
          <Bagian
            id="lap-riwayat"
            judul="Riwayat antar periode"
            wadah
            ket="Dihitung dari kolom tanggal pada berkas Anda sendiri."
          >
            <PeriodChart history={result.period_history} />
          </Bagian>
        )}

        {kontra.length > 0 && (
          <Bagian
            id="lap-kontra"
            judul="Ulasan yang foto dan teksnya berlawanan"
            ket="Ditandai untuk Anda periksa sendiri. Sistem sengaja tidak memutuskan mana yang benar."
          >
            {kontra.map((f) => (
              <ContradictionCard key={f.review_id} finding={f} />
            ))}
          </Bagian>
        )}

        {peluang.length > 0 && (
          <Bagian
            id="lap-peluang"
            judul="Peluang yang ditemukan"
            ket="Aspek yang justru dipuji pembeli. Bahan untuk promosi - sistem sengaja tidak menuliskan materi iklannya."
          >
            {peluang.map((o) => (
              <OpportunityCard key={o.aspect} opportunity={o} />
            ))}
          </Bagian>
        )}

        {benchmark.length > 0 && (
          <Bagian id="lap-banding" judul="Dibanding kategori sejenis">
            <BenchmarkCard rows={benchmark} />
          </Bagian>
        )}

        {result.data_quality && (
          <Bagian
            id="lap-mutu"
            judul="Kualitas data"
            ket="Seberapa jauh hasil di atas layak dipercaya, dilihat dari data yang masuk."
          >
            <DataQualityCard quality={result.data_quality} />
            <VisualFindings findings={result.visual_findings} />

            {/* Versi model dan mode dulu satu baris `.meta` telanjang di bawah panel, satu-
                satunya isi di seluruh laporan yang mengambang langsung di atas kanvas. Ia
                dapat panelnya sendiri, bukan dijejalkan ke dalam panel kualitas data: yang
                satu menilai data yang MASUK, yang satu menyebut perkakas yang mengolahnya. */}
            <section className="panel">
              <div className="panel-title">Model yang dipakai</div>
              <p className="meta">
                Teks: <b>{result.model_versions?.text ?? "tidak diketahui"}</b> · penelusuran
                bukti: <b>{result.model_versions?.embedding ?? "tidak aktif"}</b> · mode{" "}
                <b>{result.mode}</b>
              </p>
            </section>
          </Bagian>
        )}

        {/* Bagian terakhir, dan tempatnya memang di akhir: ia bukan temuan melainkan apa yang
            dilakukan SESUDAH membaca temuan. Menaruhnya di atas akan menawarkan penyimpanan
            sebelum ada yang layak disimpan. */}
        <Bagian
          id="lap-arsip"
          judul="Simpan & bandingkan"
          ket="Hasil ini hilang saat halaman ditutup - kami tidak menyimpan apa pun. Unduh arsipnya untuk dibandingkan di sesi berikutnya."
        >
          <ArchivePanel result={result} rentang={rentang} />
        </Bagian>
      </div>
    </div>
  );
}
