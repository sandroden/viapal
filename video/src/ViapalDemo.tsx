import { Audio } from "@remotion/media";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";
import React from "react";
import { AbsoluteFill, interpolate, staticFile, useVideoConfig } from "remotion";
import { Apertura, Chiusura, Sezione } from "./componenti/Cartelli";
import { CheCose, Passaggio, Viste } from "./componenti/Introduzione";
import { Scena } from "./componenti/Scena";
import { manifest } from "./manifest";
import { colori } from "./tema";
import { type Blocco, blocchiIntroduzione, costruisciBlocchi, musicaDisponibile } from "./timeline";

const contenutoBlocco = (b: Blocco) => {
  switch (b.tipo) {
    case "apertura":
      return (
        <Apertura titolo={manifest.apertura.titolo} sottotitolo={manifest.apertura.sottotitolo} />
      );
    case "cheCose":
      return (
        <CheCose
          titolo={manifest.introduzione.cheCose.titolo}
          sottotitolo={manifest.introduzione.cheCose.sottotitolo}
        />
      );
    case "viste":
      return (
        <Viste
          proprietario={manifest.introduzione.viste.proprietario}
          inquilino={manifest.introduzione.viste.inquilino}
        />
      );
    case "passaggio":
      return <Passaggio testo={manifest.introduzione.passaggio.testo} />;
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
    case "cheCose":
      return "Intro · Che cos'è";
    case "viste":
      return "Intro · Le due viste";
    case "passaggio":
      return "Intro · Passaggio";
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

// Blocchi in fila con una dissolvenza fra l'uno e l'altro.
const Montaggio: React.FC<{ readonly blocchi: readonly Blocco[] }> = ({ blocchi }) => {
  const transizione = linearTiming({ durationInFrames: manifest.transizioneFotogrammi });
  return (
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
  );
};

export const ViapalDemo: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: colori.carta }}>
      <Montaggio blocchi={costruisciBlocchi(manifest, fps)} />
      {musicaDisponibile ? <Musica /> : null}
    </AbsoluteFill>
  );
};

/** Solo l'introduzione, per rivederla nella cartella "Cartelli" dello Studio. */
export const IntroduzioneDemo: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: colori.carta }}>
      <Montaggio blocchi={blocchiIntroduzione(manifest, fps)} />
    </AbsoluteFill>
  );
};
