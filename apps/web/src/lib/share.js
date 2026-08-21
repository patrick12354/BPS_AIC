/** Ekspor ringkasan sebagai gambar, digambar sendiri di kanvas (L5 bagian c).
 *
 * Kanal nyata UMKM adalah grup WhatsApp, dan yang beredar di sana gambar - bukan tautan, bukan
 * PDF, dan hampir tidak pernah CSV. Ringkasan yang tidak dapat ditempel ke sana praktis tidak
 * pernah dibagikan.
 *
 * **Digambar sendiri, bukan memotret DOM.** Perpustakaan seperti html2canvas menyalin ulang
 * seluruh mesin tata letak ke dalam kanvas; ia besar, sering meleset pada `backdrop-filter` dan
 * gradien - dua hal yang dipakai hampir setiap panel di dashboard ini - dan menambah
 * ketergantungan yang harus dirawat demi satu tombol. Yang benar-benar dibutuhkan gambar ini
 * cuma selusin teks dan tiga batang.
 *
 * **Tidak ada satu pun teks ulasan di dalamnya.** Aturan yang sama dengan arsip JSON, dan
 * alasan yang sama: gambar ini akan diteruskan ke grup tanpa dibaca ulang lebih dulu. Yang
 * masuk hanya angka agregat dan nama aspek.
 */

const W = 1080;
const H = 1080;

/* Warna ditulis sebagai angka mentah, tidak dibaca dari CSS variable.
 *
 * Gambar yang dibagikan akan dibuka di aplikasi chat yang tidak tahu apa-apa soal tema terang
 * atau gelap. Mengambil `--paper` dari dokumen berarti pengguna bertema gelap mengirimkan kartu
 * hitam ke grup, dan pengguna bertema terang mengirim kartu putih untuk data yang sama -
 * bentuk yang tidak konsisten untuk sesuatu yang mewakili satu produk. */
const WARNA = {
  latar: "#faf9f5",
  tinta: "#14150f",
  redup: "#6b6d63",
  biru: "#2f5fc9",
  biruMuda: "#dbe5fb",
  merah: "#c4463a",
  garis: "#e4e2d9",
  kartu: "#ffffff",
};

const FONT = '"Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

function teks(ctx, isi, x, y, { size = 28, weight = 400, warna = WARNA.tinta, align = "left" } = {}) {
  ctx.font = `${weight} ${size}px ${FONT}`;
  ctx.fillStyle = warna;
  ctx.textAlign = align;
  ctx.textBaseline = "alphabetic";
  ctx.fillText(isi, x, y);
}

