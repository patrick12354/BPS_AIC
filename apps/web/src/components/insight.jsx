/** Primitif penampil hasil - dipakai bersama oleh tab Hasil, Detail, dan Tanya Jawab.
 *
 * Dua aturan yang mengikat di seluruh berkas ini:
 * 1. Angka hasil hitungan selalu memakai kelas `.stat` - biru tebal. Itu yang membedakan
 *    fakta terhitung dari narasi yang disusun sistem.
 * 2. Warna tidak pernah menjadi satu-satunya penanda; setiap badge urgensi memuat teksnya.
 */

import { useEffect, useRef, useState } from "react";
import { useOverflowX } from "../lib/hooks.js";
import { QUALITY_LABEL, URGENCY_LABEL, VISUAL_LABEL, aspectLabel, pct } from "../lib/format.js";
import { ReplyDrafts, TracePanel } from "./dashboard/CardTools.jsx";

/** Menyisipkan angka dalam kalimat dengan gaya angka terhitung. */
export function Narrative({ text, className = "body" }) {
  const parts = String(text ?? "").split(/(\d+(?:[.,]\d+)?%?)/g);
  return (
    <p className={className}>
      {parts.map((part, i) =>
        /^\d/.test(part) ? (
          <span key={i} className="stat">
            {part}
          </span>
        ) : (
          part
        )
      )}
    </p>
  );
}

export function EvidenceStrip({ citation, tag }) {
  // Rating dan tanggal menentukan seberapa berat sebuah kutipan patut ditimbang; tanpa
  // keduanya semua kutipan terlihat sama pentingnya.
  const meta = [
    citation.review_id,
    citation.rating ? `${citation.rating}/5` : null,
    citation.timestamp ? String(citation.timestamp).slice(0, 10) : null,
    citation.relevance_score != null ? `relevansi ${citation.relevance_score}` : null,
  ].filter(Boolean);

  return (
    <blockquote className="equote">
      <span className="qm" aria-hidden="true">
        ”
      </span>
      <p>{citation.quote}</p>
      <div className="meta">{meta.join(" · ")}</div>
      {tag && <span className="tag">{tag}</span>}
    </blockquote>
  );
}

const DECISIONS = [
  ["accepted", "Terima"],
  ["rejected", "Tolak"],
  ["saved", "Simpan dulu"],
];

