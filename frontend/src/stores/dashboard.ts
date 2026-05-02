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
  username?: string;
  email?: string;
  email_alt?: string;
  telefono?: string;
  codice_fiscale?: string;
  giorno_pagamento_affitto?: number;
  frequenza_conguagli?: string;
  frequenza_conguagli_display?: string;
  note_pagamento?: string;
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
  incasso_anno: number;
  incasso_mese: number;
  spese_anno: number;
  ritardi_count: number;
  in_scadenza_count: number;
}

export interface IncassoDettaglio {
  rent: number;
  utility: number;
  extra: number;
  totale: number;
}

export interface BreakdownTenantRow {
  tenant: string;
  rent: number;
  utility: number;
  extra: number;
  totale: number;
}

export interface SpeseDettaglioRow {
  nome: string;
  importo: number;
}

export interface SpeseDettaglio {
  per_categoria: SpeseDettaglioRow[];
  per_owner: SpeseDettaglioRow[];
  totale: number;
}

export interface BilancioProprietario {
  owner_id: number;
  nominativo: string;
  entrate_rent: number;
  entrate_utility: number;
  entrate_extra: number;
  entrate_totali: number;
  uscite: number;
  uscite_dettaglio: Record<string, number>;
  saldo: number;
}

export interface ProprietarioDashboardData {
  anno: number;
  mese: number;
  is_storico: boolean;
  kpi: ProprietarioKpi;
  incasso_anno_dettaglio: IncassoDettaglio;
  incasso_mese_dettaglio: IncassoDettaglio;
  spese_anno_dettaglio: SpeseDettaglio;
  bilancio_proprietari: BilancioProprietario[];
  breakdown_incassi: BreakdownTenantRow[];
  ritardi: ProprietarioRiga[];
  in_scadenza: ProprietarioRiga[];
  finestra_scadenza_giorni?: number;
}

interface State {
  inquilinoData: InquilinoDashboardData | null;
  proprietarioData: ProprietarioDashboardData | null;
  proprietarioByPeriodo: Record<string, ProprietarioDashboardData>;
  loadingInquilino: boolean;
  loadingProprietario: boolean;
  errore: string | null;
}

function chiavePeriodo(anno: number, mese: number): string {
  return `${anno}-${mese}`;
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): State => ({
    inquilinoData: null,
    proprietarioData: null,
    proprietarioByPeriodo: {},
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
    async loadProprietario(anno?: number, mese?: number, force = false): Promise<void> {
      const oggi = new Date();
      const a = anno ?? oggi.getFullYear();
      const m = mese ?? oggi.getMonth() + 1;
      const key = chiavePeriodo(a, m);
      const cached = this.proprietarioByPeriodo[key];
      if (cached && !force) {
        this.proprietarioData = cached;
        return;
      }
      this.loadingProprietario = true;
      this.errore = null;
      try {
        const { data } = await api.get<ProprietarioDashboardData>(
          '/api/v1/dashboard/proprietario/',
          { params: { anno: a, mese: m } },
        );
        this.proprietarioByPeriodo[key] = data;
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
      this.proprietarioByPeriodo = {};
    },
  },
});
