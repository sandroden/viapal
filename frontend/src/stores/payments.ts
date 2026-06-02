import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export type TipoPagamentoApi = 'rent' | 'utility_charge' | 'extra';

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
    loading: false,
    errore: null,
  }),
  actions: {
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
