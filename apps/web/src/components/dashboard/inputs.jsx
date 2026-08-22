/** Tiga cara memasukkan ulasan: tempel teks, unggah berkas, dan tangkapan layar.
 *
 * Ketiganya bermuara pada bentuk yang sama - larik RawReview - sehingga layar berikutnya
 * tidak perlu tahu dari mana datanya datang.
 */

import { useRef, useState } from "react";
import { MAX_FILE_BYTES, MAX_ROWS } from "../../api/client.js";
import { useOverflowX } from "../../lib/hooks.js";

const UploadIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M12 4v12m0-12l-4 4m4-4l4 4M5 18h14"
      stroke="#fff"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

/** Area jatuhkan-berkas yang juga dapat diklik dan dijangkau keyboard.
 *
 * Elemennya `button`, bukan `div` dengan handler klik: pengguna keyboard dan pembaca layar
 * mendapat afordans yang sama tanpa peran ARIA tambahan. */
export function Dropzone({ accept, multiple = false, onPick, title, hint, busy }) {
  const input = useRef(null);
  const [over, setOver] = useState(false);

  return (
    <>
      <button
        type="button"
        className={`dropzone ${over ? "dropzone--over" : ""}`}
        disabled={busy}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const dropped = [...(e.dataTransfer.files ?? [])];
          if (dropped.length) onPick(multiple ? dropped : dropped[0]);
        }}
      >
        <span className="dz-icon">
          <UploadIcon />
        </span>
        <span className="dz-title">{title}</span>
        <span className="dz-hint">{hint}</span>
      </button>
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="sr-only"
        onChange={(e) => {
          const picked = [...(e.target.files ?? [])];
          if (picked.length) onPick(multiple ? picked : picked[0]);
          e.target.value = ""; // supaya memilih berkas yang sama dua kali tetap memicu
        }}
      />
    </>
  );
}

// --------------------------------------------------------------------------------------
// Tempel teks
// --------------------------------------------------------------------------------------

export function PasteInput({ value, onChange }) {
  return (
    <div className="panel">
      <div className="panel-title">Tempel ulasan Anda, satu ulasan per baris</div>
      <label className="sr-only" htmlFor="paste">
        Ulasan Anda
      </label>
      <textarea
        id="paste"
        className="textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={"ukurannya kekecilan padahal pesan L\npengiriman cepat, packing rapi\n…"}
      />
    </div>
  );
}

// --------------------------------------------------------------------------------------
// Unggah berkas: pemetaan kolom dan pratinjau
// --------------------------------------------------------------------------------------

const MAPPABLE = [
  ["text", "Teks ulasan", true],
  ["rating", "Rating", false],
  ["timestamp", "Tanggal", false],
  ["product_name", "Nama produk", false],
];

