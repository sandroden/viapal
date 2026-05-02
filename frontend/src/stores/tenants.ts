import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export interface Tenant {
  id: number;
  nominativo: string;
  email?: string | null;
  telefono?: string | null;
  user?: number | null;
  data_nascita?: string | null;
  documento_tipo?: string | null;
  documento_numero?: string | null;
  note?: string | null;
}

interface State {
  tenants: Tenant[];
  loading: boolean;
  errore: string | null;
  ultimoSoloAttivi: boolean | null;
}

function asArray<T>(data: T[] | { results: T[] } | undefined | null): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

export const useTenantsStore = defineStore('tenants', {
  state: (): State => ({
    tenants: [],
    loading: false,
    errore: null,
    ultimoSoloAttivi: null,
  }),
  getters: {
    tenantById(state) {
      return (id: number): Tenant | undefined => state.tenants.find((t) => t.id === id);
    },
  },
  actions: {
    async fetchTenants(soloAttivi = true, force = false): Promise<void> {
      if (this.tenants.length > 0 && !force && this.ultimoSoloAttivi === soloAttivi) return;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<Tenant[] | { results: Tenant[] }>('/api/v1/tenants/', {
          params: { solo_attivi: soloAttivi ? 1 : 0 },
        });
        this.tenants = asArray(data);
        this.ultimoSoloAttivi = soloAttivi;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore';
      } finally {
        this.loading = false;
      }
    },
    async fetchTenant(id: number): Promise<Tenant> {
      const { data } = await api.get<Tenant>(`/api/v1/tenants/${id}/`);
      return data;
    },
  },
});
