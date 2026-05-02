/* global React */

// Viapal — Logo "Pappagallo nella casa"
// Silhouette di pappagallo + profilo casa + ramo con bacca.
// Costruito a forme geometriche pulite, scala da 16px a infinito.

// ── D · Solid (pappagallo pieno, su sfondo) ───────────────────
function LogoD({ size = 200, bird = '#8a4f2a', accent = '#6a7a3a', berry = '#3a2a1a',
                  bg = '#f3e8d0', stroke = '#3a2a1a', frame = true }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size}>
      {bg && <rect width="200" height="200" rx="44" fill={bg}/>}
      {/* profilo casa */}
      {frame && (
        <path d="M30 170 V90 L100 30 L170 90 V170 Z"
          fill="none" stroke={stroke} strokeWidth="6" strokeLinejoin="round"/>
      )}
      {/* ramo con foglie e bacca, in alto a destra */}
      <g>
        <path d="M132 60 q10 6 18 18" stroke={stroke} strokeWidth="2.4" fill="none" strokeLinecap="round"/>
        <ellipse cx="138" cy="58" rx="6" ry="3" transform="rotate(-25 138 58)" fill={accent}/>
        <ellipse cx="148" cy="68" rx="7" ry="3.4" transform="rotate(-10 148 68)" fill={accent}/>
        <circle cx="152" cy="80" r="3.6" fill={berry}/>
      </g>
      {/* pappagallo: testa tonda + corpo che cade verso il basso */}
      {/* corpo */}
      <path d="M58 158 C 58 116, 78 94, 108 94 C 124 94, 138 102, 144 116 C 138 130, 124 138, 108 140 C 96 142, 86 152, 80 162 Z"
        fill={bird}/>
      {/* petto più chiaro */}
      <path d="M70 158 C 72 134, 86 122, 102 124 C 108 132, 104 144, 92 150 C 84 154, 74 158, 70 158 Z"
        fill={bird} opacity="0.55"/>
      {/* testa */}
      <circle cx="108" cy="86" r="26" fill={bird}/>
      {/* "guancia" più chiara */}
      <circle cx="102" cy="92" r="14" fill={bird} opacity="0.5"/>
      {/* occhio */}
      <circle cx="114" cy="82" r="4.2" fill={stroke}/>
      <circle cx="115.4" cy="80.8" r="1.2" fill="#fff" opacity="0.7"/>
      {/* becco curvo a destra */}
      <path d="M130 88 Q 152 86, 152 100 Q 142 106, 132 100 Q 130 96, 130 88 Z" fill="#d4a560"/>
      <path d="M132 100 Q 140 104, 148 100" stroke={stroke} strokeWidth="1.4" fill="none" opacity="0.5"/>
    </svg>
  );
}

// ── E · Outline (più "stencil", scala benissimo piccola) ─────
function LogoE({ size = 200, color = '#3a2a1a', accent = '#6a7a3a',
                  bg = 'transparent', strokeW = 5 }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size}>
      {bg !== 'transparent' && <rect width="200" height="200" rx="44" fill={bg}/>}
      {/* casa */}
      <path d="M30 170 V90 L100 30 L170 90 V170 Z"
        fill="none" stroke={color} strokeWidth={strokeW} strokeLinejoin="round" strokeLinecap="round"/>
      {/* pappagallo silhouette piena dentro */}
      <g>
        {/* corpo (goccia) */}
        <path d="M62 158 C 60 118, 80 96, 110 96 C 128 96, 142 106, 146 122 C 138 138, 122 144, 104 144 C 92 146, 82 154, 76 164 Z"
          fill={color}/>
        {/* testa */}
        <circle cx="110" cy="88" r="22" fill={color}/>
        {/* occhio (negativo) */}
        <circle cx="116" cy="84" r="3.6" fill="#fff"/>
        <circle cx="116.4" cy="83.4" r="1.6" fill={color}/>
        {/* becco */}
        <path d="M130 90 Q 150 88, 150 102 Q 140 108, 130 102 Z" fill={accent}/>
      </g>
      {/* ramo */}
      <g>
        <path d="M134 64 q12 4 20 16" stroke={color} strokeWidth="2.4" fill="none" strokeLinecap="round"/>
        <ellipse cx="140" cy="62" rx="5.5" ry="2.8" transform="rotate(-25 140 62)" fill={accent}/>
        <ellipse cx="150" cy="72" rx="6.5" ry="3" transform="rotate(-10 150 72)" fill={accent}/>
        <circle cx="154" cy="82" r="3" fill={color}/>
      </g>
    </svg>
  );
}

// ── F · Reverse / monocromatico (per app icon scura) ────────
function LogoF({ size = 200, fg = '#f3e8d0', bg = '#3a4a26' }) {
  return (
    <svg viewBox="0 0 200 200" width={size} height={size}>
      <rect width="200" height="200" rx="44" fill={bg}/>
      {/* casa stroke */}
      <path d="M34 170 V92 L100 34 L166 92 V170 Z"
        fill="none" stroke={fg} strokeWidth="5" strokeLinejoin="round"/>
      {/* pappagallo */}
      <path d="M64 158 C 62 118, 82 98, 110 98 C 128 98, 142 108, 146 122 C 138 136, 122 142, 104 142 C 92 144, 82 152, 76 162 Z"
        fill={fg}/>
      <circle cx="110" cy="90" r="22" fill={fg}/>
      <circle cx="116" cy="86" r="3.4" fill={bg}/>
      <path d="M130 92 Q 150 90, 150 104 Q 140 108, 130 104 Z" fill={fg}/>
      <path d="M134 66 q12 4 20 16" stroke={fg} strokeWidth="2.4" fill="none" strokeLinecap="round"/>
      <ellipse cx="142" cy="64" rx="5.5" ry="2.8" transform="rotate(-25 142 64)" fill={fg}/>
      <ellipse cx="152" cy="74" rx="6.5" ry="3" transform="rotate(-10 152 74)" fill={fg}/>
      <circle cx="155" cy="84" r="3" fill={fg}/>
    </svg>
  );
}

window.LogoD = LogoD;
window.LogoE = LogoE;
window.LogoF = LogoF;
