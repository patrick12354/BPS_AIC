/** Dua alat yang menempel pada satu kartu aksi: draf balasan (S1) dan jejak perhitungan (S2).
 *
 * Keduanya tinggal di lembar bukti, bukan di badan kartu, dan itu keputusan tata letak yang
 * disengaja. Daftar prioritas dibaca dengan cara dipindai - mata turun dari kartu satu ke kartu
 * lima untuk memutuskan mana yang dikerjakan besok. Menaruh panel berisi belasan klausa di
 * dalam kartu akan mengubah daftar yang dapat dipindai dalam sepuluh detik menjadi dokumen
 * yang harus digulir. Kartu menyimpan pintunya; isinya menunggu di balik pintu itu.
 *
 * Keduanya juga dimuat SAAT DIBUKA, tidak ikut di payload analisis. Alasannya berbeda untuk
 * masing-masing: jejak besar dan jarang dibuka, draf balasan tidak selalu diinginkan dan tidak
 * ada gunanya disusun untuk kartu yang keputusannya "tolak".
 */

import { useEffect, useRef, useState } from "react";

import { api } from "../../api/client.js";
import { aspectLabel } from "../../lib/format.js";

/** Pemuat sederhana untuk kedua panel: satu permintaan, tiga keadaan.
 *
 * `analysisId` dan `actionId` menjadi dependensi supaya membuka kartu lain benar-benar
 * mengambil datanya sendiri - tanpa itu, panel kedua menampilkan jejak milik kartu pertama.
 */
function useCardData(fetcher, analysisId, actionId, aktif) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Fungsi pengambilnya ditulis sebagai arrow inline di pemanggil, jadi identitasnya berubah
  // tiap render. Disimpan di ref supaya efek di bawah tidak menembak ulang tiap render induk.
  const ambil = useRef(fetcher);
  ambil.current = fetcher;

  useEffect(() => {
    if (!aktif || !analysisId || !actionId) return undefined;
    let batal = false;
    setBusy(true);
    setError(null);
    ambil
      .current(analysisId, actionId)
      .then((hasil) => {
        if (!batal) setData(hasil);
      })
      .catch((err) => {
        if (!batal) setError(err.message);
      })
      .finally(() => {
        if (!batal) setBusy(false);
      });
    // Permintaan yang sudah terbang tidak dapat ditarik, tetapi hasilnya boleh diabaikan -
    // tanpa penanda ini, menutup lembar di tengah pemuatan menyetel state komponen yang sudah
    // dilepas.
    return () => {
      batal = true;
    };
  }, [aktif, analysisId, actionId]);

  return { data, busy, error };
}

// --------------------------------------------------------------------------------------
// S1 - draf balasan
// --------------------------------------------------------------------------------------

/** Satu draf, beserta ulasan yang dibalasnya.
 *
 * Tombol salin MATI sampai teksnya disentuh, dan itu bukan gesekan yang tidak perlu melainkan
 * inti dari fiturnya. Balasan penjual terbit atas nama toko, dibaca calon pembeli lain, dan
 * tidak dapat ditarik. Draf yang dapat disalin dalam satu klik akan disalin dalam satu klik -
 * termasuk kalimat "[keputusan Anda: ganti barang / refund]" yang tidak pernah dimaksudkan
 * ikut terkirim. Pola yang sama dipakai draf hasil OCR: setiap kali sistem menghasilkan teks
 * yang akan mewakili pengguna di luar sana, manusia menyentuhnya lebih dulu.
 */
