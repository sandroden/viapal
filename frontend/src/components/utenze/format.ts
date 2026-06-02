// Helper presentazionali per la feature "bollette/conguaglio utenze".
// Nessuna logica di business: solo formattazione + mappatura visiva
// (colore + icona) per tipo di utenza. I numeri arrivano dallo store.

import { useFormatoEuro } from 'src/composables/useFormatoEuro';

const { formattaEuro } = useFormatoEuro();

// Formattatore Euro: riusa quello dell'app (it-IT, simbolo in coda).
export function eur(n: number | string | null | undefined): string {
  return formattaEuro(n);
}

export type TipoUtenza = 'Luce' | 'Gas' | 'TARI';

export interface UtilityStyle {
  icon: string;
  fg: string;
  soft: string;
  bar: string;
}

// Identità visiva per tipo utenza. Le chiavi combaciano con TipoUtenza.
//   fg = testo/accento · soft = riempimento header · bar = segmento grafico
export const UTILITY: Record<TipoUtenza, UtilityStyle> = {
  Luce: { icon: 'bolt', fg: 'oklch(0.50 0.10 78)', soft: 'oklch(0.93 0.05 82)', bar: 'oklch(0.72 0.105 78)' },
  Gas: { icon: 'flame', fg: 'oklch(0.46 0.07 250)', soft: 'oklch(0.93 0.035 250)', bar: 'oklch(0.62 0.08 250)' },
  TARI: { icon: 'trash', fg: 'oklch(0.42 0.055 150)', soft: 'oklch(0.90 0.03 150)', bar: 'oklch(0.58 0.055 150)' },
};

const UTILITY_FALLBACK: UtilityStyle = {
  icon: 'bolt',
  fg: 'var(--vp-ink-2)',
  soft: 'var(--vp-paper-2)',
  bar: 'var(--vp-wood)',
};

export function utility(tipo: string): UtilityStyle {
  return UTILITY[tipo as TipoUtenza] ?? UTILITY_FALLBACK;
}

export const TIPI_UTENZA: TipoUtenza[] = ['Luce', 'Gas', 'TARI'];

// prodotto del backend (luce/gas/...) → etichetta canonica del design.
export function prodottoToTipo(prodotto: string): string {
  const p = (prodotto || '').toLowerCase();
  if (p === 'luce') return 'Luce';
  if (p === 'gas') return 'Gas';
  if (p === 'tari') return 'TARI';
  return prodotto;
}

// voce di totali_per_voce (luce/gas/tari) → etichetta canonica.
export function voceToTipo(voce: string): string {
  return prodottoToTipo(voce);
}

export type Criterio = 'teste' | 'mq' | 'giorni';

export interface CriterioDef {
  id: Criterio;
  titolo: string;
  sub: string;
  icon: string;
}

// Criteri di ripartizione. Il backend implementa SOLO 'giorni' (pro-rata):
// gli altri sono mostrati ma disabilitati (vedi `criteriAttivi`).
export const CRITERI: CriterioDef[] = [
  { id: 'teste', titolo: 'A testa', sub: 'Stessa quota per tutti', icon: 'users' },
  { id: 'mq', titolo: 'Per stanza', sub: 'In base ai m² della camera', icon: 'home' },
  { id: 'giorni', titolo: 'Pro-rata giorni', sub: 'Solo i giorni di presenza', icon: 'clock' },
];

export const CRITERI_ATTIVI: Criterio[] = ['giorni'];

export function criterioFrase(c: Criterio): string {
  return (
    {
      teste: 'a testa',
      mq: 'per m² di stanza',
      giorni: 'sui giorni di effettiva presenza',
    }[c] || ''
  );
}

const MESI = [
  'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
  'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre',
];

// 'YYYY-MM-DD' → mese minuscolo ('marzo'); robusto anche su Date ISO.
export function meseDa(isoDate: string): string {
  const m = Number((isoDate || '').slice(5, 7));
  return MESI[m - 1] ?? '';
}

export function meseCapitalize(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

export function annoDa(isoDate: string): string {
  return (isoDate || '').slice(0, 4);
}

// 'YYYY-MM-DD' → 'dd/mm'
function ggMM(isoDate: string): string {
  const d = (isoDate || '').slice(8, 10);
  const m = (isoDate || '').slice(5, 7);
  return `${d}/${m}`;
}

export function rangePeriodo(da: string, a: string): string {
  return `${ggMM(da)} – ${ggMM(a)}`;
}

// ── Tipi "view" consumati dai componenti presentazionali ────────────────

export interface ScontrinoData {
  tipo: string;
  fornitore: string;
  importo: number;
  periodo: string;
  consumo: string;
  riferimento: string;
}

export interface PeriodoView {
  id: string;
  mese: string; // minuscolo, usato nel titolo
  label: string; // 'Marzo 2026'
  range: string; // '01/03 – 31/03'
  stato: 'inviato' | 'da-inviare' | 'incompleto';
  presenti: number;
  attese: number;
}

export interface BollettaView extends ScontrinoData {
  // tipo / fornitore / importo / periodo / consumo / riferimento da ScontrinoData
  pdfUrl?: string | null;
}

export interface VoceView {
  tipo: string; // 'Luce' | 'Gas' | 'TARI'
  importo: number;
}

export interface QuotaView {
  id: string | number;
  receivableId?: number | null; // id del Receivable (per escludere dall'invio)
  nome: string;
  stanza: string;
  email: string;
  mq: number;
  giorni: number;
  avatarHue: number;
  per: Record<string, number>; // { Luce, Gas, TARI }
  quota: number;
  oggetto?: string;
  corpo?: string;
  notificare?: boolean; // false = inquilino uscito, non si invia
  bonifico?: BonificoView | null;
}

export interface BonificoView {
  beneficiario: string;
  iban: string;
  causale: string;
  importo: number;
}

// Tinta deterministica (0–360) per l'avatar, derivata dal nome.
export function avatarHue(nome: string): number {
  let h = 0;
  for (let i = 0; i < nome.length; i++) {
    h = (h * 31 + nome.charCodeAt(i)) % 360;
  }
  return h;
}
