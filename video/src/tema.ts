// Colori e caratteri presi dall'app (frontend/src/css/tokens.css, --vp-*).
import { loadFont as caricaSerif } from "@remotion/google-fonts/SourceSerif4";
import { loadFont as caricaGeist } from "@remotion/google-fonts/Geist";

export const colori = {
  /** sfondo dell'app (--vp-paper) */
  carta: "#f8efe6",
  /** sfondo del logo: i cartelli lo usano perché il logo vi si fonda */
  lino: "#f4e6d3",
  /** card primaria (--vp-cream) */
  crema: "oklch(0.985 0.008 80)",
  bordo: "oklch(0.91 0.022 75)",
  inchiostro: "oklch(0.26 0.022 50)",
  inchiostro2: "oklch(0.42 0.020 55)",
  inchiostro3: "oklch(0.58 0.018 60)",
  inchiostro4: "oklch(0.72 0.016 68)",
  terracotta: "#9b5a3a",
  terracottaTenue: "oklch(0.88 0.045 40)",
  ombra: "oklch(0.30 0.02 50 / 0.16)",
  /** dispositivi disegnati nell'introduzione: cornice scura calda, base chiara */
  cornice: "oklch(0.23 0.010 50)",
  corniceFilo: "oklch(0.36 0.012 50)",
  baseChiara: "oklch(0.87 0.008 70)",
  baseScura: "oklch(0.70 0.010 60)",
} as const;

export const { fontFamily: fontSerif } = caricaSerif("normal", {
  weights: ["400", "600"],
  subsets: ["latin", "latin-ext"],
});

export const { fontFamily: fontSans } = caricaGeist("normal", {
  weights: ["400", "500", "600"],
  subsets: ["latin", "latin-ext"],
});
