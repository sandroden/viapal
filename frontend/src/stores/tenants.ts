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
  deposito_versato?: string | null;
  data_versamento_deposito?: string | null;
  deposito_restituito?: string | null;
  data_restituzione_deposito?: string | null;
  saldo?: number | null;
}

interface State {
  tenants: Tenant[];
  loading: boolean;
  errore: string | null;
  ultimoSoloAttivi: boolean | null;
  tenantsPerAnno: Record<number, Tenant[]>;
  loadingAnno: Record<number, boolean>;
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
    tenantsPerAnno: {},
    loadingAnno: {},
  }),
  getters: {
    tenantById(state) {
      return (id: number): Tenant | undefined => state.tenants.find((t) => t.id === id);
    },
    tenantsAnno(state) {
      return (anno: number): Tenant[] => state.tenantsPerAnno[anno] ?? [];
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
    async fetchTenantsAnno(anno: number, force = false): Promise<Tenant[]> {
      if (!force && this.tenantsPerAnno[anno]) return this.tenantsPerAnno[anno];
      if (this.loadingAnno[anno]) return this.tenantsPerAnno[anno] ?? [];
      this.loadingAnno = { ...this.loadingAnno, [anno]: true };
      try {
        const { data } = await api.get<Tenant[] | { results: Tenant[] }>('/api/v1/tenants/', {
          params: { anno },
        });
        const lista = asArray(data);
        this.tenantsPerAnno = { ...this.tenantsPerAnno, [anno]: lista };
        return lista;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore';
        return [];
      } finally {
        this.loadingAnno = { ...this.loadingAnno, [anno]: false };
      }
    },
    async fetchTenant(id: number): Promise<Tenant> {
      const { data } = await api.get<Tenant>(`/api/v1/tenants/${id}/`);
      return data;
    },
  },
});
