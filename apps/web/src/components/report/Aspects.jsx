/** Seluruh aspek, satu baris masing-masing, dapat dibuka untuk melihat dasarnya.
 *
 * Bentuknya daftar rapat, BUKAN sebelas kartu berjajar. Sebelas kartu seukuran dengan ikon,
 * judul, dan tiga baris teks adalah bentuk yang paling sering muncul saat "tampilkan semuanya"
 * diterjemahkan langsung ke tata letak - dan hasilnya justru tidak bisa dibandingkan: mata
 * harus melompat antar kotak untuk menimbang dua angka yang seharusnya bersebelahan. Daftar
 * rapat menaruh seluruh batang pada satu sumbu vertikal yang sama, jadi perbandingannya
 * terbaca tanpa dibaca.
 *
 * Tiga kelompok, dan urutannya adalah urutan mendesaknya:
 *
 *   1. Yang dikeluhkan - terurut menurut jumlah keluhan.
 *   2. Yang disebut tanpa keluhan - ada di data, tidak menuntut tindakan.
 *   3. Yang tidak disebut sama sekali - dan ini justru kelompok yang paling mudah hilang.
 *
 * Kelompok ketiga adalah alasan berkas ini menerima daftar taksonomi dari `lib/aspects.js`
 * alih-alih hanya memetakan apa yang dikembalikan backend. Backend hanya mengirim aspek yang
 * punya minimal satu sebutan; aspek bernilai nol, menurut definisinya, tidak ada di sana.
 * Padahal "tidak satu pun pembeli mempertanyakan keaslian barang saya" adalah temuan, bukan
 * ketiadaan temuan - dan itu tepat jenis kalimat yang hilang kalau daftarnya cuma memetakan
 * data yang datang.
 */

import { useState } from "react";

import { aspekUntuk } from "../../lib/aspects.js";
import {
  SEVERITY_LABEL,
  TREND_LABEL,
  aspectTitle,
  pct,
} from "../../lib/format.js";
import { EvidenceStrip } from "../insight.jsx";
import { Sparkline } from "./Periods.jsx";

/** Panah tren. Bentuk DAN teks, tidak pernah warna saja. */
function Tren({ trend }) {
  if (!trend || trend === "tidak_cukup_data") return null;
  const panah = { meningkat: "↑", menurun: "↓", stabil: "→" }[trend];
  return (
    <span className={`tren tren--${trend}`}>
      <i aria-hidden="true">{panah}</i>
      {TREND_LABEL[trend]}
    </span>
  );
}

