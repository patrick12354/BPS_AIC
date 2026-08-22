/** Halaman pemasaran. Tidak memuat satu pun kontrol analisis - seluruh tombolnya bermuara
 *  ke satu tempat: dashboard. Pemisahan itu yang membuat halaman ini boleh panjang dan
 *  bersuara, sementara dashboard tetap pendek dan diam. */

import {
  Features,
  FootCta,
  Hero,
  HowItWorks,
  MarketplaceBand,
  SiteNav,
  Urgency,
  Value,
} from "../components/landing/index.js";
import { goTo } from "../lib/hooks.js";

export function LandingScreen({ theme, onToggleTheme }) {
  const start = () => goTo("dashboard");

  return (
    <>
      <SiteNav onStart={start} theme={theme} onToggleTheme={onToggleTheme} />
      <Hero onStart={start} />
      <MarketplaceBand />
      <Urgency />
      <HowItWorks />
      <Features />
      <Value />
      <FootCta onStart={start} />
    </>
  );
}
