import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';

export interface Tenant {
  id: number;
  nominativo: string;
  email?: string | null;
  telefono?: string | null;
  /** False per i profili creati e mai assegnati a una stanza. */
  ha_assignment?: boolean;
  user?: number | null;
  data_nascita?: string | null;
  documento_tipo?: string | null;
  documento_numero?: string | null;
  note?: string | null;
  deposito_versato?: string | null;
  data_versamento_deposito?: string | null;
  deposito_da_restituire?: string | null;
  data_restituzione_prevista?: string | null;
  saldo?: number | null;
  saldo_totale?: number | null;
}

interface State {
  tenants: Tenant[];
  loading: boolean;
  errore: string | null;
  ultimoSoloAttivi: boolean | null;
  tenantsPerAnno: Record<number, Tenant[]>;
  loadingAnno: Record<number, boolean>;
  tenantsConAssignment: Tenant[];
  loadingConAssignment: boolean;
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
    tenantsConAssignment: [],
    loadingConAssignment: false,
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
        this.errore = messaggioErrore(e, 'Errore caricamento inquilini');
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
        this.errore = messaggioErrore(e, 'Errore caricamento inquilini');
        return [];
      } finally {
        this.loadingAnno = { ...this.loadingAnno, [anno]: false };
      }
    },
    /** Inquilini con almeno una assegnazione sull'immobile (passata,
     *  presente o futura): la lista giusta per i select dove un profilo mai
     *  assegnato non ha senso (es. quote condominio). Cache separata da
     *  `tenants` per non interferire con gli altri usi di fetchTenants. */
    async fetchTenantsConAssignment(force = false): Promise<Tenant[]> {
      if (!force && this.tenantsConAssignment.length > 0) return this.tenantsConAssignment;
      this.loadingConAssignment = true;
      this.errore = null;
      try {
        const { data } = await api.get<Tenant[] | { results: Tenant[] }>('/api/v1/tenants/', {
          params: { solo_attivi: 0, con_assignment: 1 },
        });
        this.tenantsConAssignment = asArray(data);
        return this.tenantsConAssignment;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento inquilini');
        return [];
      } finally {
        this.loadingConAssignment = false;
      }
    },
    async fetchTenant(id: number): Promise<Tenant> {
      const { data } = await api.get<Tenant>(`/api/v1/tenants/${id}/`);
      return data;
    },
  },
});
