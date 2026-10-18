// Telefono disegnato in CSS che entra dal basso sopra la clip, con la
// schermata di blocco su cui arriva la notifica push di Viapal: lo schermo si
// accende, il telefono vibra, la notifica resta il tempo di leggerla e il
// telefono esce. Tutti i testi arrivano dal manifest (`notifiche`, stile
// "telefono"); qui restano solo l'aspetto e i tempi dell'animazione.
import type React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import type { LatoNotifica } from "../manifest";
import { colori, fontSans } from "../tema";

type Props = {
  readonly titolo: string;
  readonly corpo: string;
  /** ora grande della schermata di blocco, es. "10:42" */
  readonly ora?: string;
  /** data sopra l'ora, es. "sabato 17 ottobre" */
  readonly data?: string;
  /** cartellino accanto al telefono, es. "Sul telefono del proprietario" */
  readonly etichetta?: string;
  /** bordo dello schermo a cui sta il telefono */
  readonly lato?: LatoNotifica;
  /** distanza in px del bordo alto del telefono dal bordo alto del video, a riposo */
  readonly alto?: number;
  /** nome dell'app nell'intestazione della notifica */
  readonly app?: string;
  /** tempo relativo accanto al nome dell'app */
  readonly quando?: string;
};

// Proporzioni di un telefono attuale (~9:19,5).
const LARGHEZZA = 460;
const ALTEZZA = Math.round((LARGHEZZA * 19.5) / 9);
const CORNICE = 13;
const RAGGIO = 66;
const MARGINE_LATO = 130;

/** secondi: entrata, arrivo della notifica, uscita (dalla fine) */
const ENTRATA = 0.7;
const ARRIVO = 0.95;
const USCITA = 0.5;

// Palette da notifica di sistema in tema chiaro, volutamente neutra: si legge
// come un avviso del telefono, non come un pezzo dell'app.
const sistema = {
  card: "rgba(248, 245, 241, 0.94)",
  titolo: "#1b1b1f",
  corpo: "#3f4148",
  tenue: "#6f7179",
} as const;

// Sfondo della schermata di blocco: caldo e sobrio, scuro quanto basta perché
// ora e data bianche si leggano.
const sfondoBlocco = [
  "radial-gradient(ellipse 90% 55% at 30% 18%, oklch(0.55 0.07 50 / 0.55) 0%, transparent 70%)",
  "radial-gradient(ellipse 80% 50% at 85% 80%, oklch(0.48 0.08 35 / 0.45) 0%, transparent 70%)",
  "linear-gradient(165deg, oklch(0.40 0.055 48) 0%, oklch(0.30 0.045 40) 55%, oklch(0.21 0.03 35) 100%)",
].join(", ");

const IconeStato: React.FC = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
    {/* segnale */}
    <svg width="22" height="16" viewBox="0 0 22 16">
      {[0, 1, 2, 3].map((i) => (
        <rect key={i} x={i * 6} y={12 - i * 4} width="4" height={4 + i * 4} rx="1" fill="white" />
      ))}
    </svg>
    {/* wi-fi */}
    <svg width="20" height="16" viewBox="0 0 20 16">
      <path d="M10 15.5 L6.6 11.6 A5 5 0 0 1 13.4 11.6 Z" fill="white" />
      <path
        d="M3.6 8.6 A9 9 0 0 1 16.4 8.6"
        stroke="white"
        strokeWidth="2.2"
        fill="none"
        strokeLinecap="round"
      />
      <path
        d="M0.9 5.4 A13 13 0 0 1 19.1 5.4"
        stroke="white"
        strokeWidth="2.2"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
    {/* batteria */}
    <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
      <div
        style={{
          width: 27,
          height: 14,
          padding: 2,
          border: "1.5px solid rgba(255,255,255,0.85)",
          borderRadius: 4,
        }}
      >
        <div style={{ width: "72%", height: "100%", borderRadius: 1.5, backgroundColor: "white" }} />
      </div>
      <div style={{ width: 2, height: 5, borderRadius: 1, backgroundColor: "rgba(255,255,255,0.85)" }} />
    </div>
  </div>
);

