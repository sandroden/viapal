import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export interface Expense {
  id: number;
  data: string;
  descrizione: string;
  importo: string | number;
  category?: number | null;
  category_nome?: string | null;
  anticipata_da_owner?: number | null;
  anticipata_da_nominativo?: string | null;
  ripartibile_su_inquilini?: boolean;
  note?: string | null;
  // bolletta collegata (read-only, derivata da OneToOne UtilityBill)
  bolletta_id?: number | null;
  bolletta_numero?: string | null;
  bolletta_prodotto?: 'gas' | 'luce' | 'acqua' | null;
  bolletta_consumo?: string | number | null;
  file_pdf?: string | null;
  // legacy / form fields
  categoria?: string | null;
  fornitore?: string | null;
  metodo_pagamento?: string | null;
  ricevuta?: string | null;
}

export interface NuovaSpesa {
  data: string;
  descrizione: string;
  importo: number;
  categoria?: string | undefined;
  fornitore?: string | undefined;
  metodo_pagamento?: string | undefined;
  note?: string | undefined;
  anticipata_da_owner?: number | null;
  // Creazione contestuale BankTransaction in uscita
  crea_bank_transaction?: boolean;
  bt_owner_account?: number | null;
  bt_data?: string;
  bt_descrizione?: string;
}

interface State {
  expenses: Expense[];
  loading: boolean;
  errore: string | null;
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export const useExpensesStore = defineStore('expenses', {
  state: (): State => ({
    expenses: [],
    loading: false,
    errore: null,
  }),
  actions: {
    async fetchExpenses(force = false): Promise<void> {
      if (this.expenses.length > 0 && !force) return;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<Expense[] | { results: Expense[] }>('/api/v1/expenses/');
        this.expenses = asArray(data).sort((a, b) => (a.data < b.data ? 1 : -1));
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore';
      } finally {
        this.loading = false;
      }
    },
    async creaSpesa(payload: NuovaSpesa): Promise<Expense> {
      const { data } = await api.post<Expense>('/api/v1/expenses/', payload);
      this.expenses = [data, ...this.expenses];
      return data;
    },
  },
});
