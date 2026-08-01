import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { paramsClean } from 'src/utils/paginate';

// --- Tipi -----------------------------------------------------------------

export interface ComunicazioneFE {
  id: number;
  tenant_id: number | null;
  tenant_nominativo: string | null;
  destinatario: string;
  canale: string;
  canale_display: string;
  codice: string;
  tipo_display: string;
  oggetto: string;
  inviata_at: string | null;
  letta_at: string | null;
  errore: string;
  created_at: string;
}

export interface ComunicazioneDettaglioFE extends ComunicazioneFE {
  corpo: string;
  corpo_html: string;
}

export interface ComunicazioniFiltri {
  tenant?: number | null;
  da?: string | null;
  a?: string | null;
  canale?: string | null;
  tipo?: string | null;
  esito?: string | null;
  limit?: number;
  offset?: number;
}

interface State {
  righe: ComunicazioneFE[];
  totale: number;
  loading: boolean;
  errore: string | null;
}

function messaggioErrore(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail ?? err?.message ?? fallback;
}

export const useComunicazioniStore = defineStore('comunicazioni', {
  state: (): State => ({
    righe: [],
    totale: 0,
    loading: false,
    errore: null,
  }),
  actions: {
    /**
     * Una pagina di registro. **Paginazione server-side**: la tabella cresce
     * di N righe al mese, scaricarla tutta come fa `fetchAllPaginated`
     * diventerebbe pesante senza servire a niente.
     */
    async lista(filtri: ComunicazioniFiltri = {}): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<{
          count: number;
          results: ComunicazioneFE[];
        }>('/api/v1/comunicazioni/', {
          params: paramsClean({ limit: 25, offset: 0, ...filtri }),
        });
        this.righe = data.results ?? [];
        this.totale = data.count ?? this.righe.length;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento comunicazioni');
        this.righe = [];
        this.totale = 0;
      } finally {
        this.loading = false;
      }
    },

    /** Dettaglio con il testo realmente recapitato (non è nella lista). */
    async dettaglio(id: number): Promise<ComunicazioneDettaglioFE | null> {
      try {
        const { data } = await api.get<ComunicazioneDettaglioFE>(
          `/api/v1/comunicazioni/${id}/`,
        );
        return data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento comunicazione');
        return null;
      }
    },
  },
});
