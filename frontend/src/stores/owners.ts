import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export interface Owner {
  id: number;
  nominativo: string;
  username?: string;
  codice_fiscale?: string;
  telefono?: string;
}

interface State {
  owners: Owner[];
  loading: boolean;
  errore: string | null;
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export const useOwnersStore = defineStore('owners', {
  state: (): State => ({ owners: [], loading: false, errore: null }),
  getters: {
    byId: (state) => (id: number): Owner | undefined =>
      state.owners.find((o) => o.id === id),
  },
  actions: {
    async fetchOwners(force = false): Promise<void> {
      if (this.owners.length > 0 && !force) return;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<Owner[] | { results: Owner[] }>(
          '/api/v1/owners/',
        );
        this.owners = asArray(data).sort((a, b) =>
          a.nominativo.localeCompare(b.nominativo),
        );
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore caricamento proprietari';
      } finally {
        this.loading = false;
      }
    },
  },
});
