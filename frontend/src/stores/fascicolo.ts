import { defineStore } from 'pinia';
import { api } from 'boot/axios';

/** Stato di una voce del fascicolo, calcolato dal backend
 *  (``properties/fascicolo.py``): un'unica definizione per tutte le UI. */
export type StatoDocumento = 'ok' | 'scadenza' | 'scaduto' | 'attesa';

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
  a_carico_proprieta: boolean;
  /** Codice del generatore se il documento lo produce l'applicazione. */
  generabile: string | null;
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
    attesa: number;
    voci: number;
    da_sistemare: number;
  };
}

/** Un dato che serve al documento e non è ancora stato compilato, con il
 *  posto in cui compilarlo. È il cuore dell'anteprima: la generazione non
 *  chiede nulla in un form, dice dove andare. */
export interface DatoMancante {
  campo: string;
  etichetta: string;
  fonte: string;
  dove: string;
  link: string;
  /** Fuori dalla PWA (admin Django): va aperto in una nuova scheda. */
  esterno: boolean;
}

export interface AnteprimaDocumento {
  documento: string;
  documento_display: string;
  tenant: number;
  assignment: number;
  completo: boolean;
  mancanti: DatoMancante[];
  /** Dichiarato dal singolo documento: ogni chiave è presente solo se
   *  quel documento la riporta davvero. */
  riepilogo: {
    stanza?: string;
    decorrenza?: string;
    canone?: string;
    oneri_accessori?: string | null;
    deposito?: string | null;
    rate_deposito?: number;
    comproprietari?: string[];
    firmatario?: string | null;
    uscente?: string | null;
    contratto?: string | null;
    // Solo la comunicazione di cessione di fabbricato.
    data_cessione?: string;
    fabbricato?: string;
  };
  esistente: { id: number; descrizione: string; created_at: string } | null;
}

const ENDPOINT = '/api/v1/tenant-documents/fascicolo/';
const GENERA = '/api/v1/tenant-documents/genera/';

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
    /** Voci da rinnovare: scadute o in scadenza. */
    daSistemare: (s): VoceFascicolo[] =>
      (s.fascicolo?.voci ?? []).filter(
        (v) => v.stato === 'scaduto' || v.stato === 'scadenza',
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

    /** Cosa serve per generare un documento: campi risolti e dati mancanti.
     *  Non scrive nulla. */
    async anteprima(tenantId: number, documento: string): Promise<AnteprimaDocumento> {
      const { data } = await api.post<AnteprimaDocumento>(GENERA, {
        tenant: tenantId,
        documento,
        dry_run: true,
      });
      return data;
    },

    /** Genera il PDF e lo salva nel fascicolo dell'inquilino. Sostituisce
     *  solo un precedente PDF generato, mai una scansione caricata a mano. */
    async genera(tenantId: number, documento: string): Promise<{ id: number }> {
      const { data } = await api.post<{ id: number }>(GENERA, {
        tenant: tenantId,
        documento,
        dry_run: false,
      });
      return data;
    },
  },
});
