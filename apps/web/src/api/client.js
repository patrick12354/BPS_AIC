/** Klien API backend.
 *
 * URL relatif disengaja: kode yang sama berjalan di dev (lewat proxy Vite) dan di container
 * (di belakang reverse proxy) tanpa alamat backend yang di-hardcode.
 */

// Dua batas, bukan satu. Panggilan ringan (readiness, models, dataset contoh) yang menggantung
// satu menit hampir pasti benar-benar bermasalah, jadi menyerah cepat adalah perilaku yang
// membantu. Analisis lain ceritanya: pada CPU dua inti, 66 ulasan pernah terukur 88 detik - satu
// batas 60 detik memutus analisis yang sebenarnya berjalan normal dan menampilkannya sebagai
// kegagalan. Batas analisis disamakan dengan proxy_read_timeout nginx (300s) supaya tidak ada
// sisi yang menyerah lebih dulu dari sisi lain.
const TIMEOUT_MS = 60_000;
const TIMEOUT_ANALISIS_MS = 300_000;

async function request(path, options = {}, timeoutMs = TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  // Unggahan multipart TIDAK boleh diberi Content-Type sendiri: browser yang menyusunnya,
  // lengkap dengan boundary, dan menimpanya membuat backend gagal mengurai berkasnya.
  const isForm = options.body instanceof FormData;
  try {
    const response = await fetch(path, {
      headers: isForm ? undefined : { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      // Backend mengembalikan ErrorResponse berbahasa Indonesia (bagian 25.13). Pakai pesan
      // itu apa adanya - menggantinya dengan pesan generik justru menghilangkan saran
      // perbaikan yang sudah disiapkan backend.
      throw Object.assign(new Error(payload?.message ?? "Terjadi masalah pada sistem."), {
        suggestedAction: payload?.suggested_action,
        code: payload?.error_code,
      });
    }
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Analisis memakan waktu terlalu lama. Coba dengan data lebih sedikit.");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  readiness: () => request("/api/v1/readiness"),
  models: () => request("/api/v1/models"),
  sample: () => request("/api/v1/demo/sample"),
  analyze: (reviews) =>
    request(
      "/api/v1/analyze",
      { method: "POST", body: JSON.stringify({ reviews }) },
      TIMEOUT_ANALISIS_MS
    ),
  ask: (analysisId, question) =>
    request(
      "/api/v1/questions",
      { method: "POST", body: JSON.stringify({ analysis_id: analysisId, question }) },
      TIMEOUT_ANALISIS_MS
    ),
  /** S1 - draf balasan penjual untuk ulasan pendukung satu kartu aksi.
   *
   * Batas waktu biasa, bukan batas analisis: penyusunannya template murni atas data yang
   * sudah ada di memori server, terukur dalam milidetik. Kalau ia menggantung satu menit,
   * yang terjadi bukan "sedang lama" melainkan benar-benar bermasalah. */
  replyDrafts: (analysisId, actionId) =>
    request("/api/v1/reply-drafts", {
      method: "POST",
      body: JSON.stringify({ analysis_id: analysisId, action_id: actionId }),
    }),
  /** L5 - ringkasan agregat yang aman dibawa keluar sesi.
   *
   * Diminta ke server, bukan disusun dari `result` yang sudah ada di tangan klien. Bedanya
   * penting: pengguna dapat mengganti kategori pembanding di layar hasil, sehingga `result`
   * di sini boleh berbeda dari analisis yang benar-benar dijalankan. Arsip harus menggambarkan
   * yang dijalankan. */
  archive: (analysisId) =>
    request("/api/v1/archive", {
      method: "POST",
      body: JSON.stringify({ analysis_id: analysisId }),
    }),
  /** L5 - selisih antar-periode terhadap arsip milik pengguna sendiri.
   *
   * Arsipnya ikut dikirim di badan permintaan. Server tidak punya tempat mengambilnya, dan
   * tidak akan pernah punya - itulah cara baris "riwayat antar-sesi" dipenuhi tanpa database. */
  compare: (analysisId, previous) =>
    request("/api/v1/compare", {
      method: "POST",
      body: JSON.stringify({ analysis_id: analysisId, previous }),
    }),
  /** S2 - rantai perhitungan satu kartu aksi.
   *
   * Diambil terpisah, bukan diangkut bersama hasil analisis: satu jejak memuat belasan klausa
   * beserta prediksinya, dan sebagian besar pengguna tidak pernah membukanya. Laporan yang
   * tidak dibuka jejaknya karenanya tidak membayar ongkos payload-nya. */
  trace: (analysisId, actionId) =>
    request("/api/v1/trace", {
      method: "POST",
      body: JSON.stringify({ analysis_id: analysisId, action_id: actionId }),
    }),
  /** ING-10 - baca teks ulasan dari tangkapan layar. Batas waktunya mengikuti analisis
   *  karena OCR pada CPU untuk beberapa gambar sekaligus juga dapat berjalan lama. */
  readScreenshots: (files) => {
    const form = new FormData();
    for (const f of files) form.append("images", f);
    return request(
      "/api/v1/ocr",
      { method: "POST", body: form },
      TIMEOUT_ANALISIS_MS
    );
  },
};

/** Ubah teks tempelan menjadi RawReview. Satu baris = satu ulasan.
 *
 * Tidak ada `product_name` di sini, dan itu keadaan yang benar: teks yang ditempel tidak
 * membawa keterangan produk apa pun. Sebelumnya nilainya diambil dari isian "Produk yang
 * dianalisis" di layar unggah - satu nama yang sama ditempelkan ke SETIAP baris - dan hasilnya
 * bagian per produk melaporkan satu produk berisi seluruh ulasan, yang bukan informasi apa pun.
 * Lebih baik bagiannya tidak muncul sama sekali.
 *
 * `category` datang dari pilihan pengguna di layar unggah. Ia satu-satunya keterangan yang
 * benar-benar hanya diketahui pemilik toko dan tidak ada di dalam berkas mana pun.
 */
export function parsePastedText(text, category = "other") {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length >= 3)
    .map((line, index) => ({
      review_id: `paste_${index + 1}`,
      text: line,
      category,
      source: "manual_upload",
    }));
}

// --------------------------------------------------------------------------------------
// ING-02 / ING-07 - unggah berkas dan pemetaan kolom
// --------------------------------------------------------------------------------------

/** Pecah satu baris CSV dengan menghormati tanda kutip.
 *
 * `split(",")` merusak ulasan asli, karena ulasan pelanggan hampir selalu memuat koma.
 * Kutip ganda di dalam sel di-escape sebagai `""` mengikuti RFC 4180.
 */
function splitCsvLine(line) {
  const cells = [];
  let cell = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (inQuotes) {
      if (ch === '"' && line[i + 1] === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      cells.push(cell);
      cell = "";
    } else {
      cell += ch;
    }
  }
  cells.push(cell);
  return cells.map((c) => c.trim());
}

function parseCsv(raw) {
  // Sel yang dikutip boleh memuat newline, sehingga pemisahan baris tidak dapat dilakukan
  // dengan split("\n") sebelum tahu posisi kutipnya.
  const lines = [];
  let current = "";
  let inQuotes = false;
  for (const ch of raw.replace(/\r\n/g, "\n")) {
    if (ch === '"') inQuotes = !inQuotes;
    if (ch === "\n" && !inQuotes) {
      lines.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  if (current.trim()) lines.push(current);

  const nonEmpty = lines.filter((l) => l.trim());
  if (!nonEmpty.length) return { columns: [], rows: [] };

  const columns = splitCsvLine(nonEmpty[0]);
  const rows = nonEmpty.slice(1).map((line) => {
    const cells = splitCsvLine(line);
    return Object.fromEntries(columns.map((c, i) => [c, cells[i] ?? ""]));
  });
  return { columns, rows };
}

function parseJson(raw) {
  const data = JSON.parse(raw);
  // Beberapa ekspor membungkus larik di dalam objek; ambil larik pertama yang ditemukan.
  const rows = Array.isArray(data)
    ? data
    : Object.values(data).find((v) => Array.isArray(v)) ?? [];
  if (!rows.length) return { columns: [], rows: [] };
  const columns = [...new Set(rows.flatMap((r) => Object.keys(r ?? {})))];
  return { columns, rows: rows.map((r) => ({ ...r })) };
}

export const MAX_FILE_BYTES = 5 * 1024 * 1024;
export const MAX_ROWS = 1000;

/** Baca berkas CSV/JSON menjadi {columns, rows}. Melempar Error berbahasa Indonesia. */
export async function parseFile(file) {
  if (file.size > MAX_FILE_BYTES) {
    throw new Error("Berkas melebihi 5 MB. Coba unggah sebagian datanya lebih dulu.");
  }
  const raw = await file.text();
  const isJson = file.name.toLowerCase().endsWith(".json") || raw.trimStart().startsWith("[");
  let parsed;
  try {
    parsed = isJson ? parseJson(raw) : parseCsv(raw);
  } catch {
    throw new Error("Berkas tidak dapat dibaca. Pastikan formatnya CSV atau JSON yang utuh.");
  }
  if (!parsed.rows.length) {
    throw new Error("Berkas terbaca tetapi tidak berisi baris data.");
  }
  return { ...parsed, truncated: parsed.rows.length > MAX_ROWS, rows: parsed.rows.slice(0, MAX_ROWS) };
}

// Nama kolom yang lazim dipakai ekspor marketplace Indonesia maupun dataset publik.
const COLUMN_HINTS = {
  text: ["review", "ulasan", "text", "content", "comment", "komentar", "isi", "review_text", "customer_review"],
  rating: ["rating", "star", "bintang", "score", "nilai", "skor"],
  timestamp: ["date", "tanggal", "timestamp", "created_at", "waktu", "time"],
  product_name: ["product", "produk", "nama_produk", "product_name", "item", "title"],
};

/** ING-07 - tebak pemetaan kolom; pengguna tetap dapat menimpanya di UI. */
export function guessMapping(columns) {
  const mapping = { text: "", rating: "", timestamp: "", product_name: "" };
  const lower = columns.map((c) => String(c).toLowerCase().trim());
  for (const [field, hints] of Object.entries(COLUMN_HINTS)) {
    // Cocokkan persis lebih dulu; padanan sebagian mudah salah sasaran
    // ("rating_count" bukan rating, "review_id" bukan teks ulasan).
    let idx = lower.findIndex((c) => hints.includes(c));
    if (idx === -1) idx = lower.findIndex((c) => hints.some((h) => c.includes(h) && !c.includes("id")));
    if (idx !== -1) mapping[field] = columns[idx];
  }
  return mapping;
}

const MONTH_OK = /^\d{4}-\d{2}-\d{2}/;

function toIsoOrNull(value) {
  if (!value) return null;
  const s = String(value).trim();
  if (MONTH_OK.test(s)) return s.length === 10 ? `${s}T00:00:00` : s;
  const parsed = new Date(s);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString().slice(0, 19);
}

/** Ubah baris berkas menjadi RawReview memakai pemetaan kolom yang dipilih pengguna.
 *
 * Nama produk datang dari BERKAS, satu-satunya tempat yang benar-benar mengetahuinya. Kolom
 * yang tidak dipetakan berarti `null`, bukan string kosong: `RawReview.product_name` menerima
 * `""` tanpa mengeluh, dan nilai itu lalu terbawa ke hilir sebagai nama produk yang "ada
 * tetapi kosong" - satu baris hantu di tabel per produk yang tidak bisa dijelaskan asalnya. */
export function rowsToReviews(rows, mapping, category = "other") {
  const out = [];
  rows.forEach((row, index) => {
    const text = String(row[mapping.text] ?? "").trim();
    if (text.length < 3) return; // baris kosong dilewati, dihitung sebagai skipped oleh backend

    const ratingRaw = mapping.rating ? Number(String(row[mapping.rating]).replace(",", ".")) : NaN;
    const rating = Number.isFinite(ratingRaw) && ratingRaw >= 1 && ratingRaw <= 5
      ? Math.round(ratingRaw)
      : null;

    out.push({
      review_id: `file_${index + 1}`,
      text,
      rating,
      timestamp: mapping.timestamp ? toIsoOrNull(row[mapping.timestamp]) : null,
      product_name: mapping.product_name
        ? String(row[mapping.product_name] ?? "").trim() || null
        : null,
      category,
      source: "manual_upload",
    });
  });
  return out;
}
