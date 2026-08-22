/** Bagian tengah halaman pemasaran: pita marketplace, cara kerja, dan tiga fitur inti. */

/** Teks referensi Stitch berbunyi "Terhubung dengan ulasan dari semua marketplace besar" -
 *  itu menjanjikan integrasi langsung yang TIDAK dimiliki versi ini, jadi kalimatnya diganti
 *  menjadi jalur yang benar-benar didukung: berkas ekspor dan tangkapan layar. */
const MARKETPLACES = ["Tokopedia", "Shopee", "TikTok Shop", "Lazada", "Bukalapak", "Google Reviews"];

export function MarketplaceBand() {
  // Daftar dirender dua kali supaya pita bisa bergulir tanpa celah: salinan kedua masuk saat
  // yang pertama keluar. Salinan itu disembunyikan dari pembaca layar - isinya sama persis.
  return (
    <div className="band">
      <div className="band-inner">
        <span className="lbl">
          Bekerja dari berkas ekspor maupun tangkapan layar ulasan marketplace besar
        </span>
        <div className="band-rail" aria-label="Tokopedia, Shopee, TikTok Shop, Lazada, Bukalapak, Google Reviews">
          <div className="band-logos">
            {MARKETPLACES.map((m) => (
              <b key={m}>{m}</b>
            ))}
            {MARKETPLACES.map((m) => (
              <b key={`${m}-2`} aria-hidden="true">
                {m}
              </b>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

const STEPS = [
  [
    "01",
    "Masukkan ulasan Anda",
    "Tempel satu ulasan per baris, unggah berkas CSV/JSON hasil ekspor, atau lampirkan tangkapan layar halaman ulasan - teksnya dibaca otomatis dan tetap bisa Anda perbaiki.",
  ],
  [
    "02",
    "Sistem membacanya",
    "Setiap ulasan dipecah per aspek (ukuran, kemasan, pengiriman, pelayanan), lalu dinilai sentimen dan tingkat keluhannya.",
  ],
  [
    "03",
    "Anda dapat daftar prioritas",
    "Hal yang paling perlu dikerjakan lebih dulu, masing-masing dengan kutipan asli pelanggan sebagai buktinya.",
  ],
];

export function HowItWorks() {
  return (
    <section className="features" id="cara-kerja">
      <div className="section-head">
        <h2>
          Tiga langkah, <span className="soft">satu sore</span>
        </h2>
        <p>
          Tidak ada pemasangan dan tidak ada akun yang perlu dihubungkan. Data Anda hanya diproses
          selama sesi ini dan tidak disimpan permanen.
        </p>
      </div>
      <div className="fgrid">
        {STEPS.map(([n, title, body]) => (
          <article className="fitem" key={n}>
            <span className="step-no">Langkah {n}</span>
            <h3>{title}</h3>
            <p>{body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

export function Features() {
  return (
    <section className="features" id="fitur">
      <h2>
        Setiap ulasan, <span className="soft">jadi langkah nyata</span>
      </h2>
      <p>
        Teks dan rating dari semua kanal terkumpul di satu tempat, lalu dikelompokkan per masalah,
        diurutkan berdasarkan dampaknya, dan dilengkapi rekomendasi yang harus dibenahi lebih dulu.
      </p>

      <div className="fgrid">
        <article className="fitem">
          <div className="fasset" aria-hidden="true">
            <div className="fa1-back">
              <div className="ln" />
              <div className="ln" />
              <div className="ln" />
            </div>
            <div className="fa1-front">
              <div className="fa1-photo" />
              <div className="fa1-text">
                <div className="ln" />
                <div className="ln" />
                <span className="mini-tag">
                  <i />
                  Ukuran
                </span>
              </div>
            </div>
          </div>
          <h3>Mengerti Bahasa Pelanggan Sehari-hari</h3>
          <p>
            Bahasa gaul, singkatan, sampai ejaan bebas, semuanya tetap terbaca. Tidak ada ulasan
            yang terlewat hanya karena sulit dipahami.
          </p>
        </article>

        <article className="fitem">
          <div className="fasset" aria-hidden="true">
            <div className="fa2-panel">
              {[
                ["1", "Ukuran tidak sesuai", "82%"],
                ["2", "Kemasan rusak", "56%"],
                ["3", "Respons lambat", "33%"],
              ].map(([n, label, w]) => (
                <div className="fa2-row" key={n}>
                  <span className="fa2-badge">{n}</span>
                  <div className="fa2-body">
                    <div className="fa2-label">{label}</div>
                    <div className="fa2-track">
                      <div className="fa2-fill" style={{ width: w }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <h3>Mengurutkan yang Paling Penting</h3>
          <p>
            Masalah diurutkan berdasarkan seberapa sering muncul, seberapa besar dampaknya, dan
            seberapa baru terjadinya, jadi urutan kerjanya bukan tebak-tebakan.
          </p>
        </article>

        <article className="fitem">
          <div className="fasset" aria-hidden="true">
            <div className="fa3-rec">
              <span className="fa3-check">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M5 12.5l4.5 4.5L19 7.5"
                    stroke="#1E4FCB"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              Perbarui size chart &amp; foto ukuran asli
            </div>
            <div className="fa3-connector" />
            <div className="fa3-quote">
              <span className="qm">”</span>
              <p>"Ukurannya beda jauh sama yang di foto, kekecilan banget…"</p>
              <span className="mini-tag" style={{ marginTop: 7 }}>
                <i />
                Ukuran tidak sesuai
              </span>
            </div>
          </div>
          <h3>Menyertakan Buktinya</h3>
          <p>
            Setiap rekomendasi datang lengkap dengan kutipan asli pelanggan di baliknya, jadi Anda
            bisa ambil tindakan dengan yakin atau menolaknya dengan alasan yang jelas.
          </p>
        </article>
      </div>
    </section>
  );
}
