import { Video } from "@remotion/media";
import type React from "react";
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { ScenaRisolta } from "../timeline";
import { colori, fontSans, fontSerif } from "../tema";
import { Didascalia } from "./Didascalia";
import { NotificaPush } from "./NotificaPush";

type Props = {
  readonly risolta: ScenaRisolta;
};

const Clip: React.FC<Props> = ({ risolta }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const { zoom } = risolta;

  return (
    <AbsoluteFill
      style={{
        transformOrigin: zoom?.origine,
        scale: zoom
          ? interpolate(frame, [0, durationInFrames], [zoom.da, zoom.a], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.inOut(Easing.sin),
            })
          : undefined,
      }}
    >
      <Video
        name={risolta.scena.clip}
        src={staticFile(`clips/${risolta.scena.clip}`)}
        trimBefore={risolta.trimBefore}
        playbackRate={risolta.velocita}
        muted
        objectFit="cover"
        style={{ width: "100%", height: "100%" }}
      />
    </AbsoluteFill>
  );
};

// Finché la clip non c'è: titolo della scena e "clip in arrivo".
const Segnaposto: React.FC<Props> = ({ risolta }) => {
  const { scena } = risolta;
  return (
    <AbsoluteFill
      style={{
        backgroundColor: colori.carta,
        backgroundImage: `radial-gradient(${colori.bordo} 1.4px, transparent 1.4px)`,
        backgroundSize: "28px 28px",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 26,
          padding: "72px 120px 64px",
          marginBottom: 120,
          backgroundColor: colori.carta,
          border: `2px dashed ${colori.terracottaTenue}`,
          borderRadius: 28,
        }}
      >
        <div
          style={{
            fontFamily: fontSans,
            fontSize: 26,
            fontWeight: 600,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: colori.terracotta,
          }}
        >
          Scena {scena.id}
        </div>
        <div
          style={{
            fontFamily: fontSerif,
            fontSize: 112,
            lineHeight: 1.05,
            color: colori.inchiostro,
          }}
        >
          {scena.titolo}
        </div>
        <div
          style={{
            fontFamily: fontSans,
            fontSize: 34,
            color: colori.inchiostro2,
          }}
        >
          clip in arrivo
          <span style={{ color: colori.inchiostro4 }}> · </span>
          <span style={{ fontFamily: "monospace", fontSize: 28, color: colori.inchiostro3 }}>
            clips/{scena.clip}
          </span>
        </div>
        {scena.nota ? (
          <div
            style={{
              fontFamily: fontSans,
              fontSize: 26,
              color: colori.inchiostro3,
              maxWidth: 1100,
              textAlign: "center",
            }}
          >
            {scena.nota}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export const Scena: React.FC<Props> = ({ risolta }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: colori.carta, overflow: "hidden" }}>
      {risolta.disponibile ? <Clip risolta={risolta} /> : <Segnaposto risolta={risolta} />}
      {risolta.didascalie.map((d) => (
        <Sequence key={`${d.da}-${d.testo}`} name={d.testo} from={d.da} durationInFrames={d.durata}>
          <Didascalia testo={d.testo} etichetta={risolta.scena.titolo} posizione={d.posizione} />
        </Sequence>
      ))}
      {risolta.notifiche.map((n) => (
        <Sequence key={`notifica-${n.da}`} name={`Notifica · ${n.titolo}`} from={n.da} durationInFrames={n.durata}>
          <NotificaPush titolo={n.titolo} corpo={n.corpo} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
