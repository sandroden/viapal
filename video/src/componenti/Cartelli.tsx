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
import { colori, fontSans, fontSerif } from "../tema";

// Entrata morbida dal basso, sfalsata di `ritardo` secondi.
export const useSalita = (ritardo: number, distanza = 26): React.CSSProperties => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opzioni = {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  } as const;
  return {
    opacity: interpolate(frame, [ritardo * fps, (ritardo + 0.9) * fps], [0, 1], opzioni),
    translate: interpolate(
      frame,
      [ritardo * fps, (ritardo + 1.1) * fps],
      [`0px ${distanza}px`, "0px 0px"],
      opzioni,
    ),
  };
};

export const Filetto: React.FC<{ readonly style?: React.CSSProperties }> = ({ style }) => (
  <div
    style={{
      width: 72,
      height: 4,
      borderRadius: 2,
      backgroundColor: colori.terracotta,
      ...style,
    }}
  />
);

export const sfondoCartello: React.CSSProperties = {
  backgroundColor: colori.lino,
  backgroundImage: `radial-gradient(ellipse at 50% 42%, ${colori.lino} 0%, ${colori.lino} 45%, oklch(0.91 0.03 70) 100%)`,
  alignItems: "center",
  justifyContent: "center",
};

type AperturaProps = {
  readonly titolo: string;
  readonly sottotitolo: string;
};

export const Apertura: React.FC<AperturaProps> = ({ titolo, sottotitolo }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const logo = useSalita(0.1, 16);
  const testo = useSalita(0.7);
  const sotto = useSalita(1.3);

  return (
    <AbsoluteFill style={sfondoCartello}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          scale: interpolate(frame, [0, durationInFrames], [1, 1.025], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <Img src={staticFile("viapal.png")} style={{ width: 340, height: 344, ...logo }} />
        <div
          style={{
            marginTop: 36,
            fontFamily: fontSerif,
            fontSize: 96,
            fontWeight: 400,
            letterSpacing: "-0.015em",
            lineHeight: 1.08,
            color: colori.inchiostro,
            textAlign: "center",
            ...testo,
          }}
        >
          {titolo}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 24, marginTop: 34, ...sotto }}>
          <Filetto style={{ width: 48, height: 3 }} />
          <div
            style={{
              fontFamily: fontSans,
              fontSize: 38,
              fontWeight: 400,
              color: colori.inchiostro2,
            }}
          >
            {sottotitolo}
          </div>
          <Filetto style={{ width: 48, height: 3 }} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

type ChiusuraProps = {
  readonly titolo: string;
  readonly contatto: string;
};

export const Chiusura: React.FC<ChiusuraProps> = ({ titolo, contatto }) => {
  const logo = useSalita(0.1, 16);
  const testo = useSalita(0.4);
  const riga = useSalita(1.0);

  return (
    <AbsoluteFill style={sfondoCartello}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <Img src={staticFile("viapal.png")} style={{ width: 220, height: 223, ...logo }} />
        <div
          style={{
            marginTop: 40,
            fontFamily: fontSerif,
            fontSize: 120,
            fontWeight: 400,
            letterSpacing: "-0.02em",
            lineHeight: 1.05,
            color: colori.inchiostro,
            ...testo,
          }}
        >
          {titolo}
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 30,
            marginTop: 40,
            ...riga,
          }}
        >
          <Filetto />
          <div
            style={{
              fontFamily: fontSans,
              fontSize: 46,
              fontWeight: 500,
              letterSpacing: "0.01em",
              color: colori.terracotta,
            }}
          >
            {contatto}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

type SezioneProps = {
  readonly titolo: string;
  readonly contenuto?: readonly string[];
};

export const Sezione: React.FC<SezioneProps> = ({ titolo, contenuto }) => {
  const filetto = useSalita(0.05, 0);
  const testo = useSalita(0.15, 20);
  const elenco = useSalita(0.4, 14);

  return (
    <AbsoluteFill style={{ ...sfondoCartello, backgroundImage: undefined, backgroundColor: colori.carta }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 34 }}>
        <Filetto style={filetto} />
        <div
          style={{
            fontFamily: fontSerif,
            fontSize: 108,
            fontWeight: 400,
            letterSpacing: "-0.015em",
            color: colori.inchiostro,
            ...testo,
          }}
        >
          {titolo}
        </div>
        {contenuto && contenuto.length > 0 ? (
          <div
            style={{
              fontFamily: fontSans,
              fontSize: 34,
              color: colori.inchiostro3,
              letterSpacing: "0.01em",
              ...elenco,
            }}
          >
            {contenuto.join(" · ")}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
