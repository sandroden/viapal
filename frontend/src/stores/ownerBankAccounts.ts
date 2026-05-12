import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import type { BankAccountInfo } from 'stores/auth';

interface BankAccountFull {
  id: number;
  owner: number;
  owner_nominativo: string;
  banca: string;
  intestatario: string;
  iban: string;
  attivo: boolean;
  ordinamento: number;
}

interface State {
  accounts: BankAccountInfo[];
  loaded: boolean;
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export const useOwnerBankAccountsStore = defineStore('ownerBankAccounts', {
  state: (): State => ({
    accounts: [],
    loaded: false,
  }),
  actions: {
    async ensureLoaded(force = false): Promise<void> {
      if (this.loaded && !force) return;
      const { data } = await api.get<BankAccountFull[] | { results: BankAccountFull[] }>(
        '/api/v1/bank-accounts/',
      );
      this.accounts = asArray(data)
        .filter((a) => a.attivo)
        .map((a) => ({
          id: a.id,
          banca: a.banca,
          intestatario: a.intestatario,
          iban: a.iban,
          owner_id: a.owner,
        }));
      this.loaded = true;
    },
  },
});