// Scorciatoie in basso nella schermata di blocco (torcia e fotocamera).
const Scorciatoia: React.FC<{ readonly lato: "sinistra" | "destra" }> = ({ lato }) => (
  <div
    style={{
      position: "absolute",
      bottom: 46,
      [lato === "sinistra" ? "left" : "right"]: 40,
      width: 58,
      height: 58,
      borderRadius: "50%",
      backgroundColor: "rgba(255,255,255,0.14)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    }}
  >
    {lato === "sinistra" ? (
      <svg width="24" height="26" viewBox="0 0 24 26">
        <path d="M6 2 H18 V7 L15 11 V24 H9 V11 L6 7 Z" fill="none" stroke="white" strokeWidth="1.8" strokeLinejoin="round" />
        <circle cx="12" cy="16" r="1.6" fill="white" />
      </svg>
    ) : (
      <svg width="26" height="22" viewBox="0 0 26 22">
        <path
          d="M2 6 H7 L9 3 H17 L19 6 H24 V20 H2 Z"
          fill="none"
          stroke="white"
          strokeWidth="1.8"
          strokeLinejoin="round"
        />
        <circle cx="13" cy="12.5" r="4.2" fill="none" stroke="white" strokeWidth="1.8" />
      </svg>
    )}
  </div>
);

const Notifica: React.FC<{
  readonly titolo: string;
  readonly corpo: string;
  readonly app: string;
  readonly quando: string;
  readonly style: React.CSSProperties;
}> = ({ titolo, corpo, app, quando, style }) => (
  <div
    style={{
      margin: "0 14px",
      padding: "18px 22px 22px 20px",
      display: "flex",
      flexDirection: "column",
      gap: 10,
      backgroundColor: sistema.card,
      borderRadius: 30,
      boxShadow: "0 6px 18px rgba(0,0,0,0.18)",
      ...style,
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
      <Img
        src={staticFile("viapal.png")}
        style={{ width: 36, height: 36, borderRadius: 10, objectFit: "cover" }}
      />
      <div style={{ fontSize: 22, fontWeight: 500, color: sistema.corpo }}>{app}</div>
      <div style={{ fontSize: 22, color: sistema.tenue }}>· {quando}</div>
    </div>
    <div style={{ display: "flex", flexDirection: "column", gap: 5, paddingLeft: 2 }}>
      {/* come Android: titolo e corpo troncati con "…" oltre poche righe */}
      <div
        style={{
          fontSize: 30,
          fontWeight: 600,
          lineHeight: 1.22,
          letterSpacing: "-0.005em",
          color: sistema.titolo,
          display: "-webkit-box",
          WebkitBoxOrient: "vertical",
          WebkitLineClamp: 2,
          overflow: "hidden",
        }}
      >
        {titolo}
      </div>
      <div
        style={{
          fontSize: 26,
          fontWeight: 400,
          lineHeight: 1.3,
          color: sistema.corpo,
          display: "-webkit-box",
          WebkitBoxOrient: "vertical",
          WebkitLineClamp: 3,
          overflow: "hidden",
        }}
      >
        {corpo}
      </div>
    </div>
  </div>
);

// Va messo dentro una <Sequence> lunga quanto il telefono deve restare in
// scena: entra, ~1 s dopo arriva la notifica, esce negli ultimi 0,5 s.
export const TelefonoNotifica: React.FC<Props> = ({
  titolo,
  corpo,
  ora,
  data,
  etichetta,
  lato = "destra",
  alto = 300,
  app = "Viapal",
  quando = "ora",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, height } = useVideoConfig();
  const morbida = Easing.bezier(0.16, 1, 0.3, 1);
  const via = Easing.bezier(0.7, 0, 0.84, 0);
  const verso = lato === "destra" ? 1 : -1;
  const arrivo = ARRIVO * fps;
  const uscita = durationInFrames - USCITA * fps;
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

  // Vibrazione all'arrivo: due colpi brevi che si smorzano.
  const dopoArrivo = frame - arrivo;
  const colpo = (inizio: number, durata: number) =>
    interpolate(dopoArrivo, [inizio * fps, (inizio + durata) * fps], [1, 0], clamp) *
    (dopoArrivo >= inizio * fps ? 1 : 0);
  const ampiezza = colpo(0, 0.28) + colpo(0.38, 0.24);
  const tremito = Math.sin(dopoArrivo * 2.6) * ampiezza;

  return (
    <>
      {etichetta ? (
        <div
          style={{
            position: "absolute",
            top: alto + 120,
            [lato === "destra" ? "right" : "left"]: MARGINE_LATO + LARGHEZZA + 34,
            display: "flex",
            alignItems: "center",
            gap: 14,
            padding: "14px 24px 14px 20px",
            backgroundColor: colori.crema,
            border: `1px solid ${colori.bordo}`,
            borderRadius: 16,
            boxShadow: `0 3px 8px ${colori.ombra}, 0 14px 32px ${colori.ombra}`,
            fontFamily: fontSans,
            fontSize: 24,
            fontWeight: 600,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: colori.terracotta,
            whiteSpace: "nowrap",
            opacity: interpolate(
              frame,
              [0.45 * fps, 0.85 * fps, uscita - 0.1 * fps, uscita + 0.25 * fps],
              [0, 1, 1, 0],
              { ...clamp, easing: [morbida, Easing.linear, via] },
            ),
            translate: interpolate(
              frame,
              [0.45 * fps, 0.95 * fps],
              [`${verso * 24}px 0px`, "0px 0px"],
              { ...clamp, easing: morbida },
            ),
          }}
        >
          <div
            style={{ width: 6, height: 26, borderRadius: 3, backgroundColor: colori.terracotta }}
          />
          {etichetta}
        </div>
      ) : null}

      <div
        style={{
          position: "absolute",
          top: alto,
          [lato === "destra" ? "right" : "left"]: MARGINE_LATO,
          width: LARGHEZZA,
          height: ALTEZZA,
          translate: interpolate(
            frame,
            [0, ENTRATA * fps, uscita, durationInFrames],
            [`${verso * 160}px ${height - alto + 60}px`, "0px 0px", "0px 0px", `${verso * 60}px ${height - alto + 60}px`],
            { ...clamp, easing: [morbida, Easing.linear, via] },
          ),
          rotate: `${
            interpolate(
              frame,
              [0, ENTRATA * fps],
              [verso * 9, verso * -2],
              { ...clamp, easing: morbida },
            ) + tremito * 1.3
          }deg`,
        }}
      >
        {/* tasti laterali */}
        <div
          style={{
            position: "absolute",
            right: -4,
            top: 230,
            width: 6,
            height: 110,
            borderRadius: 3,
            backgroundColor: colori.corniceFilo,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: -4,
            top: 200,
            width: 6,
            height: 70,
            borderRadius: 3,
            backgroundColor: colori.corniceFilo,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: -4,
            top: 290,
            width: 6,
            height: 70,
            borderRadius: 3,
            backgroundColor: colori.corniceFilo,
          }}
        />

        {/* scocca */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            padding: CORNICE,
            backgroundColor: colori.cornice,
            border: `2px solid ${colori.corniceFilo}`,
            borderRadius: RAGGIO,
            boxShadow: [
              "inset 0 0 0 2px oklch(0.15 0.008 50)",
              "0 10px 24px oklch(0.25 0.03 45 / 0.28)",
              "0 40px 90px oklch(0.25 0.03 45 / 0.34)",
            ].join(", "),
          }}
        >
          {/* schermo */}
          <div
            style={{
              position: "relative",
              width: "100%",
              height: "100%",
              overflow: "hidden",
              borderRadius: RAGGIO - CORNICE,
              background: sfondoBlocco,
              fontFamily: fontSans,
              color: "white",
            }}
          >
            {/* foro della fotocamera */}
            <div
              style={{
                position: "absolute",
                top: 15,
                left: "50%",
                width: 20,
                height: 20,
                marginLeft: -10,
                borderRadius: "50%",
                backgroundColor: "#0b0b0c",
                boxShadow: "inset 0 0 0 2px #1d1d20",
                zIndex: 2,
              }}
            />
            {/* barra di stato */}
            <div
              style={{
                height: 50,
                padding: "0 32px",
                display: "flex",
                alignItems: "center",
                justifyContent: "flex-end",
              }}
            >
              <IconeStato />
            </div>

            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginTop: 22 }}>
              {data ? (
                <div
                  style={{
                    fontSize: 27,
                    fontWeight: 500,
                    letterSpacing: "0.01em",
                    color: "rgba(255,255,255,0.88)",
                  }}
                >
                  {data}
                </div>
              ) : null}
              {ora ? (
                <div
                  style={{
                    fontSize: 124,
                    fontWeight: 500,
                    lineHeight: 1,
                    letterSpacing: "-0.035em",
                    marginTop: 6,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {ora}
                </div>
              ) : null}
            </div>

            <Notifica
              titolo={titolo}
              corpo={corpo}
              app={app}
              quando={quando}
              style={{
                marginTop: 32,
                opacity: interpolate(frame, [arrivo, arrivo + 0.3 * fps], [0, 1], clamp),
                translate: interpolate(frame, [arrivo, arrivo + 0.45 * fps], ["0px -36px", "0px 0px"], {
                  ...clamp,
                  easing: morbida,
                }),
                scale: interpolate(frame, [arrivo, arrivo + 0.45 * fps], [0.94, 1], {
                  ...clamp,
                  easing: morbida,
                }),
              }}
            />

            <Scorciatoia lato="sinistra" />
            <Scorciatoia lato="destra" />
            {/* indicatore home */}
            <div
              style={{
                position: "absolute",
                bottom: 12,
                left: "50%",
                width: 150,
                height: 5,
                marginLeft: -75,
                borderRadius: 3,
                backgroundColor: "rgba(255,255,255,0.75)",
              }}
            />

            {/* schermo spento finché non arriva la notifica (solo l'always-on) */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                backgroundColor: "black",
                opacity: interpolate(frame, [arrivo - 0.05 * fps, arrivo + 0.2 * fps], [0.78, 0], clamp),
              }}
            />
            {/* riflesso del vetro */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                background:
                  "linear-gradient(125deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.03) 28%, transparent 45%)",
              }}
            />
          </div>
        </div>
      </div>
    </>
  );
};
