// Introduzione fra l'apertura e la prima sezione: che cos'è Viapal, le due
// viste (proprietario e inquilino) e la frase-ponte. Tutti i testi e le
// immagini arrivano dal manifest (`introduzione`).
import type React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { Introduzione, Vista } from "../manifest";
import { colori, fontSans, fontSerif } from "../tema";
import { Filetto, sfondoCartello, useSalita } from "./Cartelli";

// ── Che cos'è ────────────────────────────────────────────────────────────────

type CheCoseProps = Omit<Introduzione["cheCose"], "durata">;

export const CheCose: React.FC<CheCoseProps> = ({ titolo, sottotitolo }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const filetto = useSalita(0.1, 0);
  const testo = useSalita(0.25, 22);
  const sotto = useSalita(0.9, 16);

  return (
    <AbsoluteFill style={sfondoCartello}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 44,
          maxWidth: 1600,
          scale: interpolate(frame, [0, durationInFrames], [1, 1.02], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <Filetto style={filetto} />
        <div
          style={{
            fontFamily: fontSerif,
            fontSize: 92,
            fontWeight: 400,
            letterSpacing: "-0.015em",
            lineHeight: 1.12,
            color: colori.inchiostro,
            textAlign: "center",
            // "\n" nel manifest = a capo voluto
            whiteSpace: "pre-line",
            ...testo,
          }}
        >
          {titolo}
        </div>
        {sottotitolo ? (
          <div
            style={{
              fontFamily: fontSans,
              fontSize: 40,
              fontWeight: 400,
              color: colori.inchiostro2,
              textAlign: "center",
              ...sotto,
            }}
          >
            {sottotitolo}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ── Dispositivi ──────────────────────────────────────────────────────────────

const ombraDispositivo = `0 10px 22px ${colori.ombra}, 0 36px 70px ${colori.ombra}`;

const Schermo: React.FC<{
  readonly immagine: string;
  readonly larghezza: number;
  readonly altezza: number;
  readonly raggio: number;
}> = ({ immagine, larghezza, altezza, raggio }) => (
  <div
    style={{
      width: larghezza,
      height: altezza,
      borderRadius: raggio,
      overflow: "hidden",
      backgroundColor: colori.carta,
    }}
  >
    <Img
      src={staticFile(immagine)}
      style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top center" }}
    />
  </div>
);

// Portatile: coperchio scuro con lo schermo 16:9 e base chiara più larga.
const SCHERMO_PORTATILE = { larghezza: 768, altezza: 432 } as const;
const CORNICE_PORTATILE = 16;
const SPORGENZA_BASE = 50;

const Portatile: React.FC<{ readonly immagine: string }> = ({ immagine }) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
    <div
      style={{
        position: "relative",
        padding: `${CORNICE_PORTATILE + 4}px ${CORNICE_PORTATILE}px ${CORNICE_PORTATILE + 6}px`,
        backgroundColor: colori.cornice,
        border: `1.5px solid ${colori.corniceFilo}`,
        borderBottom: "none",
        borderRadius: "22px 22px 4px 4px",
        boxShadow: ombraDispositivo,
      }}
    >
      {/* fotocamera */}
      <div
        style={{
          position: "absolute",
          top: 7,
          left: "50%",
          width: 7,
          height: 7,
          marginLeft: -3.5,
          borderRadius: "50%",
          backgroundColor: colori.corniceFilo,
        }}
      />
      <Schermo immagine={immagine} {...SCHERMO_PORTATILE} raggio={4} />
    </div>
    <div
      style={{
        position: "relative",
        width: SCHERMO_PORTATILE.larghezza + 2 * (CORNICE_PORTATILE + SPORGENZA_BASE),
        height: 22,
        background: `linear-gradient(to bottom, ${colori.baseChiara} 0%, ${colori.baseChiara} 45%, ${colori.baseScura} 100%)`,
        borderRadius: "3px 3px 22px 22px / 3px 3px 14px 14px",
        boxShadow: `0 14px 28px ${colori.ombra}, 0 3px 6px ${colori.ombra}`,
      }}
    >
      {/* incavo per aprire il coperchio */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: "50%",
          width: 150,
          height: 8,
          marginLeft: -75,
          borderRadius: "0 0 10px 10px",
          backgroundColor: colori.baseScura,
          opacity: 0.55,
        }}
      />
    </div>
  </div>
);

// Tablet orizzontale: cornice scura uniforme, fotocamera sul lato corto.
const SCHERMO_TABLET = { larghezza: 608, altezza: 372 } as const;
const CORNICE_TABLET = 22;

const Tablet: React.FC<{ readonly immagine: string }> = ({ immagine }) => (
  <div
    style={{
      position: "relative",
      padding: CORNICE_TABLET,
      backgroundColor: colori.cornice,
      border: `1.5px solid ${colori.corniceFilo}`,
      borderRadius: 34,
      boxShadow: ombraDispositivo,
    }}
  >
    <div
      style={{
        position: "absolute",
        left: 8,
        top: "50%",
        width: 7,
        height: 7,
        marginTop: -3.5,
        borderRadius: "50%",
        backgroundColor: colori.corniceFilo,
      }}
    />
    <Schermo immagine={immagine} {...SCHERMO_TABLET} raggio={10} />
  </div>
);

// ── Le due viste ─────────────────────────────────────────────────────────────

/** secondi fra una voce e la successiva */
const PASSO_VOCI = 0.4;

const Voce: React.FC<{ readonly testo: string; readonly ritardo: number }> = ({ testo, ritardo }) => {
  const salita = useSalita(ritardo, 14);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 20, ...salita }}>
      <div
        style={{
          width: 11,
          height: 11,
          borderRadius: "50%",
          backgroundColor: colori.terracotta,
          flexShrink: 0,
        }}
      />
      <div
        style={{
          fontFamily: fontSans,
          fontSize: 38,
          fontWeight: 400,
          lineHeight: 1.25,
          color: colori.inchiostro2,
        }}
      >
        {testo}
      </div>
    </div>
  );
};

