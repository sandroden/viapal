import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import type { SemaforoLivello } from 'src/types/semaforo';

export type TipoPagamento = 'rent' | 'utility_charge' | 'extra';

export interface DaPagareItem {
  tipo: TipoPagamento;
  id: number;
  descrizione: string;
  importo: number;
  scadenza: string;
  stato: string;
  giorni_ritardo: number;
  semaforo: SemaforoLivello;
}

export interface UltimoPagamento {
  tipo: TipoPagamento;
  id: number;
  descrizione: string;
  importo: number;
  data_pagamento: string | null;
  stato: string;
}

export interface StanzaCorrente {
  id: number;
  nome: string;
  canone_mensile: number;
  valid_from: string;
}

export interface TenantInfo {
  id: number;
  nominativo: string;
  email?: string;
  telefono?: string;
  user?: number;
  [k: string]: unknown;
}

export interface InquilinoDashboardData {
  tenant: TenantInfo;
  stanza_corrente: StanzaCorrente | null;
  da_pagare: DaPagareItem[];
  ultimi_pagamenti: UltimoPagamento[];
}

export interface ProprietarioRiga {
  tipo: TipoPagamento;
  id: number;
  tenant: string;
  descrizione: string;
  importo: number;
  scadenza: string;
  stato: string;
  giorni_ritardo: number;
}

export interface ProprietarioKpi {
  incasso_anno_corrente: number;
  incasso_mese_corrente: number;
  spese_anno_corrente: number;
  ritardi_count: number;
  in_scadenza_count: number;
}

export interface ProprietarioDashboardData {
  kpi: ProprietarioKpi;
  ritardi: ProprietarioRiga[];
  in_scadenza: ProprietarioRiga[];
}

interface State {
  inquilinoData: InquilinoDashboardData | null;
  proprietarioData: ProprietarioDashboardData | null;
  loadingInquilino: boolean;
  loadingProprietario: boolean;
  errore: string | null;
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): State => ({
    inquilinoData: null,
    proprietarioData: null,
    loadingInquilino: false,
    loadingProprietario: false,
    errore: null,
  }),
  actions: {
    async loadInquilino(force = false): Promise<void> {
      if (this.inquilinoData && !force) return;
      this.loadingInquilino = true;
      this.errore = null;
      try {
        const { data } = await api.get<InquilinoDashboardData>('/api/v1/dashboard/inquilino/');
        this.inquilinoData = data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore nel caricamento';
      } finally {
        this.loadingInquilino = false;
      }
    },
    async loadProprietario(force = false): Promise<void> {
      if (this.proprietarioData && !force) return;
      this.loadingProprietario = true;
      this.errore = null;
      try {
        const { data } = await api.get<ProprietarioDashboardData>(
          '/api/v1/dashboard/proprietario/',
        );
        this.proprietarioData = data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore nel caricamento';
      } finally {
        this.loadingProprietario = false;
      }
    },
    invalida(): void {
      this.inquilinoData = null;
      this.proprietarioData = null;
    },
  },
});