/** ING-07 - pengguna menentukan sendiri kolom mana yang berisi apa. */
function ColumnMapper({ columns, mapping, onChange }) {
  return (
    <div>
      {MAPPABLE.map(([field, label, required]) => (
        <div className="map-row" key={field}>
          <label className="src" htmlFor={`map-${field}`}>
            {label}
            {required ? " *" : ""}
          </label>
          <span className="arrow" aria-hidden="true">
            →
          </span>
          <select
            id={`map-${field}`}
            value={mapping[field] ?? ""}
            onChange={(e) => onChange({ ...mapping, [field]: e.target.value })}
          >
            <option value="">{required ? "Pilih kolom" : "Tidak ada"}</option>
            {columns.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}

/** Pratinjau lima baris pertama supaya pengguna tahu yang terbaca benar sebelum menganalisis.
 *
 * Kolom yang sudah dipetakan ditarik ke depan, bukan diambil apa adanya dari urutan berkas.
 * Ekspor marketplace membuka diri dengan kolom teknis - review_id, order_id, shop_id - dan
 * mengambil empat kolom pertama begitu saja menghasilkan pratinjau yang tidak memuat satu pun
 * kolom yang barusan dipetakan pengguna. Yang ingin ia pastikan justru itu.
 */
function PreviewTable({ rows, columns, mapping }) {
  const [scroll, fits] = useOverflowX();
  if (!rows?.length) return null;

  const dipetakan = [mapping.text, mapping.rating, mapping.timestamp, mapping.product_name]
    .filter((c) => c && columns.includes(c));
  const shown = [...new Set([...dipetakan, ...columns])].slice(0, 4);

  return (
    <>
      <div className={`mtable-scroll ${fits ? "mtable-scroll--fit" : ""}`} ref={scroll}>
        <table className="mtable">
          <thead>
            <tr>
              {shown.map((c) => (
                <th key={c}>
                  {c}
                  {c === mapping.text && " · ulasan"}
                  {c === mapping.rating && " · rating"}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 5).map((row, i) => (
              <tr key={i}>
                {shown.map((c) => (
                  <td key={c} className="cell-clip" title={String(row[c] ?? "")}>
                    {String(row[c] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="meta" style={{ marginTop: 8 }}>
        Menampilkan 5 dari <span className="stat">{rows.length}</span> baris terbaca
        {columns.length > shown.length &&
          ` · ${columns.length - shown.length} kolom lain disembunyikan`}
      </p>
    </>
  );
}

export function FileInput({ file, mapping, onPick, onMap, onClear }) {
  const maxMb = Math.round(MAX_FILE_BYTES / (1024 * 1024));
  return (
    <>
      <Dropzone
        accept=".csv,.json,text/csv,application/json"
        onPick={onPick}
        title="Tarik berkas CSV/JSON ke sini"
        hint={`atau klik untuk memilih berkas · maksimal ${maxMb} MB, ${MAX_ROWS} baris pertama`}
      />

      {file && (
        <>
          <div className="panel">
            <p className="body">
              <b>{file.name}</b> terbaca · <span className="stat">{file.columns.length}</span> kolom
              {file.truncated && ` · sisanya dipotong di ${MAX_ROWS} baris`}
            </p>
          </div>

          <div className="panel">
            <div className="panel-title">
              Pemetaan kolom <em>otomatis, bisa diubah</em>
            </div>
            <ColumnMapper columns={file.columns} mapping={mapping} onChange={onMap} />
            <p className="meta" style={{ marginTop: 10 }}>
              Tebakan otomatis dapat Anda ubah. Hanya kolom teks ulasan yang wajib.
            </p>
          </div>

          <div className="panel">
            <div className="panel-title">Pratinjau data</div>
            <PreviewTable rows={file.rows} columns={file.columns} mapping={mapping} />
          </div>

          <button className="btn btn--text btn--block" onClick={onClear}>
            Ganti berkas
          </button>
        </>
      )}
    </>
  );
}

// --------------------------------------------------------------------------------------
// Tangkapan layar
// --------------------------------------------------------------------------------------

/** Pemilih bintang untuk satu draf.
 *
 * Rating tidak selalu terbaca dari tangkapan layar: bintangnya ikon, bukan teks, dan OCR
 * membaca teks. Sebelumnya nilainya hanya DITAMPILKAN kalau kebetulan terbaca, tanpa satu pun
 * cara mengisinya sendiri - padahal orang yang sedang menatap tangkapan layarnya bisa melihat
 * bintangnya dalam sekejap.
 *
 * Yang hilang bersama rating bukan hiasan. `severity` sebuah keluhan diturunkan dari rating
 * ulasannya (`_severity_from` di adapter teks), dan severity adalah salah satu dari tiga
 * pengali inti rumus prioritas. Draf tanpa rating karenanya masuk analisis dengan keparahan
 * paling rendah, apa pun bunyi keluhannya - jalur tangkapan layar diam-diam menghasilkan
 * urutan prioritas yang berbeda dari jalur CSV untuk ulasan yang sama persis.
 *
 * `select` bawaan, bukan lima tombol bintang: di ponsel ia membuka pemilih milik sistem yang
 * sasaran sentuhnya sudah cukup besar, dan pembaca layar mengumumkannya sebagai satu kendali
 * bernama alih-alih lima tombol yang harus ditebak hubungannya.
 */
function DraftRating({ id, value, onChange }) {
  return (
    <span className="draft__bintang">
      <label className="sr-only" htmlFor={`rating-${id}`}>
        Rating ulasan ini
      </label>
      <select
        id={`rating-${id}`}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        {/* "Tanpa rating" adalah pilihan sah dan tetap yang pertama: menebak bintang yang
            tidak terlihat lebih buruk daripada mengosongkannya. */}
        <option value="">Tanpa rating</option>
        {[1, 2, 3, 4, 5].map((n) => (
          <option key={n} value={n}>
            {n}/5
          </option>
        ))}
      </select>
    </span>
  );
}

/** Hasil OCR selalu ditampilkan sebagai draf yang bisa disunting, tidak pernah langsung
 *  dianalisis. Pembacaan teks dari gambar TIDAK pernah sempurna - huruf yang salah baca akan
 *  merambat ke seluruh hasil analisis, dan pemilik toko adalah satu-satunya yang tahu bunyi
 *  ulasan aslinya. */
export function ScreenshotInput({ shots, drafts, busy, onPick, onEdit, onRemove, onClear }) {
  return (
    <>
      <Dropzone
        accept="image/png,image/jpeg,image/webp"
        multiple
        busy={busy}
        onPick={onPick}
        title="Tarik tangkapan layar ulasan ke sini"
        hint="PNG atau JPG · bisa beberapa sekaligus"
      />

      {/* Jalur kamera, terpisah dari dropzone: atribut `capture` pada input yang sama akan
          memaksa kamera dan menutup pilihan galeri di sebagian peramban ponsel. Di desktop
          tanpa kamera, input ini jatuh ke pemilih berkas biasa - tidak ada yang rusak. Yang
          difoto adalah LAYAR yang menampilkan ulasan (ponsel lain, tablet, monitor); hasilnya
          tetap lewat OCR yang sama dan tetap menjadi draf yang wajib diperiksa. */}
      <label className="btn btn--outline camera-pick">
        Ambil foto layar ulasan dengan kamera
        <input
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={busy}
          onChange={(e) => {
            const picked = [...(e.target.files ?? [])];
            if (picked.length) onPick(picked);
            e.target.value = "";
          }}
        />
      </label>

      {busy && (
        <div className="panel">
          <p className="body">Membaca teks dari gambar…</p>
        </div>
      )}

      {shots.length > 0 && !busy && (
        <div className="panel">
          <p className="body">
            <span className="stat">{shots.length}</span> gambar terbaca ·{" "}
            <span className="stat">{drafts.length}</span> ulasan ditemukan
          </p>
          <p className="meta" style={{ marginTop: 6 }}>
            Periksa dan perbaiki dulu di bawah. Pembacaan teks dari gambar tidak pernah sempurna,
            dan huruf yang salah baca akan terbawa ke seluruh hasil analisis.
          </p>
        </div>
      )}

      {drafts.map((d, i) => (
        <div className="draft" key={d.review_id}>
          <div className="draft__head">
            <span className="draft__no">Ulasan {i + 1}</span>
            <div className="draft__meta">
              <DraftRating
                id={d.review_id}
                value={d.rating}
                onChange={(rating) => onEdit(d.review_id, { rating })}
              />
              <span className={`draft__conf draft__conf--${d.confidence_level}`}>
                {d.confidence_level === "rendah" ? "perlu diperiksa" : "terbaca jelas"}
              </span>
              <button
                className="draft__x"
                onClick={() => onRemove(d.review_id)}
                aria-label={`Buang ulasan ${i + 1}`}
              >
                ×
              </button>
            </div>
          </div>
          <label className="sr-only" htmlFor={`draft-${d.review_id}`}>
            Teks ulasan {i + 1}
          </label>
          <textarea
            id={`draft-${d.review_id}`}
            className="draft__text"
            value={d.text}
            rows={Math.min(6, Math.max(2, Math.ceil(d.text.length / 58)))}
            onChange={(e) => onEdit(d.review_id, { text: e.target.value })}
          />
        </div>
      ))}

      {shots.length > 0 && !busy && (
        <button className="btn btn--text btn--block" onClick={onClear}>
          Buang semua dan mulai lagi
        </button>
      )}
    </>
  );
}