export function DecisionRow({ actionId, decision, onDecide }) {
  return (
    <div className="btn-row">
      {DECISIONS.map(([value, label]) => (
        <button
          key={value}
          className="btn-sm"
          aria-pressed={decision === value}
          onClick={() => onDecide(actionId, decision === value ? null : value)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

/** Kartu aksi.
 *
 * Tingkat urgensi ditandai TIGA kali, sengaja: rona latar kartu (terbaca saat memindai), badge
 * bertulisan (terbaca saat berhenti), dan nomor urut (terbaca bahkan tanpa warna sama sekali).
 * Tidak ada satu pun penanda yang berdiri sendiri.
 */
export function ActionCard({ card, decision, onDecide, onOpenEvidence, index = 0 }) {
  return (
    <article
      className={`acard acard--${card.urgency} reveal`}
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <span className="acard__rank" aria-hidden="true">
        {index + 1}
      </span>
      <span className={`badge badge--${card.urgency}`}>
        {URGENCY_LABEL[card.urgency] ?? card.urgency}
      </span>
      <h4>{card.title}</h4>
      <Narrative text={card.recommended_action} className="" />

      {card.evidence_quotes.slice(0, 1).map((c) => (
        <EvidenceStrip key={c.citation_id} citation={c} />
      ))}

      {/* Tiga pintu ke lembar yang sama, masing-masing membuka bagiannya sendiri. Satu pintu
          berlabel "Lihat detail" akan menyembunyikan dua fitur di baliknya; tiga label yang
          menyebut isinya membuat keduanya benar-benar ditemukan. */}
      <div className="acard__pintu">
        {card.evidence_quotes.length > 0 && (
          <button className="link-more" onClick={() => onOpenEvidence(card, "bukti")}>
            Lihat semua bukti ({card.evidence_quotes.length}) →
          </button>
        )}
        {card.evidence_quotes.length > 0 && (
          <button className="link-more" onClick={() => onOpenEvidence(card, "balasan")}>
            Buat draf balasan →
          </button>
        )}
        <button className="link-more" onClick={() => onOpenEvidence(card, "jejak")}>
          Bagaimana angka ini dihitung? →
        </button>
      </div>

      <DecisionRow actionId={card.action_id} decision={decision} onDecide={onDecide} />
      {decision && (
        <p className="meta" style={{ marginTop: 10 }}>
          Keputusan Anda tersimpan untuk sesi ini. Sistem tidak menjalankan apa pun sendiri.
        </p>
      )}
    </article>
  );
}

export function DataQualityCard({ quality }) {
  if (!quality) return null;
  return (
    <section className="panel quality">
      <div className="panel-title">Skor kualitas data</div>
      <p className="quality__score">
        <span className="num-hero">{quality.score}</span>
        <span className="meta"> / 100</span>
      </p>
      <p className="meta">
        Kualitas data Anda: <strong>{QUALITY_LABEL[quality.level] ?? quality.level}</strong> ·{" "}
        <span className="stat">{quality.used}</span>/
        <span className="stat">{quality.total_uploaded}</span> baris dianalisis ·{" "}
        <span className="stat">{quality.with_rating}</span> punya rating ·{" "}
        <span className="stat">{quality.with_timestamp}</span> punya tanggal
      </p>
      {quality.notes?.length > 0 && (
        <ul className="meta note-list">
          {quality.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** Perbandingan terhadap baseline kategori.
 *
 * Kolom "Selisih" HILANG - bukan dikosongkan, bukan diberi tanda tanya - saat sisi tokonya
 * masih terlalu tipis untuk dibandingkan. Alasannya bukan kehati-hatian umum melainkan
 * aritmetika yang bisa diperiksa: pada 5 ulasan, proporsi apa pun membawa margin kesalahan
 * sekitar +-40 poin persentase, sehingga "selisih +12 poin" dan "selisih -12 poin" adalah
 * pembacaan yang sama sahnya atas data yang sama. Menampilkan salah satunya sebagai temuan
 * berarti memilih satu dari dua kesimpulan berlawanan dengan cara melempar koin, lalu
 * mencetaknya dengan gaya angka terhitung.
 *
 * Angka toko dan angka baseline tetap ditampilkan apa adanya. Yang ditahan hanya KLAIM
 * perbandingannya, karena itu satu-satunya bagian yang tidak didukung datanya.
 */
export function BenchmarkCard({ rows }) {
  const [scroll, fits] = useOverflowX();
  if (!rows?.length) return null;

  // Ambang berlaku per sesi, bukan per baris: penyebutnya jumlah ulasan yang sama untuk
  // seluruh aspek. Diambil dari baris pertama supaya tabelnya tidak setengah berkolom.
  const awal = Boolean(rows[0].preliminary);

  return (
    <section className="panel">
      <div className="panel-title">Benchmark kategori</div>
      <p className="meta" style={{ marginBottom: 10 }}>
        Dibandingkan terhadap rata-rata kategori dari data publik. Bukan data toko pesaing, dan
        bersifat historis, bukan pemantauan langsung.
      </p>

      {awal && (
        <div className="banner-grey" style={{ marginTop: 0 }}>
          <b>Indikasi awal.</b> Data Anda baru{" "}
          <span className="stat">{rows[0].store_sample_size}</span> ulasan, sehingga angka sisi
          toko sendiri masih bermargin ±
          <span className="stat">{pct(rows[0].store_margin_of_error)}</span>. Selisih terhadap
          rata-rata kategori belum ditampilkan karena pada rentang selebar itu ia belum dapat
          dibedakan dari nol. Kumpulkan sekitar 30 ulasan untuk melihatnya.
        </div>
      )}

      <div className={`mtable-scroll ${fits ? "mtable-scroll--fit" : ""}`} ref={scroll}>
        <table className="mtable">
          <thead>
            <tr>
              <th>Aspek</th>
              <th>Toko Anda</th>
              <th>Rata-rata</th>
              {!awal && <th>Selisih</th>}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 5).map((r) => (
              <tr key={r.aspect}>
                <td>{aspectLabel(r.aspect)}</td>
                <td className="stat">{pct(r.store_pct)}</td>
                <td className="stat">{pct(r.baseline_pct)}</td>
                {!awal && (
                  <td
                    className="stat"
                    style={{ color: r.gap > 0 ? "var(--red-ink)" : "var(--green-ink)" }}
                  >
                    {r.gap > 0 ? "+" : ""}
                    {pct(r.gap)}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="meta" style={{ marginTop: 8 }}>
        Dari <span className="stat">{rows[0].baseline_sample_size}</span> ulasan pembanding ·
        keyakinan {rows[0].confidence_level} · margin pembanding ±
        <span className="stat">{pct(rows[0].margin_of_error)}</span> · margin toko Anda ±
        <span className="stat">{pct(rows[0].store_margin_of_error)}</span>
      </p>
    </section>
  );
}

/** Sebaran aspek sebagai batang horizontal.
 *
 * Batang horizontal dipilih karena tugas datanya membandingkan BESARAN antar kategori yang
 * labelnya panjang ("kesesuaian deskripsi"); batang vertikal memaksa label dimiringkan dan
 * tidak terbaca di layar HP. Nilainya dilabeli langsung di ujung kanan, sehingga identitas
 * tidak pernah bergantung pada warna saja.
 *
 * `focus` adalah aspek yang ditandai pengguna di layar unggah. Perlakuannya SATU hal saja:
 * aspek yang ditandai tidak boleh terpotong oleh batas enam baris. Aspek yang jarang disebut
 * justru sering aspek yang paling ingin diperiksa - "adakah yang meragukan keaslian barang
 * saya" dijawab paling jujur oleh angka kecil, dan angka itulah yang hilang saat daftarnya
 * dipotong menurut jumlah sebutan. Urutannya sendiri TIDAK diubah: batang yang melompat ke
 * atas karena ditandai berhenti bisa dibaca sebagai perbandingan besaran.
 */
export function AspectChart({ aggregates, focus = [] }) {
  if (!aggregates?.length) return null;

  const ditandai = new Set(focus);
  const urut = [...aggregates].sort((a, b) => b.total_mentions - a.total_mentions);
  const rows = [
    ...urut.slice(0, 6),
    ...urut.slice(6).filter((r) => ditandai.has(r.aspect)),
  ].sort((a, b) => b.total_mentions - a.total_mentions);
  const max = Math.max(...rows.map((r) => r.total_mentions), 1);
  const adaTanda = rows.some((r) => ditandai.has(r.aspect));

  return (
    <section className="panel">
      <div className="panel-title">
        Sebaran per aspek
        {adaTanda && <em>◆ ditandai sebagai fokus Anda</em>}
      </div>
      <div className="legend">
        <span>
          <i style={{ background: "var(--blue)" }} />
          Disebut
        </span>
        <span>
          <i style={{ background: "var(--red-base)" }} />
          Berisi keluhan
        </span>
      </div>

      <div className="bars">
        {rows.map((r, i) => {
          const netral = r.total_mentions - r.negative_count;
          const fokus = ditandai.has(r.aspect);
          return (
            <div
              className={`bar ${fokus ? "bar--fokus" : ""}`}
              key={r.aspect}
              title={`${aspectLabel(r.aspect)}: ${r.total_mentions} sebutan, ${r.negative_count} berisi keluhan`}
            >
              <span className="bar__name">
                {/* Belah ketupat, bukan warna. Batangnya sudah memakai biru dan merah untuk
                    arti lain; menandai fokus dengan warna ketiga membuat legenda di atas
                    berbohong. Bentuk juga tetap terbaca oleh mata yang tidak membedakan
                    warna. */}
                {/* `role="img"` supaya `aria-label`-nya benar-benar dibacakan: pada elemen
                    tanpa peran, atribut itu diabaikan sebagian pembaca layar dan yang
                    terdengar tinggal nama aspeknya - tak terbedakan dari aspek lain. */}
                {fokus && (
                  <b className="bar__tanda" role="img" aria-label="Fokus Anda:">
                    ◆
                  </b>
                )}
                {aspectLabel(r.aspect)}
              </span>
              <span className="bar__track">
                <i
                  className="bar__fill"
                  style={{
                    width: `${(netral / max) * 100}%`,
                    background: "linear-gradient(90deg, var(--blue), var(--blue-light))",
                    animationDelay: `${i * 55}ms`,
                  }}
                />
                <i
                  className="bar__fill"
                  style={{
                    width: `${(r.negative_count / max) * 100}%`,
                    background: "linear-gradient(90deg, var(--red-base), var(--red-light))",
                    animationDelay: `${i * 55 + 40}ms`,
                  }}
                />
              </span>
              <span className="bar__val">{r.total_mentions}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** OPP-01 - aspek yang justru dipuji. Sinyal untuk promosi, bukan teks iklan jadi. */
export function OpportunityCard({ opportunity: o }) {
  return (
    <article className="acard">
      <span className="badge badge--positive">Peluang</span>
      <h4>{o.highlight}</h4>
      <p>
        <span className="stat">{o.positive_count}</span> sebutan positif ·{" "}
        <span className="stat">{pct(o.pct_positive)}</span> dari yang membahas{" "}
        {aspectLabel(o.aspect)}. Dapat Anda pakai sebagai bahan promosi. Sistem tidak menuliskan
        materi iklannya untuk Anda.
      </p>
      {o.evidence_quotes.map((c) => (
        <EvidenceStrip key={c.citation_id} citation={c} />
      ))}
    </article>
  );
}

/** L4 - ulasan yang teks dan fotonya menunjuk arah berlawanan.
 *
 * Bentuknya menaruh kedua bukti BERDAMPINGAN dan tidak memutuskan siapa yang benar. Itu bukan
 * kehati-hatian berlebihan: sistem memang tidak tahu apakah pembelinya sungkan menulis
 * keluhan, salah unggah foto, atau memfoto barang lain. Yang diketahuinya cuma bahwa keduanya
 * tidak cocok - dan itu saja sudah cukup untuk meminta satu menit perhatian manusia.
 *
 * Nilainya justru dari kelangkaan sinyalnya. Ulasan bintang lima bertuliskan "barangnya
 * bagus!" dengan foto barang penyok terhitung sebagai kepuasan di setiap dashboard yang ada di
 * pasar, karena semuanya buta foto. Masalah nyatanya tidak pernah muncul di angka mana pun.
 */
export function ContradictionCard({ finding: f }) {
  return (
    <article className="acard acard--sedang kontra">
      <span className="badge badge--sedang">Perlu dicek sendiri</span>
      <h4>Foto membantah teksnya</h4>
      <p>{f.display_note}</p>

      <div className="kontra__pasangan">
        <div className="kontra__sisi">
          <div className="kontra__label">Kata teksnya</div>
          <EvidenceStrip
            citation={{
              citation_id: `k-${f.review_id}`,
              review_id: f.review_id,
              quote: f.quote,
              rating: f.rating,
            }}
          />
        </div>
        <div className="kontra__sisi">
          <div className="kontra__label">Kata fotonya</div>
          <div className="kontra__visual">
            <b>{VISUAL_LABEL[f.visual.label] ?? f.visual.label}</b>
            <span className="meta">
              keyakinan <span className="stat">{pct(f.visual.confidence)}</span> ·{" "}
              {f.visual.model_version}
            </span>
            {/* Foto aslinya sengaja tidak ditampilkan ulang: gambar tidak pernah menyimpan
                di server, dan menampilkannya kembali menuntut penyimpanan sesi yang justru
                dihindari seluruh produk ini. Yang ditunjukkan adalah bacaannya. */}
            <p className="meta">
              Foto ini tidak disimpan di server, jadi tidak dapat ditampilkan ulang di sini.
              Buka ulasan <span className="stat">{f.review_id}</span> di marketplace Anda untuk
              melihatnya.
            </p>
          </div>
        </div>
      </div>

      <p className="meta">
        Sistem tidak menyimpulkan mana yang benar. Keduanya ditampilkan apa adanya supaya Anda
        yang memutuskan.
      </p>
    </article>
  );
}

/** VIS-02 - temuan foto, termasuk yang abstain.
 *
 * Backend hanya mengisi `findings` bila model visual lolos gerbang go/no-go. Selama belum,
 * daftarnya kosong dan bagian ini TIDAK dirender - lebih baik tidak ada daripada ada tetapi
 * berisi tebakan. Status itu dijelaskan pada tab Roadmap.
 */
export function VisualFindings({ findings }) {
  if (!findings?.length) return null;
  const decided = findings.filter((f) => !f.abstain);
  const abstained = findings.filter((f) => f.abstain);
  return (
    <section className="panel">
      <div className="panel-title">Temuan dari foto ulasan</div>
      {decided.length === 0 ? (
        <p className="body">
          Tidak ada foto yang dapat disimpulkan dengan cukup yakin. Semua foto ditandai perlu
          dilihat manusia.
        </p>
      ) : (
        <ul className="body note-list">
          {decided.map((f) => (
            <li key={f.image_ref}>
              <strong>{VISUAL_LABEL[f.label] ?? f.label}</strong> pada ulasan{" "}
              <span className="stat">{f.review_id}</span> · keyakinan{" "}
              <span className="stat">{pct(f.confidence)}</span>
            </li>
          ))}
        </ul>
      )}
      {abstained.length > 0 && (
        <div className="banner-grey" style={{ marginTop: 14, marginBottom: 0 }}>
          <span className="stat">{abstained.length}</span> foto tidak disimpulkan karena sistem
          tidak cukup yakin. Foto tersebut menunggu Anda periksa sendiri. Sistem sengaja tidak
          menebak.
        </div>
      )}
    </section>
  );
}

/** Bukti lengkap. Lembar yang naik dari bawah di layar sempit, dialog di tengah pada layar
 *  lebar - keduanya elemen `dialog` yang sama, hanya berbeda posisi dan animasi lewat CSS.
 *
 *  `dialog` dipakai, bukan div bertumpuk, karena ia sudah membawa jebakan fokus, penutupan
 *  dengan Esc, dan lapisan teratas yang tidak bisa terpotong oleh `overflow` induk mana pun.
 */
export function EvidenceDialog({ card, section, analysisId, decision, onDecide, onClose }) {
  const ref = useRef(null);
  const headingRef = useRef(null);

  // Bagian mana yang terbuka. Disetel dari pintu yang ditekan pengguna di kartu, dan disetel
  // ULANG tiap kali kartu atau pintunya berganti - tanpa itu, membuka "draf balasan" pada
  // kartu kedua akan menampilkan bagian yang kebetulan terbuka terakhir kali.
  const [buka, setBuka] = useState(section ?? "bukti");
  useEffect(() => {
    setBuka(section ?? "bukti");
  }, [card?.action_id, section]);

  // `onClose` biasanya ditulis sebagai arrow inline di pemanggilnya, sehingga identitasnya
  // berubah pada SETIAP render induk. Kalau ia ikut menjadi dependensi efek di bawah, efek itu
  // melepas lalu memasang ulang pendengarnya berkali-kali - dan peristiwa `close` milik
  // `<dialog>` dikirim secara asinkron, jadi ia dapat tiba tepat di sela pelepasan itu dan
  // hilang tanpa jejak. Akibatnya panel tampak tertutup tetapi state React masih menganggapnya
  // terbuka, dan kartu berikutnya tidak dapat dibuka sama sekali.
  const tutupRef = useRef(onClose);
  tutupRef.current = onClose;

  useEffect(() => {
    const el = ref.current;
    if (!el || !card) return undefined;
    if (!el.open) el.showModal();
    headingRef.current?.focus();
    // Peristiwa `close` menangkap SEMUA jalan keluar - tombol silang, klik latar, dan Esc
    // yang ditangani browser sendiri - sehingga state React tidak pernah tertinggal terbuka.
    const onCloseEvent = () => tutupRef.current?.();
    el.addEventListener("close", onCloseEvent);
    return () => el.removeEventListener("close", onCloseEvent);
  }, [card]);

  // Setiap jalan keluar yang PUNYA penanganya sendiri memanggil ini, bukan hanya menutup
  // elemennya dan berharap peristiwa `close` menyusul. Peristiwa itu tetap dipasang untuk Esc,
  // yang ditangani browser tanpa melewati kode mana pun - tetapi ia bukan satu-satunya
  // tumpuan. Memanggilnya dua kali tidak berakibat apa-apa: keduanya menyetel state ke null.
  const tutup = () => {
    ref.current?.close();
    onClose();
  };

  if (!card) return null;

  return (
    <dialog
      className="sheet"
      ref={ref}
      aria-label={`Bukti untuk ${card.title}`}
      onClick={(e) => {
        // Latar milik elemen dialog itu sendiri, jadi klik di luar panel muncul sebagai
        // klik pada dialognya.
        if (e.target === ref.current) tutup();
      }}
    >
      <div className="sheet__inner">
        <div className="sheet__handle" aria-hidden="true" />
        <div className="sheet__head">
          <h3 tabIndex={-1} ref={headingRef}>
            Bukti untuk: {card.title}
          </h3>
          <button className="sheet__x" onClick={tutup} aria-label="Tutup">
            ×
          </button>
        </div>

        {/* Tiga bagian, satu terbuka pada satu waktu. Akordeon, bukan tiga panel bertumpuk:
            jejak perhitungan sendiri sepanjang satu layar penuh, dan menaruhnya terbuka di
            bawah bukti membuat tombol keputusan di kaki lembar berada di luar jangkauan
            gulir bagi orang yang cuma ingin menekan "Terima". */}
        <div className="tabs tabs--block" role="tablist" aria-label="Isi lembar">
          {[
            ["bukti", `Bukti (${card.evidence_quotes.length})`],
            ["balasan", "Draf balasan"],
            ["jejak", "Jejak perhitungan"],
          ].map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={buka === id}
              className={`tab ${buka === id ? "tab--active" : ""}`}
              onClick={() => setBuka(id)}
            >
              {label}
            </button>
          ))}
        </div>

        {buka === "bukti" &&
          (card.evidence_quotes.length === 0 ? (
            <div className="banner-grey">
              Data belum cukup untuk menampilkan kutipan pendukung pada topik ini.
            </div>
          ) : (
            <div className="sheet__quotes">
              {card.evidence_quotes.map((c) => (
                <EvidenceStrip key={c.citation_id} citation={c} tag={card.aspect_label} />
              ))}
            </div>
          ))}

        {/* Keduanya dipasang-lepas mengikuti bagian yang terbuka, bukan disembunyikan dengan
            CSS: yang menempel pada pemasangannya adalah permintaan jaringannya, dan panel
            yang tidak pernah dibuka tidak boleh menembak permintaan apa pun. */}
        {buka === "balasan" && (
          <ReplyDrafts analysisId={analysisId} card={card} aktif />
        )}
        {buka === "jejak" && <TracePanel analysisId={analysisId} card={card} aktif />}

        {buka === "bukti" && card.visual_evidence && (
          <div className="banner-grey" style={{ marginTop: 12 }}>
            {card.visual_evidence.abstain ? (
              <>
                Ada foto pada ulasan ini, tetapi sistem tidak cukup yakin untuk menyimpulkannya (
                {card.visual_evidence.abstain_reason}). Silakan periksa sendiri.
              </>
            ) : (
              <>
                Foto pada ulasan <span className="stat">{card.visual_evidence.review_id}</span>{" "}
                terdeteksi sebagai{" "}
                <b>{VISUAL_LABEL[card.visual_evidence.label] ?? card.visual_evidence.label}</b>{" "}
                dengan keyakinan <span className="stat">{pct(card.visual_evidence.confidence)}</span>
                .
              </>
            )}
          </div>
        )}

        {/* Ringkasan alasan disembunyikan saat jejaknya terbuka: ia adalah versi kalimat dari
            langkah 3 dan 4 di panel itu, dan menaruh keduanya berdampingan membuat pembaca
            mencari-cari perbedaannya, padahal tidak ada. */}
        {buka !== "jejak" && (
          <div className="reason-box">
            <h5>Kenapa ini diprioritaskan</h5>
            <Narrative text={card.priority_reasoning} className="body" />
          </div>
        )}

        <div className="banner-grey" style={{ marginTop: 12 }}>
          Risiko bila keliru: {card.risk_if_recommendation_wrong}
        </div>

        <div className="sheet__foot">
          <DecisionRow
            actionId={card.action_id}
            decision={decision}
            onDecide={(id, value) => {
              onDecide(id, value);
              tutup();
            }}
          />
        </div>
      </div>
    </dialog>
  );
}
