/** Arsip analisis, perbandingan antar-periode, dan ekspor bagikan (L5).
 *
 * Bagian ini menjawab satu baris Roadmap yang selama ini tertahan - "riwayat antar-sesi" -
 * tanpa menyentuh larangan database, dengan membalik siapa yang menyimpan. Pengguna mengunduh
 * sekeping JSON berisi agregat, lalu mengunggahnya kembali bulan depan sebagai pembanding.
 *
 * Yang didapat bukan sekadar fitur yang setara. Ia lebih baik untuk produk ini: kalimat "kami
 * tidak menyimpan apa pun" berhenti menjadi keterbatasan yang harus dimaklumi dan menjadi
 * bentuk kepemilikan. Arsipnya ada di komputer pengguna, dan ia yang memutuskan kapan
 * dibandingkan - termasuk memutuskan untuk tidak pernah.
 */

import { useRef, useState } from "react";

import { api } from "../../api/client.js";
import { aspectLabel, pct } from "../../lib/format.js";
import { unduhJson, unduhRingkasanPng } from "../../lib/share.js";

/** Satu baris perubahan aspek.
 *
 * Selisih yang TIDAK berarti tetap ditampilkan, dan itu keputusan yang perlu dijelaskan:
 * menyembunyikannya akan membuat aspek yang benar-benar diam terlihat sama dengan aspek yang
 * tidak diukur. Yang dibedakan bukan ada-tidaknya baris, melainkan apakah angkanya boleh
 * dibaca sebagai perubahan - dan itu ditandai kata, bukan warna saja.
 */
function BarisDelta({ d }) {
  const arah = d.direction;
  const tanda = d.delta_pct > 0 ? "+" : "";
  return (
    <tr>
      <td>{aspectLabel(d.aspect)}</td>
      <td className="stat">{pct(d.before_pct)}</td>
      <td className="stat">{pct(d.after_pct)}</td>
      <td>
        {d.significant ? (
          <em className={arah === "membaik" ? "gap gap--baik" : "gap gap--buruk"}>
            {tanda}
            {pct(d.delta_pct)} {arah}
          </em>
        ) : (
          <em className="gap" title={`Margin selisih ±${pct(d.margin_of_error)}`}>
            {tanda}
            {pct(d.delta_pct)} · belum berarti
          </em>
        )}
      </td>
    </tr>
  );
}

function Perbandingan({ data }) {
  const berarti = data.deltas.filter((d) => d.significant);
  return (
    <>
      <div className={berarti.length ? "banner-blue" : "banner-grey"}>{data.headline}</div>

      {data.warnings.map((w) => (
        <div key={w} className="banner-grey">
          {w}
        </div>
      ))}

      <p className="meta" style={{ margin: "10px 0" }}>
        <span className="stat">{data.previous_total}</span> ulasan sebelumnya vs{" "}
        <span className="stat">{data.current_total}</span> sekarang. Persentase dihitung
        terhadap seluruh ulasan di masing-masing sesi, bukan terhadap sebutan aspeknya -
        penyebut yang berubah tidak dapat dibandingkan.
      </p>

      <div className="mtable-scroll">
        <table className="mtable">
          <thead>
            <tr>
              <th>Aspek</th>
              <th>Sebelumnya</th>
              <th>Sekarang</th>
              <th>Perubahan</th>
            </tr>
          </thead>
          <tbody>
            {data.deltas.map((d) => (
              <BarisDelta key={d.aspect} d={d} />
            ))}
          </tbody>
        </table>
      </div>

      <p className="meta" style={{ marginTop: 10 }}>
        "Belum berarti" bukan berarti tidak berubah - berarti selisihnya masih lebih kecil
        daripada margin kesalahan kedua sisi digabung, sehingga tidak dapat dibedakan dari
        kebetulan. Semakin banyak ulasan di kedua sesi, semakin sempit marginnya.
      </p>
    </>
  );
}

