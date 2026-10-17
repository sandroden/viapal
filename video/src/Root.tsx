import type React from "react";
import { Composition, Folder } from "remotion";
import { Apertura, Chiusura, Sezione } from "./componenti/Cartelli";
import { Scena } from "./componenti/Scena";
import { manifest } from "./manifest";
import { ALTEZZA, FPS, LARGHEZZA, durataTotale, risolviScena } from "./timeline";
import { ViapalDemo } from "./ViapalDemo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ViapalDemo"
        component={ViapalDemo}
        durationInFrames={durataTotale(manifest, FPS)}
        fps={FPS}
        width={LARGHEZZA}
        height={ALTEZZA}
      />
      <Folder name="Cartelli">
        <Composition
          id="Apertura"
          component={Apertura}
          durationInFrames={manifest.apertura.durata * FPS}
          fps={FPS}
          width={LARGHEZZA}
          height={ALTEZZA}
          defaultProps={{
            titolo: manifest.apertura.titolo,
            sottotitolo: manifest.apertura.sottotitolo,
          }}
        />
        <Composition
          id="Sezione"
          component={Sezione}
          durationInFrames={manifest.durataSezione * FPS}
          fps={FPS}
          width={LARGHEZZA}
          height={ALTEZZA}
          defaultProps={{
            titolo: "I soldi",
            contenuto: ["Riconciliazione", "Ritardi e solleciti", "Spese e conto economico"],
          }}
        />
        <Composition
          id="Chiusura"
          component={Chiusura}
          durationInFrames={manifest.chiusura.durata * FPS}
          fps={FPS}
          width={LARGHEZZA}
          height={ALTEZZA}
          defaultProps={{
            titolo: manifest.chiusura.titolo,
            contatto: manifest.chiusura.contatto,
          }}
        />
      </Folder>
      {/* Una composizione per scena, generata dal manifest, per rivederle da sole. */}
      <Folder name="Scene">
        {manifest.scene.map((scena) => {
          const risolta = risolviScena(scena, manifest, FPS);
          return (
            <Composition
              key={scena.id}
              id={`Scena-${scena.id}`}
              component={Scena}
              durationInFrames={risolta.durata}
              fps={FPS}
              width={LARGHEZZA}
              height={ALTEZZA}
              defaultProps={{ risolta }}
            />
          );
        })}
      </Folder>
    </>
  );
};