function kotakBulat(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/** Potong teks yang kepanjangan dengan elipsis, diukur pada font yang sedang aktif. */
function potong(ctx, isi, maxLebar) {
  if (ctx.measureText(isi).width <= maxLebar) return isi;
  let hasil = isi;
  while (hasil.length > 1 && ctx.measureText(`${hasil}…`).width > maxLebar) {
    hasil = hasil.slice(0, -1);
  }
  return `${hasil}…`;
}

/** Gambar kartu ringkasan ke kanvas baru dan kembalikan elemennya. */
export function gambarRingkasan({ total, berkeluhan, rentang, teratas, judul = "Ulasin" }) {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  ctx.fillStyle = WARNA.latar;
  ctx.fillRect(0, 0, W, H);

  // --- kepala
  teks(ctx, judul, 80, 120, { size: 44, weight: 800, warna: WARNA.biru });
  teks(ctx, "Ringkasan ulasan pelanggan", 80, 168, { size: 28, warna: WARNA.redup });
  if (rentang) teks(ctx, rentang, 80, 210, { size: 24, warna: WARNA.redup });

  ctx.strokeStyle = WARNA.garis;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(80, 250);
  ctx.lineTo(W - 80, 250);
  ctx.stroke();

  // --- dua angka kepala
  teks(ctx, String(total), 80, 380, { size: 120, weight: 800 });
  teks(ctx, "ulasan dianalisis", 80, 424, { size: 28, warna: WARNA.redup });

  const pct = total ? Math.round((berkeluhan / total) * 100) : 0;
  teks(ctx, `${pct}%`, W - 80, 380, { size: 120, weight: 800, warna: WARNA.merah, align: "right" });
  teks(ctx, `${berkeluhan} memuat keluhan`, W - 80, 424, {
    size: 28, warna: WARNA.redup, align: "right",
  });

  // --- tiga keluhan teratas
  teks(ctx, "Yang paling sering dikeluhkan", 80, 530, { size: 32, weight: 700 });

  const kartuY = 570;
  const kartuH = 330;
  ctx.fillStyle = WARNA.kartu;
  kotakBulat(ctx, 80, kartuY, W - 160, kartuH, 24);
  ctx.fill();
  ctx.strokeStyle = WARNA.garis;
  ctx.stroke();

  const baris = teratas.slice(0, 3);
  const maks = Math.max(...baris.map((b) => b.count), 1);
  baris.forEach((b, i) => {
    const y = kartuY + 70 + i * 92;
    ctx.font = `600 30px ${FONT}`;
    teks(ctx, potong(ctx, b.label, 420), 130, y, { size: 30, weight: 600 });
    teks(ctx, `${b.count}`, W - 130, y, { size: 30, weight: 700, warna: WARNA.merah, align: "right" });

    // Batang selalu digambar penuh sebagai alur, lalu diisi menurut porsinya - tanpa alurnya,
    // batang terpendek tidak punya acuan dan angka 3 terlihat sama besar dengan angka 30.
    const barX = 130;
    const barW = W - 260;
    ctx.fillStyle = WARNA.biruMuda;
    kotakBulat(ctx, barX, y + 18, barW, 16, 8);
    ctx.fill();
    ctx.fillStyle = WARNA.merah;
    kotakBulat(ctx, barX, y + 18, Math.max((b.count / maks) * barW, 8), 16, 8);
    ctx.fill();
  });

  if (!baris.length) {
    teks(ctx, "Tidak ada keluhan yang cukup sering muncul.", 130, kartuY + 80, {
      size: 28, warna: WARNA.redup,
    });
  }

  // --- kaki
  //
  // Baris terakhir diakhiri sehingga ekor huruf terjauhnya berhenti sekitar 80px dari tepi
  // bawah - jarak yang sama dengan margin kiri dan kanan. Pada versi pertama ia berhenti di
  // 58px, dan kartunya terlihat sedikit "jatuh" ke bawah tanpa alasan yang bisa ditunjuk.
  ctx.beginPath();
  ctx.moveTo(80, H - 160);
  ctx.lineTo(W - 80, H - 160);
  ctx.stroke();
  teks(ctx, "Dianalisis dengan Ulasin", 80, H - 112, { size: 26, weight: 700 });
  teks(ctx, "Angka dihitung dari ulasan Anda sendiri. Tidak ada teks ulasan di gambar ini.",
    80, H - 84, { size: 22, warna: WARNA.redup });

  return canvas;
}

/** Susun bahan gambar dari AnalysisResult, lalu picu unduhan PNG.
 *
 * Mengembalikan Promise supaya pemanggil dapat menampilkan keadaan sibuk; `toBlob` asinkron
 * dan pada gambar seukuran ini benar-benar memakan beberapa puluh milidetik.
 */
export function unduhRingkasanPng(result, rentang, namaAspek) {
  const teratas = (result.aspect_aggregates ?? [])
    .filter((a) => a.negative_count > 0)
    .sort((a, b) => b.negative_count - a.negative_count)
    .map((a) => ({ label: namaAspek(a.aspect), count: a.negative_count }));

  const canvas = gambarRingkasan({
    total: result.summary.total_reviews,
    berkeluhan: result.summary.reviews_with_complaint ?? 0,
    rentang,
    teratas,
  });

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Gambar gagal dibuat di peramban ini."));
        return;
      }
      unduhBlob(blob, "ringkasan-ulasin.png");
      resolve();
    }, "image/png");
  });
}

/** Picu unduhan sebuah blob. Objek URL-nya dilepas setelah klik supaya tidak menahan memori. */
export function unduhBlob(blob, nama) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nama;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Pelepasan ditunda satu putaran: sebagian peramban membatalkan unduhan yang URL-nya
  // dicabut pada tick yang sama dengan kliknya.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Unduh objek apa pun sebagai berkas JSON ber-indentasi. */
export function unduhJson(data, nama) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  unduhBlob(blob, nama);
}
