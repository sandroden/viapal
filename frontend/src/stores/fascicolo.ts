import { defineStore } from 'pinia';
import { api } from 'boot/axios';

/** Stato di una voce del fascicolo, calcolato dal backend
 *  (``properties/fascicolo.py``): un'unica definizione per tutte le UI. */
export type StatoDocumento = 'ok' | 'scadenza' | 'scaduto' | 'mancante' | 'attesa';

/** Un file: le voci fronte/retro sono due pagine dello stesso documento. */
export interface PaginaDocumento {
  id: number;
  file: string;
  nome_file: string;
  estensione: string;
  is_pdf: boolean;
  descrizione: string;
  etichetta: string;
  data_scadenza: string | null;
  stato: StatoDocumento;
  created_at: string;
}

export interface VoceFascicolo {
  tipo: string;
  tipo_display: string;
  richiesto: boolean;
  a_carico_proprieta: boolean;
  suggerimento: string;
  stato: StatoDocumento;
  stato_display: string;
  data_scadenza: string | null;
  giorni_alla_scadenza: number | null;
  caricato_il: string | null;
  pagine: PaginaDocumento[];
  /** Solo per i documenti fuori checklist ("Altro"). */
  titolo?: string;
}

export interface Fascicolo {
  tenant: number;
  tenant_nominativo: string;
  oggi: string;
  giorni_preavviso_scadenza: number;
  voci: VoceFascicolo[];
  altri: VoceFascicolo[];
  riepilogo: {
    ok: number;
    scadenza: number;
    scaduto: number;
    mancante: number;
    attesa: number;
    voci: number;
    da_sistemare: number;
    completezza: number;
  };
}

const ENDPOINT = '/api/v1/tenant-documents/fascicolo/';

interface State {
  fascicolo: Fascicolo | null;
  loading: boolean;
  errore: string | null;
}

export const useFascicoloStore = defineStore('fascicolo', {
  state: (): State => ({ fascicolo: null, loading: false, errore: null }),

  getters: {
    /** Voci della checklist + documenti liberi, nell'ordine di visualizzazione. */
    voci: (s): VoceFascicolo[] => s.fascicolo?.voci ?? [],
    altri: (s): VoceFascicolo[] => s.fascicolo?.altri ?? [],
    /** Voci che l'inquilino deve caricare (mancanti o da rinnovare). */
    daSistemare: (s): VoceFascicolo[] =>
      (s.fascicolo?.voci ?? []).filter(
        (v) => v.stato === 'mancante' || v.stato === 'scaduto' || v.stato === 'scadenza',
      ),
  },

  actions: {
    /** Carica il fascicolo: il proprio (inquilino) o quello di ``tenantId``
     *  (proprietario, inquilino dell'immobile attivo). */
    async fetch(tenantId?: number): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const url = tenantId ? `${ENDPOINT}?tenant=${tenantId}` : ENDPOINT;
        const { data } = await api.get<Fascicolo>(url);
        this.fascicolo = data;
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        this.errore =
          err?.response?.data?.detail ?? err?.message ?? 'Errore caricamento fascicolo';
      } finally {
        this.loading = false;
      }
    },
  },
});
