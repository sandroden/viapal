import type { DocumentoFE } from 'stores/documenti';
import type { StatoDocumento, VoceFascicolo } from 'stores/fascicolo';

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
  const pagine = voce.pagine.length > 1 ? ` · ${voce.pagine.length} pagine` : '';
  return voce.caricato_il ? `caricato il ${formattaData(voce.caricato_il)}${pagine}` : '';
}
