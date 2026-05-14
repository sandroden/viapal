import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export interface ExpenseCategory {
  id: number;
  nome: string;
  codice: string;
  ripartibile_inquilini: boolean;
}

interface State {
  categories: ExpenseCategory[];
  loaded: boolean;
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export const useExpenseCategoriesStore = defineStore('expenseCategories', {
  state: (): State => ({
    categories: [],
    loaded: false,
  }),
  actions: {
    async ensureLoaded(force = false): Promise<void> {
      if (this.loaded && !force) return;
      const { data } = await api.get<ExpenseCategory[] | { results: ExpenseCategory[] }>(
        '/api/v1/expense-categories/',
      );
      this.categories = asArray(data);
      this.loaded = true;
    },
  },
});
