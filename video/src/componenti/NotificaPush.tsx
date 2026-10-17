import type React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { fontSans } from "../tema";

type Props = {
  readonly titolo: string;
  readonly corpo: string;
  /** nome dell'app nell'intestazione della notifica */
  readonly app?: string;
  /** tempo relativo accanto al nome dell'app */
  readonly quando?: string;
};

// Palette neutra da notifica di sistema (Android/Chrome in tema chiaro):
// volutamente estranea ai colori dell'app, perché si legga come un avviso
// del telefono che arriva *sopra* Viapal.
const sistema = {
  sfondo: "#f7f7f9",
  bordo: "rgba(0, 0, 0, 0.07)",
  titolo: "#1b1b1f",
  corpo: "#44464f",
  tenue: "#74777f",
  ombra: "rgba(10, 12, 20, 0.22)",
} as const;

const MARGINE = 22;

// Notifica push simulata in alto a destra: scivola dentro dall'alto, resta e
// esce verso destra. Va messa dentro una <Sequence> lunga quanto deve restare.
export const NotificaPush: React.FC<Props> = ({ titolo, corpo, app = "Viapal", quando = "ora" }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const uscita = durationInFrames - 0.4 * fps;
  const morbida = Easing.bezier(0.16, 1, 0.3, 1);
  const via = Easing.bezier(0.7, 0, 0.84, 0);

  return (
    <div
      style={{
        position: "absolute",
        top: MARGINE,
        right: MARGINE,
        width: 620,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: "18px 26px 20px 22px",
        backgroundColor: sistema.sfondo,
        border: `1px solid ${sistema.bordo}`,
        borderRadius: 28,
        boxShadow: `0 2px 6px ${sistema.ombra}, 0 18px 44px ${sistema.ombra}`,
        fontFamily: fontSans,
        opacity: interpolate(frame, [0, 0.3 * fps, uscita, durationInFrames], [0, 1, 1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: [morbida, Easing.linear, via],
        }),
        translate: interpolate(
          frame,
          [0, 0.55 * fps, uscita, durationInFrames],
          ["0px -150px", "0px 0px", "0px 0px", "120px 0px"],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: [morbida, Easing.linear, via],
          },
        ),
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Img
          src={staticFile("viapal.png")}
          style={{ width: 34, height: 34, borderRadius: 9, objectFit: "cover" }}
        />
        <div style={{ fontSize: 21, fontWeight: 500, color: sistema.corpo }}>{app}</div>
        <div style={{ fontSize: 21, color: sistema.tenue }}>· {quando}</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingLeft: 2 }}>
        <div style={{ fontSize: 27, fontWeight: 600, lineHeight: 1.25, color: sistema.titolo }}>
          {titolo}
        </div>
        <div style={{ fontSize: 24, fontWeight: 400, lineHeight: 1.3, color: sistema.corpo }}>
          {corpo}
        </div>
      </div>
    </div>
  );
};
