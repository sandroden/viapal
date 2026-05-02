import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export type TipoPagamentoApi = 'rent' | 'utility_charge' | 'extra';

export interface RentPayment {
  id: number;
  assignment: number;
  competenza_da: string;
  competenza_a: string;
  scadenza: string;
  importo_dovuto: string | number;
  importo_pagato: string | number | null;
  data_pagamento: string | null;
  stato: string;
  metodo_pagamento?: string | null;
  riferimento?: string | null;
  note?: string | null;
}

export interface UtilityCharge {
  id: number;
  assignment: number;
  period: number;
  scadenza: string;
  importo_totale: string | number;
  importo_pagato: string | number | null;
  data_pagamento: string | null;
  stato: string;
  giorni_presenza?: number;
}

interface DichiaraPayload {
  importo_pagato?: number | undefined;
  data_pagamento?: string | undefined;
  metodo_pagamento?: string | undefined;
  riferimento?: string | undefined;
  note?: string | undefined;
}

interface State {
  rentPayments: RentPayment[];
  utilityCharges: UtilityCharge[];
  loading: boolean;
  errore: string | null;
}

function endpointPerTipo(tipo: TipoPagamentoApi): string {
  if (tipo === 'rent') return '/api/v1/rent-payments';
  if (tipo === 'utility_charge') return '/api/v1/utility-charges';
  return '/api/v1/extra-charges';
}

export const usePaymentsStore = defineStore('payments', {
  state: (): State => ({
    rentPayments: [],
    utilityCharges: [],
    loading: false,
    errore: null,
  }),
  actions: {
    async fetchRentPayments(): Promise<void> {
      this.loading = true;
      try {
        const { data } = await api.get<RentPayment[] | { results: RentPayment[] }>(
          '/api/v1/rent-payments/',
        );
        this.rentPayments = Array.isArray(data) ? data : (data.results ?? []);
      } finally {
        this.loading = false;
      }
    },
    async fetchUtilityCharges(): Promise<void> {
      this.loading = true;
      try {
        const { data } = await api.get<UtilityCharge[] | { results: UtilityCharge[] }>(
          '/api/v1/utility-charges/',
        );
        this.utilityCharges = Array.isArray(data) ? data : (data.results ?? []);
      } finally {
        this.loading = false;
      }
    },
    async fetchUtilityCharge(id: number): Promise<UtilityCharge> {
      const { data } = await api.get<UtilityCharge>(`/api/v1/utility-charges/${id}/`);
      return data;
    },
    async dichiaraPagato(
      tipo: TipoPagamentoApi,
      id: number,
      payload: DichiaraPayload,
    ): Promise<void> {
      const base = endpointPerTipo(tipo);
      await api.post(`${base}/${id}/dichiara_pagato/`, payload);
    },
    async confermaPagato(
      tipo: TipoPagamentoApi,
      id: number,
      payload: DichiaraPayload = {},
    ): Promise<void> {
      const base = endpointPerTipo(tipo);
      await api.post(`${base}/${id}/conferma_pagato/`, payload);
    },
    async getDettaglio<T = unknown>(tipo: TipoPagamentoApi, id: number): Promise<T> {
      const base = endpointPerTipo(tipo);
      const { data } = await api.get<T>(`${base}/${id}/`);
      return data;
    },
  },
});
