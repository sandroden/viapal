import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';

// Vista utenze inquilino (sola lettura, solo periodi inviati).

export interface PeriodoInquilinoFE {
  id: number;
  periodo_da: string;
  periodo_a: string;
  stato: string;
  avvisi_inviati_at: string | null;
}

export interface BollettaInquilinoFE {
  id: number;
  prodotto: string;
  supplier_nome: string;
  consumo: string | null;
  numero_fattura: string;
  periodo_da: string;
  periodo_a: string;
  importo_totale: string;
  quota_esclusa: string;
  motivo_esclusione: string;
  importo_ripartibile: string;
  file_pdf: string | null;
}

export interface EsclusioneInquilinoFE {
  bill_id: number;
  prodotto: string;
  motivo: string;
  quota_esclusa: number | string;
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
  totale_escluso: number | string;
  esclusioni: EsclusioneInquilinoFE[];
  quote: QuotaInquilinoFE[];
  tenant_id: number;
}

interface State {
  periodi: PeriodoInquilinoFE[];
  dettaglio: DettaglioInquilinoFE | null;
  loading: boolean;
  errore: string | null;
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