/** Satu aspek yang punya sebutan di dalam data. */
function BarisAspek({
  agg, total, benchmark, kartu, seri, buckets, terkalibrasi, terbuka, onToggle,
}) {
  const porsi = total ? agg.total_mentions / total : 0;
  const negatif = total ? agg.negative_count / total : 0;

  return (
    <div className={`aspek ${terbuka ? "aspek--buka" : ""}`}>
      <button
        className="aspek__kepala"
        onClick={onToggle}
        aria-expanded={terbuka}
        aria-label={`${aspectTitle(agg.aspect)}: ${agg.total_mentions} sebutan, ${agg.negative_count} berisi keluhan`}
      >
        <span className="aspek__nama">{aspectTitle(agg.aspect)}</span>

        {/* Dua lapis pada satu batang: seluruh sebutan, lalu bagian yang berkeluhan di
            atasnya. Dua batang terpisah akan menuntut pembacanya menjumlahkan sendiri. */}
        <span className="aspek__track" aria-hidden="true">
          <i className="aspek__isi aspek__isi--semua" style={{ width: `${porsi * 100}%` }} />
          <i className="aspek__isi aspek__isi--neg" style={{ width: `${negatif * 100}%` }} />
        </span>

        <span className="aspek__jml">
          <span className="stat">{agg.negative_count}</span>
          <em>/{agg.total_mentions}</em>
        </span>

        {seri && buckets?.length > 1 && <Sparkline counts={seri.counts} buckets={buckets} />}

        <Tren trend={agg.trend} />

        <span className="aspek__panah" aria-hidden="true">
          ›
        </span>
      </button>

      <div className="aspek__laci" data-buka={terbuka ? "ya" : "tidak"}>
        <div className="aspek__laci-isi">
          <dl className="aspek__fakta">
            <div>
              <dt>Disebut</dt>
              <dd>
                <span className="stat">{agg.total_mentions}</span> kali dari{" "}
                <span className="stat">{total}</span> ulasan
              </dd>
            </div>
            <div>
              <dt>Berisi keluhan</dt>
              <dd>
                <span className="stat">{agg.negative_count}</span> ({pct(agg.pct_negative)} dari
                sebutannya)
              </dd>
            </div>
            <div>
              <dt>Dipuji</dt>
              <dd>
                <span className="stat">{agg.positive_count}</span> sebutan
              </dd>
            </div>
            <div>
              <dt>Keparahan tipikal</dt>
              <dd>{SEVERITY_LABEL[agg.dominant_severity] ?? agg.dominant_severity}</dd>
            </div>
            {benchmark && (
              <div>
                <dt>Dibanding kategori</dt>
                <dd>
                  <span className="stat">{pct(benchmark.store_pct)}</span> vs{" "}
                  <span className="stat">{pct(benchmark.baseline_pct)}</span>{" "}
                  {/* Selisihnya ditahan pada data tipis dengan alasan yang sama seperti di
                      tabel benchmark: margin sisi toko lebih lebar daripada selisih yang mau
                      ditunjukkan, jadi tandanya sendiri bisa terbalik. Lihat BenchmarkCard. */}
                  {benchmark.preliminary ? (
                    <em className="gap">indikasi awal</em>
                  ) : (
                    <em className={benchmark.gap > 0 ? "gap gap--buruk" : "gap gap--baik"}>
                      {benchmark.gap > 0 ? "+" : ""}
                      {pct(benchmark.gap)}
                    </em>
                  )}
                </dd>
              </div>
            )}
            {/* Keyakinan model tampil HANYA bila checkpoint-nya sudah dikalibrasi.
                
                Sebelum kalibrasi, angkanya adalah penanda tetap (0,80 saat checkpoint aktif,
                0,60 saat leksikon) yang tidak pernah berubah antar aspek. Ditampilkan
                berdampingan dengan angka yang benar-benar dihitung, ia terbaca sebagai hasil
                pengukuran - dan itu satu-satunya angka di seluruh laporan yang tidak diukur.
                
                Sesudah kalibrasi (temperature scaling, ml/text/calibrate.py) ia menjadi
                probabilitas sungguhan dengan galat kalibrasi yang dilaporkan di MODEL_CARD,
                dan tidak ada lagi alasan menahannya. Saklarnya datang dari backend, bukan
                dari tebakan sisi klien: hanya sisi yang membaca isi checkpoint yang tahu. */}
            {terkalibrasi && (
              <div>
                <dt>Keyakinan model</dt>
                <dd>
                  <span className="stat">{pct(agg.avg_confidence)}</span> rata-rata,
                  terkalibrasi
                </dd>
              </div>
            )}
          </dl>

          {/* Kutipan diambil dari Action Card aspek yang sama - satu-satunya tempat bukti
              sudah tersaring agar benar-benar memuat keluhan pada aspek itu. Aspek tanpa
              kartu tidak dibuatkan kutipan sendiri; mengambil kutipan tanpa penyaringan itu
              persis kesalahan yang tercatat di LIMITATIONS.md. */}
          {kartu?.evidence_quotes?.length > 0 && (
            <div className="aspek__bukti">
              <p className="meta">Kutipan aslinya:</p>
              {kartu.evidence_quotes.slice(0, 2).map((c) => (
                <EvidenceStrip key={c.citation_id} citation={c} />
              ))}
            </div>
          )}

          {agg.negative_count > 0 && !kartu && (
            <p className="meta">
              Aspek ini tidak masuk lima prioritas teratas, jadi kutipan pendukungnya tidak
              diambil. Tanyakan langsung di tab Tanya Jawab untuk melihat ulasannya.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export function AspectSections({ result, category }) {
  const [buka, setBuka] = useState(null);

  const total = result.summary.total_reviews;
  const aggregates = result.aspect_aggregates ?? [];
  const benchmarks = Object.fromEntries(
    (result.benchmark_by_category?.[category] ?? result.benchmark ?? []).map((b) => [b.aspect, b])
  );
  const kartuPerAspek = Object.fromEntries((result.top_actions ?? []).map((c) => [c.aspect, c]));
  const seriPerAspek = Object.fromEntries(
    (result.period_history?.series ?? []).map((s) => [s.aspect, s])
  );
  const buckets = result.period_history?.buckets ?? [];

  const berkeluhan = aggregates
    .filter((a) => a.negative_count > 0)
    .sort((a, b) => b.negative_count - a.negative_count);
  const bersih = aggregates
    .filter((a) => a.negative_count === 0)
    .sort((a, b) => b.total_mentions - a.total_mentions);

  const disebut = new Set(aggregates.map((a) => a.aspect));
  const takDisebut = aspekUntuk(category).filter((id) => !disebut.has(id));

  const baris = (agg) => (
    <BarisAspek
      key={agg.aspect}
      agg={agg}
      total={total}
      benchmark={benchmarks[agg.aspect]}
      terkalibrasi={Boolean(result.confidence_calibrated)}
      kartu={kartuPerAspek[agg.aspect]}
      seri={seriPerAspek[agg.aspect]}
      buckets={buckets}
      terbuka={buka === agg.aspect}
      onToggle={() => setBuka(buka === agg.aspect ? null : agg.aspect)}
    />
  );

  return (
    <div className="aspeks">
      {/* Angka di tiap baris berbunyi "8/57", dan tanpa keterangan itu bisa dibaca terbalik -
          delapan sebutan yang lima puluh tujuh di antaranya bermasalah tidak masuk akal, tetapi
          pembaca baru menyadarinya setelah berhenti dan berpikir. Legenda ini menyebutkan
          urutannya sekali, di tempat yang terbaca sebelum baris pertama. */}
      <div className="legend aspeks__legend">
        <span>
          <i style={{ background: "var(--blue)" }} />
          Disebut
        </span>
        <span>
          <i style={{ background: "var(--red-base)" }} />
          Berisi keluhan
        </span>
        <span className="aspeks__baca">angka dibaca keluhan / sebutan</span>
      </div>

      {berkeluhan.length > 0 && (
        <>
          <p className="aspeks__grup">Yang dikeluhkan</p>
          {berkeluhan.map(baris)}
        </>
      )}

      {bersih.length > 0 && (
        <>
          <p className="aspeks__grup">Disebut, tanpa keluhan</p>
          {bersih.map(baris)}
        </>
      )}

      {takDisebut.length > 0 && (
        <>
          <p className="aspeks__grup">Tidak disebut sama sekali</p>
          <div className="aspeks__sepi">
            <ul>
              {takDisebut.map((id) => (
                <li key={id}>{aspectTitle(id)}</li>
              ))}
            </ul>
            <p className="meta">
              Tidak satu pun dari <span className="stat">{total}</span> ulasan menyinggung aspek
              ini. Itu bisa berarti tidak bermasalah, bisa juga berarti pembeli Anda memang tidak
              membicarakannya - keduanya berbeda, dan data ini tidak bisa memisahkan keduanya.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