export function ArchivePanel({ result, rentang }) {
  const [sibuk, setSibuk] = useState(null); // "arsip" | "gambar" | "banding"
  const [error, setError] = useState(null);
  const [banding, setBanding] = useState(null);
  const berkas = useRef(null);

  async function unduhArsip() {
    setSibuk("arsip");
    setError(null);
    try {
      const arsip = await api.archive(result.analysis_id);
      unduhJson(arsip, `arsip-ulasin-${result.analysis_id}.json`);
    } catch (err) {
      setError(err.message);
    } finally {
      setSibuk(null);
    }
  }

  async function unduhGambar() {
    setSibuk("gambar");
    setError(null);
    try {
      await unduhRingkasanPng(result, rentang, aspectLabel);
    } catch (err) {
      setError(err.message);
    } finally {
      setSibuk(null);
    }
  }

  async function bandingkan(file) {
    if (!file) return;
    setSibuk("banding");
    setError(null);
    try {
      const isi = JSON.parse(await file.text());
      // Diperiksa di sini supaya berkas yang jelas keliru - CSV, hasil unduhan lain, JSON
      // apa pun - ditolak dengan kalimat yang menyebut apa yang salah, bukan dengan pesan
      // validasi Pydantic yang datang dari server.
      if (!isi || typeof isi !== "object" || !Array.isArray(isi.aspects)) {
        throw new Error(
          "Berkas ini bukan arsip analisis Ulasin. Pilih berkas .json yang Anda unduh dari " +
            "halaman hasil sesi sebelumnya."
        );
      }
      setBanding(await api.compare(result.analysis_id, isi));
    } catch (err) {
      setError(err.message);
      setBanding(null);
    } finally {
      setSibuk(null);
    }
  }

  return (
    <>
      {error && <div className="banner-error">{error}</div>}

      <div className="panel">
        <div className="panel-title">Simpan hasil ini</div>
        <p className="meta" style={{ marginBottom: 12 }}>
          Arsipnya berisi angka agregat saja - tidak ada teks ulasan, kutipan, maupun identitas
          pembeli di dalamnya. Simpan di komputer Anda; kami tidak menyimpan apa pun setelah
          halaman ini ditutup.
        </p>
        <div className="arsip__aksi">
          <button className="btn btn--outline" disabled={sibuk === "arsip"} onClick={unduhArsip}>
            {sibuk === "arsip" ? "Menyiapkan…" : "Unduh arsip analisis (.json)"}
          </button>
          <button className="btn btn--outline" disabled={sibuk === "gambar"} onClick={unduhGambar}>
            {sibuk === "gambar" ? "Menggambar…" : "Unduh ringkasan (.png)"}
          </button>
        </div>
        <p className="meta" style={{ marginTop: 10 }}>
          Gambar PNG dibuat untuk dibagikan ke grup WhatsApp. Isinya angka dan nama aspek saja.
        </p>
      </div>

      <div className="panel">
        <div className="panel-title">Bandingkan dengan sesi sebelumnya</div>
        <p className="meta" style={{ marginBottom: 12 }}>
          Unggah arsip yang Anda unduh bulan lalu untuk melihat apa yang berubah. Berkasnya
          dibaca lalu dibuang bersama jawabannya - tidak ada yang tersimpan di server.
        </p>
        <button
          className="btn btn--outline"
          disabled={sibuk === "banding"}
          onClick={() => berkas.current?.click()}
        >
          {sibuk === "banding" ? "Membandingkan…" : "Pilih arsip sebelumnya (.json)"}
        </button>
        <input
          ref={berkas}
          type="file"
          accept=".json,application/json"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0];
            e.target.value = ""; // supaya memilih berkas yang sama dua kali tetap memicu
            bandingkan(f);
          }}
        />

        {banding && (
          <div style={{ marginTop: 16 }}>
            <Perbandingan data={banding} />
          </div>
        )}
      </div>
    </>
  );
}
