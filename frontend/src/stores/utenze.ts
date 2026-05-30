import { defineStore } from 'pinia';
import { api } from 'boot/axios';

// --- Tipi -----------------------------------------------------------------

export interface PeriodFE {
  id: number;
  periodo_da: string;
  periodo_a: string;
  stato: string;
  stato_display: string;
  data_invio: string | null;
  tot_luce: string;
  tot_gas: string;
  tot_tari: string;
  tot_altro: string;
  giorni_totali: number;
}

export interface Completezza {
  luce: boolean;
  gas: boolean;
  tari: boolean;
  completo: boolean;
}

export interface PerMeseResponse {
  period: PeriodFE;
  created: boolean;
  completezza: Completezza;
  anno: number;
  mese: number;
}

export interface QuotaInquilino {
  assignment_id: number;
  tenant_nominativo: string;
  giorni_presenza: number;
  quota: number | string;
  dettaglio: Record<string, number | string>;
  importo_esistente: number | string | null;
}

export interface AnteprimaResponse {
  period_id: number;
  periodo_da: string;
  periodo_a: string;
  totale_periodo: number | string;
  totali_per_voce: Record<string, number | string>;
  sum_giorni_presenza: number;
  quote: QuotaInquilino[];
  diff_arrotondamento: number | string;
  completezza: Completezza;
  skipped?: string;
  // presenti dopo emetti
  creati?: number;
  aggiornati_diversi?: number;
  aggiornati_uguali?: number;
  skippati_per_allocation?: unknown[];
  period?: PeriodFE;
}

export interface AvvisoFE {
  receivable_id: number;
  tenant_id: number;
  tenant_nominativo: string;
  email: string;
  importo: number | string;
  scadenza: string | null;
  oggetto: string;
  corpo: string;
  canale: string;
  esito?: string;
  errore?: string;
}

export interface InvioAvvisiResponse {
  period_id: number;
  dry_run: boolean;
  from_email: string;
  totale: number;
  inviati: number;
  errori: number;
  senza_email: string[];
  avvisi: AvvisoFE[];
}

export interface OwnerFE {
  id: number;
  nominativo: string;
}

export interface BollettaFE {
  id: number;
  prodotto: string;
  consumo: string | null;
  numero_fattura: string;
  data_emissione: string;
  periodo_da: string;
  periodo_a: string;
  importo_totale: string;
  supplier_nome?: string;
  pagata_da_nominativo?: string;
}

interface State {
  owners: OwnerFE[];
  period: PeriodFE | null;
  completezza: Completezza | null;
  anteprima: AnteprimaResponse | null;
  invio: InvioAvvisiResponse | null;
  ultimoUpload: BollettaFE | null;
  loading: boolean;
  errore: string | null;
}

function messaggioErrore(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail ?? err?.message ?? fallback;
}

export const useUtenzeStore = defineStore('utenze', {
  state: (): State => ({
    owners: [],
    period: null,
    completezza: null,
    anteprima: null,
    invio: null,
    ultimoUpload: null,
    loading: false,
    errore: null,
  }),
  actions: {
    async fetchOwners(): Promise<void> {
      if (this.owners.length) return;
      try {
        const { data } = await api.get<OwnerFE[] | { results: OwnerFE[] }>(
          '/api/v1/owners/',
        );
        this.owners = Array.isArray(data) ? data : data.results;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento proprietari');
      }
    },

    async caricaBolletta(file: File, ownerId: number): Promise<BollettaFE | null> {
      this.loading = true;
      this.errore = null;
      try {
        const form = new FormData();
        form.append('file_pdf', file);
        form.append('pagata_da_owner', String(ownerId));
        const { data } = await api.post<BollettaFE>('/api/v1/utility-bills/', form);
        this.ultimoUpload = data;
        return data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento bolletta');
        return null;
      } finally {
        this.loading = false;
      }
    },

    async perMese(anno?: number, mese?: number): Promise<PerMeseResponse | null> {
      this.loading = true;
      this.errore = null;
      this.anteprima = null;
      this.invio = null;
      try {
        const params = anno && mese ? { anno, mese } : {};
        const { data } = await api.get<PerMeseResponse>(
          '/api/v1/utility-periods/per-mese/',
          { params },
        );
        this.period = data.period;
        this.completezza = data.completezza;
        return data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore ricerca periodo');
        return null;
      } finally {
        this.loading = false;
      }
    },

    async calcolaAnteprima(): Promise<void> {
      if (!this.period) return;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<AnteprimaResponse>(
          `/api/v1/utility-periods/${this.period.id}/anteprima/`,
        );
        this.anteprima = data;
        this.completezza = data.completezza;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore calcolo anteprima');
      } finally {
        this.loading = false;
      }
    },

    async emetti(): Promise<boolean> {
      if (!this.period) return false;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.post<AnteprimaResponse>(
          `/api/v1/utility-periods/${this.period.id}/emetti/`,
        );
        this.anteprima = data;
        if (data.period) this.period = data.period;
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore emissione addebiti');
        return false;
      } finally {
        this.loading = false;
      }
    },

    async inviaAvvisi(dryRun: boolean): Promise<InvioAvvisiResponse | null> {
      if (!this.period) return null;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.post<InvioAvvisiResponse>(
          `/api/v1/utility-periods/${this.period.id}/invia-avvisi/`,
          { dry_run: dryRun },
        );
        this.invio = data;
        return data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore invio avvisi');
        return null;
      } finally {
        this.loading = false;
      }
    },

    reset(): void {
      this.period = null;
      this.completezza = null;
      this.anteprima = null;
      this.invio = null;
    },
  },
});
