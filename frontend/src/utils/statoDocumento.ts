import type { QVueGlobals } from 'quasar';
import type { DocumentoFE } from 'stores/documenti';
import type {
  PaginaDocumento,
  StatoDocumento,
  StatoFirma,
  VoceFascicolo,
} from 'stores/fascicolo';

/** Colori e icona di uno stato del fascicolo. Il vocabolario visivo è unico:
 *  la stessa voce ha lo stesso colore nel fascicolo dell'inquilino e nella
 *  scheda del proprietario. */
export interface StileStato {
  dot: string;
  bg: string;
  fg: string;
  label: string;
  icona: string;
}

export const STILI_STATO: Record<StatoDocumento, StileStato> = {
  ok: {
    dot: 'var(--vp-sage)',
    bg: 'var(--vp-sage-soft)',
    fg: 'var(--vp-status-ok-fg)',
    label: 'valido',
    icona: 'check_circle',
  },
  scadenza: {
    dot: 'var(--vp-honey)',
    bg: 'var(--vp-honey-soft)',
    fg: 'var(--vp-status-wait-fg)',
    label: 'in scadenza',
    icona: 'schedule',
  },
  scaduto: {
    dot: 'var(--vp-clay)',
    bg: 'var(--vp-clay-soft)',
    fg: 'var(--vp-status-late-fg)',
    label: 'scaduto',
    icona: 'error_outline',
  },
};

/** Tipi che si caricano in due pagine: il modulo propone fronte e retro. */
export const TIPI_FRONTE_RETRO = ['carta_identita', 'permesso_soggiorno'];

/** Tipi che si firmano a più mani: i file sono versioni, non pagine.
 *  Duplicata da ``TenantDocument.TIPI_FIRMATI``: serve al foglio di
 *  caricamento, che deve chiedere lo stato prima che il file esista. */
export const TIPI_FIRMATI = ['atto_subentro_locazione', 'cessione_fabbricato'];

/** Gli stati che si possono scegliere, nell'ordine del giro di firme.
 *  Le etichette sono le stesse del backend (``get_stato_firma_display``). */
export const STATI_FIRMA: { value: Exclude<StatoFirma, ''>; label: string }[] = [
  { value: 'bozza', label: 'bozza' },
  { value: 'firmata_proprieta', label: 'firmata dalla proprietà' },
  { value: 'definitiva', label: 'definitiva' },
];

/** Colori del badge di firma. Volutamente lontani da quelli delle scadenze
 *  (miele, argilla): una bozza non è un problema, è un passo. */
export const STILI_FIRMA: Record<StatoFirma, Omit<StileStato, 'icona'>> = {
  // Fondo paper-3 e non paper-2: il visore affiancato è paper-2, e lì la
  // pillola sparirebbe lasciando solo pallino e testo.
  '': {
    dot: 'var(--vp-ink-4)',
    bg: 'var(--vp-paper-3)',
    fg: 'var(--vp-ink-3)',
    label: 'senza stato',
  },
  bozza: {
    dot: 'var(--vp-ink-4)',
    bg: 'var(--vp-paper-3)',
    fg: 'var(--vp-ink-2)',
    label: 'bozza',
  },
  firmata_proprieta: {
    dot: 'var(--vp-sky)',
    bg: 'var(--vp-sky-soft)',
    fg: 'var(--vp-status-declared-fg)',
    label: 'firmata dalla proprietà',
  },
  definitiva: {
    dot: 'var(--vp-sage)',
    bg: 'var(--vp-sage-soft)',
    fg: 'var(--vp-status-ok-fg)',
    label: 'definitiva',
  },
};

/** Come si nomina un file nei messaggi: «la versione "definitiva"», «la
 *  pagina "retro"», o il documento intero se il file è uno solo. */
export function nomeFile(voce: VoceFascicolo, pagina: PaginaDocumento): string {
  if (voce.versioni) return `la versione «${pagina.etichetta}»`;
  if (voce.pagine.length > 1) return `la pagina "${pagina.etichetta}"`;
  return `"${voce.titolo ?? voce.tipo_display}"`;
}

/** Chiede conferma prima di eliminare un file del fascicolo: lo stesso
 *  messaggio dal visore, dal dialog a schermo intero e dalla riga di una
 *  versione. */
export function confermaEliminaFile(
  $q: QVueGlobals,
  voce: VoceFascicolo,
  pagina: PaginaDocumento,
  poi: () => void,
): void {
  $q.dialog({
    title: 'Elimina documento',
    message: `Eliminare ${nomeFile(voce, pagina)}? L'operazione non è reversibile.`,
    cancel: { label: 'Annulla', flat: true, noCaps: true },
    ok: { label: 'Elimina', color: 'negative', unelevated: true, noCaps: true },
  }).onOk(poi);
}

/** Adatta un documento "piatto" (documenti della casa) alla forma delle voci
 *  del fascicolo, così il visore è lo stesso ovunque. */
export function voceDaDocumento(doc: DocumentoFE): VoceFascicolo {
  const percorso = doc.file.split('?')[0] ?? '';
  const estensione = percorso.split('.').pop()?.toLowerCase() ?? '';
  const stato: StatoDocumento = doc.scaduto ? 'scaduto' : 'ok';
  return {
    tipo: doc.tipo,
    tipo_display: doc.tipo_display,
    // I documenti della casa si caricano e basta: nessuno di essi è
    // prodotto dall'applicazione.
    generabile: null,
    suggerimento: '',
    stato,
    stato_display: STILI_STATO[stato].label,
    data_scadenza: doc.data_scadenza,
    giorni_alla_scadenza: null,
    caricato_il: doc.created_at,
    titolo: doc.descrizione || doc.tipo_display,
    versioni: false,
    stato_firma: '',
    stato_firma_display: '',
    pagine: [
      {
        id: doc.id,
        file: doc.file,
        nome_file: decodeURIComponent(percorso.split('/').pop() ?? ''),
        estensione,
        is_pdf: estensione === 'pdf',
        descrizione: doc.descrizione,
        etichetta: doc.descrizione || 'documento',
        data_scadenza: doc.data_scadenza,
        stato,
        stato_firma: '',
        stato_firma_display: '',
        generato: false,
        // Si apre sempre in sola lettura: il flag non viene mai consultato.
        modificabile: false,
        created_at: doc.created_at,
      },
    ],
  };
}

/** Riga di dettaglio sotto il titolo della voce (data, scadenza, suggerimento).
 *
 *  Con ``scadenzaNelBadge`` la data di scadenza è già mostrata dal badge di
 *  stato accanto: qui si racconta il caricamento, per non ripeterla. */
export function dettaglioVoce(
  voce: VoceFascicolo,
  formattaData: (d: string) => string,
  opzioni: { scadenzaNelBadge?: boolean } = {},
): string {
  if (voce.data_scadenza && !opzioni.scadenzaNelBadge) {
    const data = formattaData(voce.data_scadenza);
    return voce.stato === 'scaduto' ? `scaduto il ${data}` : `scade il ${data}`;
  }
  const caricato = voce.caricato_il ? `caricato il ${formattaData(voce.caricato_il)}` : '';
  // Lo stato della firma sta nel badge accanto: qui solo quante versioni ci
  // sono, e quando è arrivata la principale.
  if (voce.versioni) {
    const n = voce.pagine.length;
    return [n > 1 ? `${n} versioni` : '', caricato].filter(Boolean).join(' · ');
  }
  const pagine = voce.pagine.length > 1 ? ` · ${voce.pagine.length} pagine` : '';
  return caricato ? `${caricato}${pagine}` : '';
}
