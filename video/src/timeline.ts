// Traduce il manifest (secondi) in blocchi del montaggio (fotogrammi).
import clipsDisponibili from "./clips-disponibili.json";
import {
  manifest,
  type LatoNotifica,
  type Manifest,
  type Notifica,
  type Posizione,
  type Scena,
  type StileNotifica,
  type Zoom,
} from "./manifest";

export const FPS = 30;
export const LARGHEZZA = 1920;
export const ALTEZZA = 1080;

type InfoClip = { readonly durata: number | null };
const clips: Record<string, InfoClip | undefined> = clipsDisponibili.clips;

export const musicaDisponibile: boolean = clipsDisponibili.musica;

export type DidascaliaFotogrammi = {
  readonly testo: string;
  readonly da: number;
  readonly durata: number;
  readonly posizione: Posizione;
};

export type NotificaFotogrammi = Omit<Notifica, "da" | "a" | "stile" | "lato"> & {
  readonly stile: StileNotifica;
  readonly lato: LatoNotifica;
  readonly da: number;
  readonly durata: number;
};

export type ScenaRisolta = {
  readonly scena: Scena;
  readonly disponibile: boolean;
  /** fotogramma della sorgente da cui partire */
  readonly trimBefore: number;
  readonly velocita: number;
  readonly durata: number;
  readonly zoom: Required<Zoom> | null;
  readonly didascalie: readonly DidascaliaFotogrammi[];
  readonly notifiche: readonly NotificaFotogrammi[];
};

export type Blocco =
  | { readonly tipo: "apertura"; readonly chiave: string; readonly durata: number }
  | { readonly tipo: "chiusura"; readonly chiave: string; readonly durata: number }
  | { readonly tipo: "cheCose"; readonly chiave: string; readonly durata: number }
  | { readonly tipo: "viste"; readonly chiave: string; readonly durata: number }
  | { readonly tipo: "passaggio"; readonly chiave: string; readonly durata: number }
  | {
      readonly tipo: "sezione";
      readonly chiave: string;
      readonly durata: number;
      readonly titolo: string;
      /** titoli delle scene del gruppo, fino alla sezione successiva */
      readonly contenuto: readonly string[];
    }
  | {
      readonly tipo: "scena";
      readonly chiave: string;
      readonly durata: number;
      readonly risolta: ScenaRisolta;
    };

const DURATA_SEGNAPOSTO_PREDEFINITA = 8;

const secondiInFotogrammi = (s: number, fps: number) => Math.round(s * fps);

const risolviZoom = (scena: Scena, m: Manifest): Required<Zoom> | null => {
  if (scena.zoom === false) return null;
  const base = m.zoomPredefinito === false ? null : m.zoomPredefinito;
  const proprio = typeof scena.zoom === "object" ? scena.zoom : null;
  if (!base && !proprio) return null;
  return {
    da: proprio?.da ?? base?.da ?? 1,
    a: proprio?.a ?? base?.a ?? 1.04,
    origine: proprio?.origine ?? base?.origine ?? "50% 50%",
  };
};

export const risolviScena = (scena: Scena, m: Manifest = manifest, fps = FPS): ScenaRisolta => {
  const info = clips[scena.clip];
  const disponibile = info !== undefined;
  const velocita = scena.velocita ?? 1;
  const inizio = scena.inizio ?? 0;
  // Un segnaposto si comporta come una clip lunga `durataPrevista`.
  const lunghezzaSorgente = (disponibile ? info.durata : null) ??
    scena.durataPrevista ??
    DURATA_SEGNAPOSTO_PREDEFINITA;
  const fine = Math.min(scena.fine ?? lunghezzaSorgente, disponibile && info.durata ? info.durata : Infinity);
  const minimo = m.transizioneFotogrammi * 2 + 1;
  const durata = Math.max(minimo, Math.floor(((fine - inizio) * fps) / velocita));

  // secondi della clip tagliata (sul tempo sorgente) → fotogrammi del montaggio
  const intervallo = (da: number, a: number) => {
    const inizioF = Math.max(0, Math.round((da * fps) / velocita));
    return { da: inizioF, durata: Math.min(durata, Math.round((a * fps) / velocita)) - inizioF };
  };

  const didascalie = scena.didascalie
    .map((d) => ({ testo: d.testo, ...intervallo(d.da, d.a), posizione: d.posizione ?? "basso-sx" }))
    .filter((d) => d.durata > 0);

  const notifiche = (scena.notifiche ?? [])
    .map(({ da, a, stile, lato, ...resto }) => ({
      ...resto,
      stile: stile ?? "telefono",
      lato: lato ?? "destra",
      ...intervallo(da, a),
    }))
    .filter((n) => n.durata > 0);

  return {
    scena,
    disponibile,
    trimBefore: secondiInFotogrammi(inizio, fps),
    velocita,
    durata,
    zoom: risolviZoom(scena, m),
    didascalie,
    notifiche,
  };
};

/** I tre cartelli dell'introduzione, fra l'apertura e la prima sezione. */
export const blocchiIntroduzione = (m: Manifest = manifest, fps = FPS): Blocco[] => {
  const { cheCose, viste, passaggio } = m.introduzione;
  return [
    { tipo: "cheCose", chiave: "intro-checose", durata: secondiInFotogrammi(cheCose.durata, fps) },
    { tipo: "viste", chiave: "intro-viste", durata: secondiInFotogrammi(viste.durata, fps) },
    { tipo: "passaggio", chiave: "intro-passaggio", durata: secondiInFotogrammi(passaggio.durata, fps) },
  ];
};

export const costruisciBlocchi = (m: Manifest = manifest, fps = FPS): Blocco[] => {
  const blocchi: Blocco[] = [
    { tipo: "apertura", chiave: "apertura", durata: secondiInFotogrammi(m.apertura.durata, fps) },
    ...blocchiIntroduzione(m, fps),
  ];
  m.scene.forEach((scena, i) => {
    if (scena.sezione) {
      const successiva = m.scene.findIndex((s, j) => j > i && s.sezione);
      blocchi.push({
        tipo: "sezione",
        chiave: `sezione-${scena.id}`,
        durata: secondiInFotogrammi(m.durataSezione, fps),
        titolo: scena.sezione,
        // una scena spezzata in più tagli (03a/03b) compare una volta sola
        contenuto: [
          ...new Set(m.scene.slice(i, successiva === -1 ? undefined : successiva).map((s) => s.titolo)),
        ],
      });
    }
    const risolta = risolviScena(scena, m, fps);
    blocchi.push({ tipo: "scena", chiave: `scena-${scena.id}`, durata: risolta.durata, risolta });
  });
  blocchi.push({
    tipo: "chiusura",
    chiave: "chiusura",
    durata: secondiInFotogrammi(m.chiusura.durata, fps),
  });
  return blocchi;
};

/** Somma dei blocchi meno le sovrapposizioni delle dissolvenze. */
export const durataBlocchi = (blocchi: readonly Blocco[], m: Manifest = manifest): number => {
  const somma = blocchi.reduce((tot, b) => tot + b.durata, 0);
  return somma - (blocchi.length - 1) * m.transizioneFotogrammi;
};

export const durataTotale = (m: Manifest = manifest, fps = FPS): number =>
  durataBlocchi(costruisciBlocchi(m, fps), m);
