import { Audio } from "@remotion/media";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import React from "react";
import { AbsoluteFill, interpolate, staticFile, useVideoConfig } from "remotion";
import { Apertura, Chiusura, Sezione } from "./componenti/Cartelli";
import { Scena } from "./componenti/Scena";
import { manifest } from "./manifest";
import { colori } from "./tema";
import { type Blocco, costruisciBlocchi, musicaDisponibile } from "./timeline";

const contenutoBlocco = (b: Blocco) => {
  switch (b.tipo) {
    case "apertura":
      return (
        <Apertura titolo={manifest.apertura.titolo} sottotitolo={manifest.apertura.sottotitolo} />
      );
    case "chiusura":
      return <Chiusura titolo={manifest.chiusura.titolo} contatto={manifest.chiusura.contatto} />;
    case "sezione":
      return <Sezione titolo={b.titolo} contenuto={b.contenuto} />;
    case "scena":
      return <Scena risolta={b.risolta} />;
  }
};

const nomeBlocco = (b: Blocco) => {
  switch (b.tipo) {
    case "apertura":
      return "Apertura";
    case "chiusura":
      return "Chiusura";
    case "sezione":
      return `Sezione · ${b.titolo}`;
    case "scena":
      return `${b.risolta.scena.id} · ${b.risolta.scena.titolo}${b.risolta.disponibile ? "" : " (segnaposto)"}`;
  }
};

// Traccia musicale opzionale: entra solo se esiste public/musica.mp3
// (rilancia `npm run clips` dopo averla aggiunta).
const Musica: React.FC = () => {
  const { fps, durationInFrames } = useVideoConfig();
  const { file, volume, dissolvenzaEntrata, dissolvenzaUscita } = manifest.musica;
  return (
    <Audio
      name="Musica"
      src={staticFile(file)}
      loop
      volume={(f) =>
        interpolate(
          f,
          [0, dissolvenzaEntrata * fps, durationInFrames - dissolvenzaUscita * fps, durationInFrames],
          [0, volume, volume, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      }
    />
  );
};

export const ViapalDemo: React.FC = () => {
  const { fps } = useVideoConfig();
  const blocchi = costruisciBlocchi(manifest, fps);
  const transizione = linearTiming({ durationInFrames: manifest.transizioneFotogrammi });

  return (
    <AbsoluteFill style={{ backgroundColor: colori.carta }}>
      <TransitionSeries name="Montaggio">
        {blocchi.map((b, i) => (
          <React.Fragment key={b.chiave}>
            {i > 0 ? (
              <TransitionSeries.Transition presentation={fade()} timing={transizione} />
            ) : null}
            <TransitionSeries.Sequence name={nomeBlocco(b)} durationInFrames={b.durata}>
              {contenutoBlocco(b)}
            </TransitionSeries.Sequence>
          </React.Fragment>
        ))}
      </TransitionSeries>
      {musicaDisponibile ? <Musica /> : null}
    </AbsoluteFill>
  );
};
