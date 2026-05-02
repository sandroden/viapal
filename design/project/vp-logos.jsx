/* global React */

// Viapal — Logo da intarsio del pappagallo
// Tre direzioni di stilizzazione, dalla più figurativa alla più astratta.

// ── A · Linea continua (più fedele) ──────────────────────────
// Pappagallo + arcata + ramo, single-weight outline,
// sembra un bollo / timbro / ex-libris.
function LogoA({ size = 200, color = 'var(--vp-terra)', accent = 'var(--vp-leaf)', bg = 'transparent' }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size}>
      {bg !== 'transparent' && <rect width="200" height="200" rx="44" fill={bg}/>}
      {/* arcata */}
      <path d="M40 170 V92 a60 60 0 0 1 120 0 V170"
        fill="none" stroke={color} strokeWidth="3.5" strokeLinecap="round"/>
      {/* ramo decorativo dentro l'arcata, dietro il pappagallo */}
      <g stroke={accent} strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" opacity="0.85">
        <path d="M70 60 q10 -10 22 -8"/>
        <path d="M130 56 q12 -2 20 6"/>
        <path d="M150 78 q6 14 -2 26"/>
        <path d="M62 88 q-2 14 6 24"/>
        {/* foglie */}
        <path d="M80 50 q-6 -2 -10 4 q4 4 10 0 z" fill={accent}/>
        <path d="M138 48 q8 0 12 6 q-6 4 -12 -2 z" fill={accent}/>
        <path d="M156 90 q4 6 0 14 q-6 -2 -4 -12 z" fill={accent}/>
        <path d="M58 102 q-4 6 0 14 q6 -2 4 -12 z" fill={accent}/>
        {/* bacche */}
        <circle cx="78" cy="62" r="2.4" fill={accent} stroke="none"/>
        <circle cx="142" cy="60" r="2.4" fill={accent} stroke="none"/>
        <circle cx="68" cy="80" r="1.8" fill={accent} stroke="none"/>
      </g>
      {/* pappagallo */}
      <g fill="none" stroke={color} strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
        {/* testa */}
        <circle cx="118" cy="78" r="14"/>
        <circle cx="120" cy="76" r="2.2" fill={color}/>
        {/* becco */}
        <path d="M132 80 q6 0 6 6 q-4 2 -8 -2 z" fill={color}/>
        {/* corpo */}
        <path d="M104 88 q-12 14 -8 36 q4 16 18 18 q14 -2 18 -16 q4 -22 -8 -38"/>
        {/* ala */}
        <path d="M108 100 q-2 14 4 28 q-12 -4 -14 -18 q0 -8 10 -10 z" fill={color} opacity="0.18"/>
        {/* coda strisce */}
        <path d="M104 120 q-4 22 0 36" />
        <path d="M112 122 q-2 22 2 36" />
        <path d="M118 122 q-1 22 1 36" />
        {/* zampe */}
        <path d="M118 142 v8 m-3 0 l-3 4 m6 -4 l3 4" />
      </g>
      {/* fiore in basso */}
      <g fill={color} opacity="0.85">
        <circle cx="68" cy="142" r="5"/>
        <circle cx="76" cy="138" r="5"/>
        <circle cx="78" cy="146" r="5"/>
        <circle cx="70" cy="150" r="5"/>
        <circle cx="73" cy="143" r="2" fill={accent}/>
      </g>
    </svg>
  );
}

// ── B · Geometrico (livello "icon stamp") ────────────────────
// Pappagallo ridotto a forme primarie: cerchio testa, goccia corpo,
// 3 strisce coda. Più moderno, scala benissimo.
function LogoB({ size = 200, color = 'var(--vp-terra)', accent = 'var(--vp-leaf)', bg = 'transparent' }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size}>
      {bg !== 'transparent' && <rect width="200" height="200" rx="44" fill={bg}/>}
      {/* arcata */}
      <path d="M44 168 V96 a56 56 0 0 1 112 0 V168"
        fill="none" stroke={color} strokeWidth="4" strokeLinejoin="round"/>
      {/* foglie minimali */}
      <g fill={accent}>
        <ellipse cx="62" cy="74" rx="6" ry="11" transform="rotate(-30 62 74)"/>
        <ellipse cx="138" cy="74" rx="6" ry="11" transform="rotate(30 138 74)"/>
        <ellipse cx="58" cy="110" rx="5" ry="10" transform="rotate(-50 58 110)"/>
        <ellipse cx="142" cy="110" rx="5" ry="10" transform="rotate(50 142 110)"/>
        <circle cx="76" cy="62" r="2.4"/>
        <circle cx="124" cy="62" r="2.4"/>
      </g>
      {/* pappagallo: corpo a goccia */}
      <path d="M100 70 c-22 0 -34 18 -34 38 c0 22 14 38 34 38 c20 0 34 -16 34 -38 c0 -20 -12 -38 -34 -38 z"
        fill={color}/>
      {/* coda 3 strisce */}
      <g>
        <rect x="84"  y="138" width="6" height="28" rx="3" fill={color}/>
        <rect x="94"  y="140" width="6" height="30" rx="3" fill={accent}/>
        <rect x="104" y="138" width="6" height="28" rx="3" fill={color}/>
      </g>
      {/* testa è già parte del corpo: occhio + becco */}
      <circle cx="108" cy="82" r="3.2" fill="var(--vp-paper)"/>
      <path d="M120 86 q8 2 6 10 q-6 0 -10 -4 z" fill={color}/>
    </svg>
  );
}

// ── C · Astratto (monogramma + foglia) ───────────────────────
// La V di Viapal scolpita come becco-foglia. Il più "serio",
// funziona a 16px come favicon.
function LogoC({ size = 200, color = 'var(--vp-terra)', accent = 'var(--vp-leaf)', bg = 'transparent' }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size}>
      {bg !== 'transparent' && <rect width="200" height="200" rx="44" fill={bg}/>}
      {/* arcata */}
      <path d="M50 170 V104 a50 50 0 0 1 100 0 V170"
        fill="none" stroke={color} strokeWidth="4" strokeLinejoin="round" opacity="0.55"/>
      {/* V intarsiata, con becco a destra */}
      <path d="M62 76 L100 156 L138 76 q8 -4 12 4 q-4 4 -12 4 z"
        fill={color}/>
      {/* foglia che esce dalla V */}
      <path d="M100 140 C 86 120, 80 96, 92 78 C 108 92, 110 118, 100 140 Z"
        fill={accent}/>
      <path d="M100 140 L96 100" stroke={color} strokeWidth="1.5" opacity="0.5"/>
      {/* occhio del pappagallo (puntino) */}
      <circle cx="142" cy="80" r="3" fill={color}/>
    </svg>
  );
}

window.LogoA = LogoA;
window.LogoB = LogoB;
window.LogoC = LogoC;
