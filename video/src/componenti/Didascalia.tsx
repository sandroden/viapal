import type React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { Posizione } from "../manifest";
import { colori, fontSans, fontSerif } from "../tema";

type Props = {
  readonly testo: string;
  /** occhiello sopra la didascalia (nome della scena) */
  readonly etichetta?: string;
  /** angolo della card: di norma in basso a sinistra */
  readonly posizione?: Posizione;
};

const MARGINE_X = 96;
const MARGINE_Y = 84;

// Coordinate CSS della card e verso da cui entra (dal bordo più vicino).
const ancoraggio = (p: Posizione): { stile: React.CSSProperties; daSopra: boolean } => {
  if (typeof p === "object") {
    return { stile: { ...p }, daSopra: p.top !== undefined && p.bottom === undefined };
  }
  const [v, o] = p.split("-");
  return {
    stile: {
      ...(v === "alto" ? { top: MARGINE_Y } : { bottom: MARGINE_Y }),
      ...(o === "dx" ? { right: MARGINE_X } : { left: MARGINE_X }),
    },
    daSopra: v === "alto",
  };
};

// Card crema con filetto terracotta, come le card dell'app; di norma in basso
// a sinistra, altrove se lì copre l'azione. Va messo dentro una <Sequence>
// lunga quanto la didascalia.
export const Didascalia: React.FC<Props> = ({ testo, etichetta, posizione = "basso-sx" }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const uscita = durationInFrames - 0.45 * fps;
  const { stile, daSopra } = ancoraggio(posizione);
  const segno = daSopra ? -1 : 1;

  return (
    <div
      style={{
        position: "absolute",
        ...stile,
        maxWidth: 1560,
        display: "flex",
        alignItems: "stretch",
        gap: 28,
        padding: "30px 48px 32px 32px",
        backgroundColor: colori.crema,
        border: `1px solid ${colori.bordo}`,
        borderRadius: 20,
        boxShadow: `0 4px 10px ${colori.ombra}, 0 22px 48px ${colori.ombra}`,
        opacity: interpolate(frame, [0, 0.5 * fps, uscita, durationInFrames], [0, 1, 1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: [Easing.bezier(0.16, 1, 0.3, 1), Easing.linear, Easing.bezier(0.7, 0, 0.84, 0)],
        }),
        translate: interpolate(
          frame,
          [0, 0.7 * fps, uscita, durationInFrames],
          [`0px ${28 * segno}px`, "0px 0px", "0px 0px", `0px ${10 * segno}px`],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: [Easing.bezier(0.16, 1, 0.3, 1), Easing.linear, Easing.bezier(0.7, 0, 0.84, 0)],
          },
        ),
      }}
    >
      <div
        style={{
          width: 6,
          borderRadius: 3,
          backgroundColor: colori.terracotta,
          flexShrink: 0,
        }}
      />
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {etichetta ? (
          <div
            style={{
              fontFamily: fontSans,
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: colori.terracotta,
            }}
          >
            {etichetta}
          </div>
        ) : null}
        <div
          style={{
            fontFamily: fontSerif,
            fontSize: 50,
            fontWeight: 400,
            lineHeight: 1.18,
            letterSpacing: "-0.005em",
            color: colori.inchiostro,
            // "\n" nel testo del manifest = a capo voluto (la card si stringe sulla riga più lunga)
            whiteSpace: "pre-line",
          }}
        >
          {testo}
        </div>
      </div>
    </div>
  );
};