// coperchio (schermo + cornici + filo) e base del portatile, il più alto dei due
const ALTEZZA_DISPOSITIVI = SCHERMO_PORTATILE.altezza + 2 * CORNICE_PORTATILE + 10 + 2 + 22;

const Colonna: React.FC<{
  readonly vista: Vista;
  readonly dispositivo: "portatile" | "tablet";
  /** secondi: quando entra il dispositivo; titolo e voci seguono */
  readonly inizio: number;
  /** rientro del testo rispetto al bordo sinistro della colonna */
  readonly rientro: number;
}> = ({ vista, dispositivo, inizio, rientro }) => {
  const entrata = useSalita(inizio, 40);
  const titolo = useSalita(inizio + 0.4, 18);

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        style={{
          height: ALTEZZA_DISPOSITIVI,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "center",
          ...entrata,
        }}
      >
        {dispositivo === "portatile" ? (
          <Portatile immagine={vista.immagine} />
        ) : (
          <Tablet immagine={vista.immagine} />
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", paddingLeft: rientro, marginTop: 64 }}>
        <div
          style={{
            fontFamily: fontSerif,
            fontSize: 66,
            fontWeight: 400,
            letterSpacing: "-0.01em",
            lineHeight: 1.1,
            color: colori.inchiostro,
            ...titolo,
          }}
        >
          {vista.titolo}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 30 }}>
          {vista.voci.map((v, i) => (
            <Voce key={v} testo={v} ritardo={inizio + 0.85 + i * PASSO_VOCI} />
          ))}
        </div>
      </div>
    </div>
  );
};

type VisteProps = Omit<Introduzione["viste"], "durata">;

export const Viste: React.FC<VisteProps> = ({ proprietario, inquilino }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  // l'inquilino entra quando il lato proprietario ha finito le sue voci
  const inizioInquilino = 0.15 + 0.85 + proprietario.voci.length * PASSO_VOCI + 0.2;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: colori.carta,
        backgroundImage: `radial-gradient(ellipse at 50% 35%, ${colori.carta} 0%, ${colori.carta} 50%, oklch(0.92 0.025 70) 100%)`,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          gap: 130,
          scale: interpolate(frame, [0, durationInFrames], [1, 1.02], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.inOut(Easing.sin),
          }),
        }}
      >
        <Colonna
          vista={proprietario}
          dispositivo="portatile"
          inizio={0.15}
          rientro={SPORGENZA_BASE}
        />
        <Colonna vista={inquilino} dispositivo="tablet" inizio={inizioInquilino} rientro={0} />
      </div>
    </AbsoluteFill>
  );
};

// ── Passaggio ────────────────────────────────────────────────────────────────

type PassaggioProps = Omit<Introduzione["passaggio"], "durata">;

// Stesso fondo del cartello di sezione. La frase sale ed esce verso l'alto
// prima della dissolvenza, così non si sovrappone al titolo della sezione.
export const Passaggio: React.FC<PassaggioProps> = ({ testo }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const salita = useSalita(0.05, 20);
  const uscita = [durationInFrames - 0.75 * fps, durationInFrames - 0.3 * fps];
  return (
    <AbsoluteFill style={{ ...sfondoCartello, backgroundImage: undefined, backgroundColor: colori.carta }}>
      <div
        style={{
          opacity: interpolate(frame, uscita, [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.7, 0, 0.84, 0),
          }),
          translate: interpolate(frame, uscita, ["0px 0px", "0px -18px"], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.7, 0, 0.84, 0),
          }),
        }}
      >
        <div
          style={{
            fontFamily: fontSerif,
            fontSize: 100,
            fontWeight: 400,
            letterSpacing: "-0.015em",
            color: colori.inchiostro,
            ...salita,
          }}
        >
          {testo}
        </div>
      </div>
    </AbsoluteFill>
  );
};
