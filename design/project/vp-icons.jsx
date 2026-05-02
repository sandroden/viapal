/* global React */

// Viapal — shared icons & micro-illustrations
// Usage: <VPIcon name="home" size={20} />

const VP_ICONS = {
  home: 'M3 11.5L12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z',
  receipt: 'M5 3h14v18l-3-2-3 2-3-2-3 2-2-2zM8 8h8M8 12h8M8 16h5',
  bills: 'M4 6h16v12H4zM4 10h16M8 14h2',
  bell: 'M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4',
  camera: 'M4 8h3l2-3h6l2 3h3v11H4zM12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  plus: 'M12 5v14M5 12h14',
  check: 'M5 13l4 4L19 7',
  x: 'M6 6l12 12M18 6L6 18',
  arrow: 'M5 12h14M13 6l6 6-6 6',
  chevron: 'M9 6l6 6-6 6',
  back: 'M15 6l-6 6 6 6',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM16 16l5 5',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0',
  users: 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M16 3a4 4 0 0 1 0 8M22 21a7 7 0 0 0-5-6.7',
  doc: 'M6 3h9l5 5v13H6zM15 3v5h5',
  folder: 'M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  wallet: 'M3 7a2 2 0 0 1 2-2h13v3M3 7v11a2 2 0 0 0 2 2h15V11h-4a2 2 0 0 0 0 4h4',
  chart: 'M4 19V5M4 19h16M8 15v-4M12 15V8M16 15v-7',
  wrench: 'M14 4a5 5 0 0 0-5 6.5L4 15.5a2 2 0 0 0 2.8 2.8L11.5 14a5 5 0 1 0 2.5-10z',
  settings: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12c0 .5-.1 1-.2 1.4l2.1 1.6-2 3.4-2.4-1a7 7 0 0 1-2.4 1.4l-.4 2.6h-4l-.4-2.6a7 7 0 0 1-2.4-1.4l-2.4 1-2-3.4 2.1-1.6c-.1-.4-.2-.9-.2-1.4s.1-1 .2-1.4L3.5 9l2-3.4 2.4 1a7 7 0 0 1 2.4-1.4l.4-2.6h4l.4 2.6a7 7 0 0 1 2.4 1.4l2.4-1 2 3.4-2.1 1.6c.1.4.2.9.2 1.4z',
  leaf: 'M5 21c0-9 6-15 15-15-1 9-6 14-15 15zM5 21l8-8',
  message: 'M4 5h16v12H8l-4 4z',
  alert: 'M12 4l10 17H2zM12 10v5M12 18v.5',
  euro: 'M18 6a6 6 0 1 0 0 12M3 10h10M3 14h10',
  upload: 'M12 16V4M7 9l5-5 5 5M4 20h16',
  download: 'M12 4v12M7 11l5 5 5-5M4 20h16',
  clock: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 7v5l3 2',
  trend: 'M3 17l6-6 4 4 8-8M14 7h7v7',
  filter: 'M4 5h16l-6 8v6l-4-2v-4z',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
  contract: 'M6 3h9l5 5v10a3 3 0 0 1-3 3H6zM9 13h6M9 17h4M14 3v5h5',
  key: 'M14 8a4 4 0 1 0-3.5 5.9L4 20.5l2 2 1.5-1.5 2-2L11 17l3-3a4 4 0 0 0 0-6z',
  flame: 'M12 22c4 0 7-3 7-7 0-3-2-5-3-7 0 2-2 3-3 3 1-3-1-7-3-9 0 4-5 5-5 11 0 5 3 9 7 9z',
  drop: 'M12 3c-4 5-7 9-7 13a7 7 0 0 0 14 0c0-4-3-8-7-13z',
};

function VPIcon({ name, size = 20, color = 'currentColor', stroke = 1.6, fill, style = {} }) {
  const d = VP_ICONS[name];
  if (!d) return null;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={fill || 'none'}
      stroke={fill ? 'none' : color} strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }}>
      <path d={d} />
    </svg>
  );
}

// Micro-illustrazioni: tetto/foglia/busta/casa
function VPRoof({ size = 72, color = 'var(--vp-terra)' }) {
  return (
    <svg width={size} height={size * 0.7} viewBox="0 0 100 70" fill="none">
      <path d="M8 38 L50 8 L92 38" stroke={color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M22 32 V58 H78 V32" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" opacity="0.5"/>
      <rect x="44" y="40" width="12" height="18" stroke={color} strokeWidth="2" opacity="0.5"/>
    </svg>
  );
}

function VPLeaf({ size = 60, color = 'var(--vp-leaf)' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 60 60" fill="none">
      <path d="M10 50 C10 25, 25 10, 50 10 C45 35, 30 50, 10 50 Z" stroke={color} strokeWidth="2.2" strokeLinejoin="round"/>
      <path d="M10 50 L40 20" stroke={color} strokeWidth="1.5" opacity="0.6"/>
    </svg>
  );
}

function VPEnvelope({ size = 56, color = 'var(--vp-terra)' }) {
  return (
    <svg width={size} height={size * 0.72} viewBox="0 0 70 50" fill="none">
      <rect x="4" y="6" width="62" height="38" rx="3" stroke={color} strokeWidth="2.2"/>
      <path d="M4 10 L35 30 L66 10" stroke={color} strokeWidth="2.2" strokeLinecap="round"/>
    </svg>
  );
}

function VPHouse({ size = 64, color = 'var(--vp-terra)', accent = 'var(--vp-leaf)' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <path d="M8 32 L32 12 L56 32 V54 H8 Z" stroke={color} strokeWidth="2.4" strokeLinejoin="round"/>
      <rect x="26" y="38" width="12" height="16" stroke={color} strokeWidth="2"/>
      <circle cx="48" cy="22" r="5" stroke={accent} strokeWidth="2"/>
      <path d="M48 17 V14 M48 27 V30 M53 22 H56 M40 22 H43" stroke={accent} strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

// Avatar morbido — iniziale su sfondo terracotta variabile
function VPAvatar({ name = '', size = 36, hue = 38 }) {
  const initial = name.trim().charAt(0).toUpperCase() || '·';
  const bg = `oklch(0.86 0.05 ${hue})`;
  const fg = `oklch(0.40 0.08 ${hue})`;
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: bg, color: fg,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'var(--vp-font-display)', fontWeight: 500,
      fontSize: size * 0.45, flexShrink: 0,
    }}>{initial}</div>
  );
}

Object.assign(window, { VPIcon, VPRoof, VPLeaf, VPEnvelope, VPHouse, VPAvatar });