function DraftItem({ draft, index }) {
  const [teks, setTeks] = useState(draft.draft);
  const [disunting, setDisunting] = useState(false);
  const [tersalin, setTersalin] = useState(false);

  async function salin() {
    try {
      await navigator.clipboard.writeText(teks);
      setTersalin(true);
      setTimeout(() => setTersalin(false), 2000);
    } catch {
      // Papan klip dapat ditolak peramban (izin, konteks tidak aman). Teksnya tetap ada di
      // kotak yang dapat diblok dan disalin sendiri, jadi tidak ada yang benar-benar hilang.
      setTersalin(false);
    }
  }

  return (
    <div className="draft">
      <div className="draft__head">
        <span className="draft__no">Balasan {index + 1}</span>
        <div className="draft__meta">
          {draft.rating && <span className="draft__conf">{draft.rating}/5</span>}
        </div>
      </div>

      {/* Ulasan yang dibalas ikut ditampilkan. Menyunting balasan tanpa melihat keluhannya
          sama dengan menulis surat tanpa membaca surat yang dijawab. */}
      <blockquote className="equote equote--rapat">
        <p>{draft.quote}</p>
      </blockquote>

      <label className="sr-only" htmlFor={`balasan-${draft.review_id}`}>
        Draf balasan untuk ulasan {index + 1}
      </label>
      <textarea
        id={`balasan-${draft.review_id}`}
        className="draft__text"
        value={teks}
        rows={Math.min(8, Math.max(3, Math.ceil(teks.length / 58)))}
        onChange={(e) => {
          setTeks(e.target.value);
          setDisunting(true);
        }}
      />

      {draft.decision_slots.length > 0 && (
        <p className="meta draft__slot">
          Ada bagian yang menunggu keputusan Anda: {draft.decision_slots.join(", ")}. Sistem
          tidak menuliskan janji ganti barang atau refund untuk Anda.
        </p>
      )}

      <div className="btn-row">
        <button className="btn-sm" disabled={!disunting} onClick={salin}>
          {tersalin ? "Tersalin ✓" : "Salin balasan"}
        </button>
      </div>
      {!disunting && (
        <p className="meta" style={{ marginTop: 6 }}>
          Sunting dulu teksnya - tombol salin aktif setelah Anda menyentuhnya.
        </p>
      )}
    </div>
  );
}

export function ReplyDrafts({ analysisId, card, aktif }) {
  const { data, busy, error } = useCardData(api.replyDrafts, analysisId, card.action_id, aktif);

  if (!aktif) return null;
  if (busy) return <p className="body">Menyusun draf balasan…</p>;
  if (error) return <div className="banner-error">{error}</div>;
  if (!data) return null;

  if (!data.drafts.length) {
    return (
      <div className="banner-grey">
        Kartu ini belum punya kutipan pendukung, jadi tidak ada ulasan tertentu yang dapat
        dibalas. Tanyakan aspeknya di tab Tanya Jawab untuk melihat ulasannya lebih dulu.
      </div>
    );
  }

  return (
    <>
      <p className="meta" style={{ marginBottom: 10 }}>
        {data.note}
      </p>
      {data.drafts.map((d, i) => (
        <DraftItem key={d.review_id} draft={d} index={i} />
      ))}
    </>
  );
}

// --------------------------------------------------------------------------------------
// S2 - jejak perhitungan
// --------------------------------------------------------------------------------------

const SENTIMEN_LABEL = { negatif: "keluhan", positif: "pujian", netral: "netral" };

/** Rantai penuh dari klausa mentah sampai skor prioritas.
 *
 * Empat langkah, dan urutannya adalah urutan perhitungannya sendiri: klausa apa yang terbaca,
 * bagaimana klausa itu menjadi angka agregat, bagaimana agregat menjadi komponen rumus, dan
 * bagaimana komponen menjadi skor. Pembaca yang curiga dapat berhenti di langkah mana pun.
 *
 * Tidak ada satu pun angka baru di sini - semuanya sudah dipakai kartu di atasnya. Itu justru
 * gunanya: yang ditunjukkan bukan perhitungan tandingan melainkan perhitungan YANG SAMA,
 * dibuka isinya.
 */
