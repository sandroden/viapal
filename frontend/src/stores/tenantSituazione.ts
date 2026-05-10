import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import type { TenantInfo } from 'stores/dashboard';

export interface AssignmentRiga {
  id: number;
  room_id: number;
  room_nome: string;
  valid_from: string;
  valid_to: string | null;
  canone_mensile: number;
  data_atto_cessione: string | null;
}

export interface RentRiga {
  id: number;
  competenza_da: string;
  competenza_a: string;
  importo_dovuto: number;
  importo_pagato: number;
  scadenza: string;
  stato: string;
  giorni_ritardo: number;
  data_pagamento: string | null;
  is_aggiustamento: boolean;
}

export interface UtilityLine {
  voce: string;
  importo: number;
}

export interface UtilityRiga {
  id: number;
  period_id: number;
  period_da: string;
  period_a: string;
  importo_totale: number;
  importo_pagato: number;
  scadenza: string | null;
  stato: string;
  data_pagamento: string | null;
  lines: UtilityLine[];
}

export interface ExtraRiga {
  id: number;
  data: string;
  descrizione: string;
  importo: number;
  scadenza: string | null;
  stato: string;
}

export interface QuotaCondominioRiga {
  valid_from: string;
  valid_to: string | null;
  importo_mensile: number;
  note: string;
}

export interface QuotaCondominio {
  corrente: QuotaCondominioRiga | null;
  storico: QuotaCondominioRiga[];
}

export interface ContractInfo {
  id: number;
  data_decorrenza: string;
  default_pagatore_bollette: string | null;
}

export interface TenantSituazione {
  tenant: TenantInfo;
  anno: number;
  assignments: AssignmentRiga[];
  contract: ContractInfo | null;
  quota_condominio: QuotaCondominio;
  rent: {
    dovuto_anno: number;
    pagato_anno: number;
    saldo: number;
    righe: RentRiga[];
  };
  utility: {
    dovuto_anno: number;
    pagato_anno: number;
    saldo: number;
    righe: UtilityRiga[];
  };
  extra: {
    totale_anno: number;
    righe: ExtraRiga[];
  };
  totali_anno: {
    dovuto: number;
    pagato: number;
    saldo: number;
  };
  ritardo_medio_giorni: number;
}

interface State {
  byTenantAnno: Record<string, TenantSituazione>;
  loading: boolean;
  errore: string | null;
}

function chiave(tenantId: number, anno: number): string {
  return `${tenantId}-${anno}`;
}

export const useTenantSituazioneStore = defineStore('tenantSituazione', {
  state: (): State => ({
    byTenantAnno: {},
    loading: false,
    errore: null,
  }),
  actions: {
    async loadSituazione(
      tenantId: number,
      anno?: number,
      force = false,
    ): Promise<void> {
      const a = anno ?? new Date().getFullYear();
      const key = chiave(tenantId, a);
      if (this.byTenantAnno[key] && !force) return;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<TenantSituazione>(
          `/api/v1/tenants/${tenantId}/situazione/`,
          { params: { anno: a } },
        );
        this.byTenantAnno[key] = data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore nel caricamento';
      } finally {
        this.loading = false;
      }
    },
    get(tenantId: number, anno: number): TenantSituazione | null {
      return this.byTenantAnno[chiave(tenantId, anno)] ?? null;
    },
  },
});
