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
  owner_id: number;
  owner_nominativo: string;
  allocations: BankTransactionAllocFE[];
  importo_allocato: string | number;
  residuo: string | number;
  stato_riconciliazione: StatoRiconciliazione;
  is_inter_owner?: boolean;
  note?: string | null;
}

export type TipoInterOwner =
  | 'distribuzione'
  | 'incasso_conguaglio'
  | 'bilaterale'
  | 'aggiustamento';

export interface MarcaInterOwnerPayload {
  bank_transaction: number;
  tipo: TipoInterOwner;
  controparte_owner?: number | null;
  settlement?: number | null;
  descrizione?: string;
  note?: string;
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

/**
 * Scarica TUTTE le pagine di un endpoint DRF paginato (LimitOffset),
 * accumulando i `results` finché non si raggiunge `count`. Necessario per la
 * riconciliazione: con un periodo ampio i Receivable/BT superano il `max_limit`
 * del backend (200) e fermarsi alla prima pagina nasconderebbe le voci più
 * vecchie ancora da abbinare (es. un'utenza 2024 con periodo 2023-2026).
 */
async function fetchAllPaginated<T>(
  url: string,
  filtri: Record<string, unknown>,
): Promise<T[]> {
  const pageSize = Number(filtri.limit) || 200;
  const acc: T[] = [];
  let offset = 0;
  // Guardia anti-loop: il backend cap a 200/pagina, quindi bastano poche
  // pagine; il tetto duro evita cicli infiniti se `count` fosse incoerente.
  for (let guard = 0; guard < 1000; guard++) {
    const { data } = await api.get<T[] | { count?: number; results?: T[] }>(url, {
      params: paramsClean({ ...filtri, limit: pageSize, offset }),
    });
    if (Array.isArray(data)) return data; // endpoint non paginato
    const results = data.results ?? [];
    acc.push(...results);
    const count = typeof data.count === 'number' ? data.count : acc.length;
    offset += pageSize;
    if (results.length === 0 || acc.length >= count) break;
  }
  return acc;
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
        this.bts = await fetchAllPaginated<BankTransactionFE>(
          '/api/v1/bank-transactions/',
          { ...filtri },
        );
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
        this.receivables = await fetchAllPaginated<ReceivableFE>(
          '/api/v1/receivables/',
          { ...filtri },
        );
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore caricamento receivable';
      } finally {
        this.loadingReceivables = false;
      }
    },
    async marcaInterOwner(payload: MarcaInterOwnerPayload): Promise<void> {
      await api.post('/api/v1/owner-ledger/bt-inter-owner/', payload);
      // Aggiorna in-place il flag is_inter_owner della BT toccata.
      const bt = this.bts.find((b) => b.id === payload.bank_transaction);
      if (bt) bt.is_inter_owner = true;
    },
    async disfaInterOwner(btId: number): Promise<void> {
      await api.delete(`/api/v1/owner-ledger/bt-inter-owner/${btId}/`);
      const bt = this.bts.find((b) => b.id === btId);
      if (bt) bt.is_inter_owner = false;
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
