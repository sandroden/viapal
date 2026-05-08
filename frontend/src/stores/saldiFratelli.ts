import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export interface OwnerMinimale {
  id: number;
  nominativo: string;
}

export interface SaldoLiveFE {
  owner: OwnerMinimale;
  quota: string;
  baseline_settlement: string;
  incassi_per_causale: Record<string, string>;
  spese_per_categoria: Record<string, string>;
  anticipi_pendenti: string;
  bt_inter_owner: string;
  totale: string;
}

export interface OwnerSettlementFE {
  id: number;
  data: string;
  periodo_da: string;
  periodo_a: string;
  descrizione: string;
  snapshot: Record<string, string>;
  note?: string | null;
}

export interface OwnerLedgerEntryFE {
  id: number;
  owner: number;
  owner_nominativo: string;
  data: string;
  descrizione: string;
  importo: string;
  tipo: string;
  tipo_display: string;
  riferimento_receivable?: number | null;
  riferimento_expense?: number | null;
  riferimento_settlement?: number | null;
  bank_transaction?: number | null;
  note?: string | null;
}

export interface InterOwnerEntryFE {
  id: number;
  owner_da: number;
  owner_da_nominativo: string;
  owner_a: number;
  owner_a_nominativo: string;
  data: string;
  importo: string;
  descrizione: string;
  riferimento_loan?: number | null;
  riferimento_expense?: number | null;
  bank_transaction?: number | null;
  note?: string | null;
}

interface State {
  saldi: SaldoLiveFE[];
  settlements: OwnerSettlementFE[];
  ledgerEntries: OwnerLedgerEntryFE[];
  bilaterali: InterOwnerEntryFE[];
  loading: boolean;
  errore: string | null;
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export const useSaldiFratelliStore = defineStore('saldiFratelli', {
  state: (): State => ({
    saldi: [],
    settlements: [],
    ledgerEntries: [],
    bilaterali: [],
    loading: false,
    errore: null,
  }),
  actions: {
    async fetchSaldi(at?: string): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const params: Record<string, string> = {};
        if (at) params.at = at;
        const { data } = await api.get<SaldoLiveFE[]>(
          '/api/v1/owner-ledger/saldi-live/',
          { params },
        );
        this.saldi = data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore caricamento saldi';
      } finally {
        this.loading = false;
      }
    },
    async fetchSettlements(): Promise<void> {
      const { data } = await api.get<
        OwnerSettlementFE[] | { results: OwnerSettlementFE[] }
      >('/api/v1/owner-settlements/');
      this.settlements = asArray(data);
    },
    async fetchLedgerInterOwner(): Promise<void> {
      const { data } = await api.get<
        OwnerLedgerEntryFE[] | { results: OwnerLedgerEntryFE[] }
      >('/api/v1/owner-ledger/');
      this.ledgerEntries = asArray(data).filter((v) => v.bank_transaction != null);
    },
    async fetchBilaterali(): Promise<void> {
      const { data } = await api.get<
        InterOwnerEntryFE[] | { results: InterOwnerEntryFE[] }
      >('/api/v1/inter-owner-entries/');
      this.bilaterali = asArray(data);
    },
    async fetchLedgerBySettlement(settlementId: number): Promise<OwnerLedgerEntryFE[]> {
      const { data } = await api.get<
        OwnerLedgerEntryFE[] | { results: OwnerLedgerEntryFE[] }
      >('/api/v1/owner-ledger/', {
        params: { riferimento_settlement: settlementId },
      });
      return asArray(data).filter((v) => v.riferimento_settlement === settlementId);
    },
  },
});
