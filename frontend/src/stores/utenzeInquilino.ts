import { defineStore } from 'pinia';
import { api } from 'boot/axios';

// Vista utenze inquilino (sola lettura, solo periodi inviati).

export interface PeriodoInquilinoFE {
  id: number;
  periodo_da: string;
  periodo_a: string;
  stato: string;
  avvisi_inviati_at: string | null;
}

export interface BollettaInquilinoFE {
  prodotto: string;
  supplier_nome: string;
  consumo: string | null;
  numero_fattura: string;
  periodo_da: string;
  periodo_a: string;
  importo_totale: string;
  file_pdf: string | null;
}

export interface QuotaInquilinoFE {
  assignment_id: number;
  tenant_nominativo: string;
  giorni_presenza: number;
  quota: number | string;
  dettaglio: Record<string, number | string>;
  is_me: boolean;
}

export interface DettaglioInquilinoFE {
  period: PeriodoInquilinoFE;
  bollette: BollettaInquilinoFE[];
  totali_per_voce: Record<string, number | string>;
  totale_periodo: number | string;
  quote: QuotaInquilinoFE[];
  tenant_id: number;
}

interface State {
  periodi: PeriodoInquilinoFE[];
  dettaglio: DettaglioInquilinoFE | null;
  loading: boolean;
  errore: string | null;
}

function messaggioErrore(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: { detail?: string } }; message?: string };
  return err?.response?.data?.detail ?? err?.message ?? fallback;
}

export const useUtenzeInquilinoStore = defineStore('utenzeInquilino', {
  state: (): State => ({
    periodi: [],
    dettaglio: null,
    loading: false,
    errore: null,
  }),
  actions: {
    async fetchPeriodi(): Promise<PeriodoInquilinoFE[]> {
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<{ periodi: PeriodoInquilinoFE[] }>(
          '/api/v1/utenze-inquilino/',
        );
        this.periodi = data.periodi;
        return data.periodi;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento periodi');
        return [];
      } finally {
        this.loading = false;
      }
    },

    async fetchDettaglio(periodId: number): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<DettaglioInquilinoFE>(
          `/api/v1/utenze-inquilino/${periodId}/`,
        );
        this.dettaglio = data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento utenze');
        this.dettaglio = null;
      } finally {
        this.loading = false;
      }
    },
  },
});
