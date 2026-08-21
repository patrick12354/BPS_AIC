/** Cangkang Ulasin.
 *
 * Dua permukaan yang benar-benar terpisah: halaman pemasaran di "#/" dan dashboard analisis
 * di "#/analisis". Berkas ini hanya memilih salah satunya, memegang tema, dan mengurus
 * transisi geser di antara keduanya.
 */

import { useEffect, useRef, useState } from "react";
import { FaqBot } from "./components/landing/FaqBot.jsx";
import { DashboardScreen } from "./screens/DashboardScreen.jsx";
import { LandingScreen } from "./screens/LandingScreen.jsx";
import { useRoute, useTheme } from "./lib/hooks.js";

export default function App() {
  const [theme, toggleTheme] = useTheme();
  const { route, direction } = useRoute();
  const frame = useRef(null);

  // Dashboard TIDAK dilepas saat pengguna kembali ke halaman pemasaran.
  //
  // Melepasnya berarti membuang hasil analisis yang sudah jadi - beserta keputusan Terima/Tolak
  // dan seluruh riwayat tanya jawab - hanya karena pengguna menekan logo untuk melihat sesuatu
  // sebentar. Analisis 66 ulasan memakan hampir satu menit, dan tidak ada yang disimpan di
  // server untuk dipulihkan (ADR-010, sesi tunggal). Jadi ia dipasang sekali lalu disembunyikan.
  //
  // Pemasangannya tetap ditunda sampai benar-benar dibuka, supaya pengunjung yang hanya membaca
  // halaman pemasaran tidak ikut menanggung biaya render dan panggilan /readiness-nya.
  const [dashboardPernahDibuka, setDashboardPernahDibuka] = useState(route === "dashboard");
  useEffect(() => {
    if (route === "dashboard") setDashboardPernahDibuka(true);
  }, [route]);

  useEffect(() => {
    // Berpindah permukaan berarti berganti halaman, jadi posisi gulir dimulai dari atas -
    // tanpa ini dashboard terbuka di tengah-tengah, sejauh halaman landing tergulir tadi.
    window.scrollTo({ top: 0, behavior: "auto" });

    // Animasi masuk dijalankan ulang dengan tangan, bukan lewat `key` yang memasang ulang
    // komponennya: pemasangan ulang itulah yang tadinya menghapus hasil analisis. Melepas
    // kelasnya lalu membaca `offsetWidth` memaksa reflow, dan itu yang membuat browser
    // memperlakukan pemasangan kelas berikutnya sebagai animasi baru.
    const el = frame.current;
    if (!el) return;
    el.classList.remove("route--in");
    void el.offsetWidth;
    el.classList.add("route--in");
  }, [route, direction]);

  return (
    <>
      {/* `hidden` DAN `inert` pada permukaan yang tidak aktif, bukan salah satunya.
        *
        * `hidden` bergantung pada `display: none` yang bisa dikalahkan aturan CSS mana pun -
        * dan permukaan ini punya kelas beranimasi (`.route--in`) plus lima berkas gaya yang
        * bebas menyentuh `display`. Sekali ada aturan yang menang, seluruh isi halaman yang
        * "tersembunyi" kembali masuk urutan tab: pengguna papan ketik di dashboard menekan
        * Tab dan fokusnya menghilang ke tombol-tombol halaman pemasaran yang tidak terlihat
        * di layar, tanpa cara menyadarinya selain kehilangan jejak kursor.
        *
        * `inert` tidak lewat CSS. Ia mencabut seluruh subtree dari urutan fokus, dari pohon
        * aksesibilitas, dan dari peristiwa penunjuk sekaligus - jadi kalaupun `display`-nya
        * bocor, isinya tetap tidak dapat dijangkau. Nilainya string kosong, bukan `true`:
        * React 18 menolak boolean pada atribut yang belum dikenalnya dan justru tidak
        * merendernya sama sekali.
        */}
      <div className="route route--in" ref={frame} data-dir={direction}>
        <div hidden={route !== "landing"} inert={route !== "landing" ? "" : undefined}>
          <LandingScreen theme={theme} onToggleTheme={toggleTheme} />
        </div>
        {dashboardPernahDibuka && (
          <div hidden={route !== "dashboard"} inert={route !== "dashboard" ? "" : undefined}>
            <DashboardScreen theme={theme} onToggleTheme={toggleTheme} />
          </div>
        )}
      </div>

      {/* Kotak FAQ berada DI LUAR `.route`, bukan di dalam LandingScreen tempat isinya
        * sebenarnya berasal.
        *
        * Alasannya aturan containing block: elemen yang sedang menganimasikan `transform`
        * atau `opacity` menjadi acuan posisi bagi keturunannya yang `position: fixed`.
        * `.route--in` menganimasikan keduanya selama 280ms tiap kali permukaan berganti -
        * dan selama jendela itu, tombol yang seharusnya menempel di sudut viewport justru
        * menempel di ujung bawah halaman, lalu melompat ke tempatnya begitu animasinya
        * usai. Dipasang di sini, ia tidak pernah punya leluhur yang beranimasi.
        *
        * Ia dipasang-lepas mengikuti rute, bukan disembunyikan seperti dashboard: yang
        * hilang saat dilepas cuma percakapan FAQ yang memang tidak sayang ditinggalkan. */}
      {route === "landing" && <FaqBot />}
    </>
  );
}
