import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import type { SemaforoLivello } from 'src/types/semaforo';

export type TipoPagamento = 'rent' | 'utility_charge' | 'extra';

export interface DatiPagamento {
  beneficiario: string;
  iban: string;
  banca: string;
  causale: string;
}

export interface DaPagareItem {
  tipo: TipoPagamento;
  id: number;
  descrizione: string;
  importo: number;
  importo_dovuto: number;
  importo_pagato: number;
  residuo: number;
  parziale: boolean;
  scadenza: string;
  stato: string;
  giorni_ritardo: number;
  semaforo: SemaforoLivello;
  pagamento: DatiPagamento | null;
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
  deposito_versato?: string | null;
  data_versamento_deposito?: string | null;
  deposito_da_restituire?: string | null;
  data_restituzione_prevista?: string | null;
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

export type TipoBilancio = 'entrate' | 'uscite';

export interface BilancioDettaglioEntrata {
  id: number;
  tipo: TipoPagamento;
  causale: string;
  causale_label: string;
  tenant: string;
  descrizione: string;
  importo_dovuto: number;
  importo_pagato: number;
  scadenza: string | null;
  data_pagamento: string | null;
  stato: string;
}

export interface BilancioDettaglioUscita {
  id: number;
  data: string;
  categoria: string;
  supplier: string | null;
  descrizione: string;
  importo: number;
  bolletta_id?: number | null;
  bolletta_numero?: string | null;
  bolletta_prodotto?: 'gas' | 'luce' | 'acqua' | null;
  file_pdf?: string | null;
}

export interface BilancioDettaglioResponse {
  owner_id: number;
  owner_nominativo: string;
  anno: number;
  tipo: TipoBilancio;
  totale: number;
  righe: BilancioDettaglioEntrata[] | BilancioDettaglioUscita[];
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
  bilancioDettaglio: Record<string, BilancioDettaglioResponse>;
  loadingInquilino: boolean;
  loadingProprietario: boolean;
  loadingBilancioDettaglio: boolean;
  errore: string | null;
}

function chiaveBilancio(ownerId: number, anno: number, tipo: TipoBilancio): string {
  return `${ownerId}-${anno}-${tipo}`;
}

function chiavePeriodo(anno: number, mese: number): string {
  return `${anno}-${mese}`;
}

export const useDashboardStore = defineStore('dashboard', {
  state: (): State => ({
    inquilinoData: null,
    proprietarioData: null,
    proprietarioByPeriodo: {},
    bilancioDettaglio: {},
    loadingInquilino: false,
    loadingProprietario: false,
    loadingBilancioDettaglio: false,
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
    async loadDettaglioBilancio(
      ownerId: number,
      anno: number,
      tipo: TipoBilancio,
      force = false,
    ): Promise<BilancioDettaglioResponse | null> {
      const key = chiaveBilancio(ownerId, anno, tipo);
      const cached = this.bilancioDettaglio[key];
      if (cached && !force) return cached;
      this.loadingBilancioDettaglio = true;
      this.errore = null;
      try {
        const { data } = await api.get<BilancioDettaglioResponse>(
          `/api/v1/dashboard/proprietario/${ownerId}/dettaglio-bilancio/`,
          { params: { anno, tipo } },
        );
        this.bilancioDettaglio[key] = data;
        return data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore nel caricamento';
        return null;
      } finally {
        this.loadingBilancioDettaglio = false;
      }
    },
    invalida(): void {
      this.inquilinoData = null;
      this.proprietarioData = null;
      this.proprietarioByPeriodo = {};
      this.bilancioDettaglio = {};
    },
  },
});