export function TracePanel({ analysisId, card, aktif }) {
  const { data, busy, error } = useCardData(api.trace, analysisId, card.action_id, aktif);

  if (!aktif) return null;
  if (busy) return <p className="body">Membuka jejak perhitungan…</p>;
  if (error) return <div className="banner-error">{error}</div>;
  if (!data) return null;

  const agg = data.aggregate;

  return (
    <div className="jejak">
      <ol className="jejak__langkah">
        <li>
          <h5>1 · Klausa yang terbaca model</h5>
          <p className="meta">
            Klasifikasi berjalan per klausa, bukan per ulasan. Inilah potongan kalimat yang
            benar-benar memicu aspek <b>{aspectLabel(data.aspect)}</b>, apa adanya.
          </p>
          <ul className="jejak__klausa">
            {data.clauses.map((c, i) => (
              <li key={`${c.review_id}-${i}`}>
                <span className={`jejak__tanda jejak__tanda--${c.sentiment}`}>
                  {SENTIMEN_LABEL[c.sentiment] ?? c.sentiment}
                </span>
                <span className="jejak__teks">{c.clause}</span>
                <span className="meta">
                  {c.review_id} · keparahan {c.severity}
                </span>
              </li>
            ))}
          </ul>
        </li>

        <li>
          <h5>2 · Dijumlahkan menjadi agregat</h5>
          <p className="body">
            <span className="stat">{agg.total_mentions}</span> sebutan ·{" "}
            <span className="stat">{agg.negative_count}</span> berisi keluhan ·{" "}
            <span className="stat">{agg.positive_count}</span> positif · tren{" "}
            <b>{agg.trend.replace("_", " ")}</b> · keparahan tipikal{" "}
            <b>{agg.dominant_severity}</b>
          </p>
        </li>

        <li>
          <h5>3 · Komponen rumus prioritas</h5>
          <code className="jejak__rumus">{data.formula}</code>
          <table className="mtable jejak__tabel">
            <thead>
              <tr>
                <th>Komponen</th>
                <th>Nilai</th>
                <th>Dari mana</th>
              </tr>
            </thead>
            <tbody>
              {data.factors.map((f) => (
                <tr key={f.key}>
                  <td>
                    {f.label}
                    <em className="jejak__peran">{f.role}</em>
                  </td>
                  <td className="stat">{f.value}</td>
                  <td className="meta">{f.explanation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </li>

        <li>
          <h5>4 · Menjadi skor kartu</h5>
          <p className="body">
            <span className="stat">{data.core}</span> (pengali inti) ×{" "}
            <span className="stat">{data.modifier}</span> (modifier) × 100 ={" "}
            <span className="stat">{data.score}</span>
          </p>
          <p className="meta">
            Angka terakhir itulah skor prioritas yang menentukan urutan kartu ini di laporan.
          </p>
        </li>
      </ol>

      {data.citations.length > 0 && (
        <div className="jejak__kutipan">
          <h5>Kutipan yang dipilih, beserta skor relevansinya</h5>
          <ul className="meta note-list">
            {data.citations.map((c) => (
              <li key={c.citation_id}>
                <span className="stat">{c.relevance_score}</span> · {c.review_id}
                {c.rating ? ` · ${c.rating}/5` : ""}
              </li>
            ))}
          </ul>
          <p className="meta">
            Dipilih dengan kemiripan vektor terhadap aspeknya, disaring agar hanya ulasan yang
            benar-benar memuat keluhan pada aspek ini yang lolos.
          </p>
        </div>
      )}

      {data.notes.map((n) => (
        <div key={n} className="banner-grey" style={{ marginTop: 10 }}>
          {n}
        </div>
      ))}

      <p className="meta" style={{ marginTop: 10 }}>
        Seluruh angka di atas dihitung kode deterministik, bukan model bahasa. Jalur yang sama
        dapat diambil lewat API: <code>POST /api/v1/analyze?trace=1</code>.
      </p>
    </div>
  );
}
