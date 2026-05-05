import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export type StatoRiconciliazione = 'pieno' | 'parziale' | 'vuoto';

export interface BankTransactionAllocFE {
  id: number;
  receivable: number;
  causale: string;
  receivable_descrizione: string;
  importo: string | number;
}

export interface BankTransactionFE {
  id: number;
  data: string;
  descrizione: string;
  importo: string | number;
  owner_account: number;
  conto_banca: string;
  allocations: BankTransactionAllocFE[];
  importo_allocato: string | number;
  residuo: string | number;
  stato_riconciliazione: StatoRiconciliazione;
  note?: string | null;
}

export interface ReceivableAllocFE {
  id: number;
  bank_transaction: number;
  bt_data: string;
  bt_descrizione: string;
  bt_importo: string | number;
  importo: string | number;
}

export interface ReceivableFE {
  id: number;
  causale: 'affitto' | 'utenze' | 'extra';
  descrizione_estesa: string;
  assignment: number;
  tenant_id: number;
  tenant_nominativo: string;
  scadenza: string;
  competenza_da: string;
  competenza_a: string | null;
  importo_dovuto: string | number;
  importo_allocato: string | number;
  residuo: string | number;
  stato: string;
  stato_display: string;
  allocations: ReceivableAllocFE[];
}

export interface BTFiltri {
  data_da?: string | null;
  data_a?: string | null;
  riconciliato?: 'all' | 'true' | 'false';
  tenant?: number | null;
  owner_account?: number | null;
  limit?: number;
}

export interface ReceivableFiltri {
  tenant?: number | null;
  causale?: string | null;
  stato?: string | null;
  riconciliato?: 'all' | 'true' | 'false';
  data_da?: string | null;
  data_a?: string | null;
  assignment?: number | null;
  limit?: number;
}

export interface ReconcileItem {
  bank_transaction: number;
  receivable: number;
  importo: string;
}

export interface ReconcileBulkPayload {
  replace_for_transactions: number[];
  items: ReconcileItem[];
}

export interface ReconcileBulkResult {
  bank_transactions: BankTransactionFE[];
  receivables: ReceivableFE[];
}

interface State {
  bts: BankTransactionFE[];
  receivables: ReceivableFE[];
  loadingBts: boolean;
  loadingReceivables: boolean;
  saving: boolean;
  errore: string | null;
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

function paramsClean(filtri: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(filtri)) {
    if (v === null || v === undefined || v === '') continue;
    if (typeof v === 'number') out[k] = v.toString();
    else if (typeof v === 'boolean') out[k] = v ? 'true' : 'false';
    else if (typeof v === 'string') out[k] = v;
  }
  return out;
}

export const useRiconciliazioneStore = defineStore('riconciliazione', {
  state: (): State => ({
    bts: [],
    receivables: [],
    loadingBts: false,
    loadingReceivables: false,
    saving: false,
    errore: null,
  }),
  actions: {
    async fetchBankTransactions(filtri: BTFiltri = {}): Promise<void> {
      this.loadingBts = true;
      this.errore = null;
      try {
        const { data } = await api.get<
          BankTransactionFE[] | { results: BankTransactionFE[] }
        >('/api/v1/bank-transactions/', {
          params: paramsClean({ ...filtri }),
        });
        this.bts = asArray(data);
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore caricamento transazioni';
      } finally {
        this.loadingBts = false;
      }
    },
    async fetchReceivables(filtri: ReceivableFiltri = {}): Promise<void> {
      this.loadingReceivables = true;
      this.errore = null;
      try {
        const { data } = await api.get<
          ReceivableFE[] | { results: ReceivableFE[] }
        >('/api/v1/receivables/', {
          params: paramsClean({ ...filtri }),
        });
        this.receivables = asArray(data);
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore caricamento receivable';
      } finally {
        this.loadingReceivables = false;
      }
    },
    async saveBulk(payload: ReconcileBulkPayload): Promise<ReconcileBulkResult> {
      this.saving = true;
      this.errore = null;
      try {
        const { data } = await api.post<ReconcileBulkResult>(
          '/api/v1/reconciliations/',
          payload,
        );
        // Aggiorna in-place le BT e i Receivable interessati nello state.
        const aggiornaBt = new Map(data.bank_transactions.map((b) => [b.id, b]));
        this.bts = this.bts.map((b) => aggiornaBt.get(b.id) ?? b);
        const aggiornaRec = new Map(data.receivables.map((r) => [r.id, r]));
        this.receivables = this.receivables.map((r) => aggiornaRec.get(r.id) ?? r);
        return data;
      } finally {
        this.saving = false;
      }
    },
  },
});
