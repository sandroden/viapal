import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export type NotaRiga = 'ok' | 'non_pagata' | 'parziale' | 'eccesso';

export interface RendicontoAllocazione {
  data: string;
  bonifico_totale: number;
  quota: number;
  split: boolean;
  // resto del bonifico (versato e mai imputato): valorizzato solo
  // sulla riga portante, mostrato come riga propria sotto il bonifico
  resto: number;
}

export interface RendicontoRiga {
  data: string | null;
  mese: string | null;
  scadenza: string | null;
  descrizione: string;
  dovuto: number;
  pagato: number;
  // differenza ONESTA della voce = pagato − dovuto
  diff: number;
  diff_mese: number | null;
  nota: NotaRiga;
  stato: string;
  data_pagamento: string | null;
  allocazioni: RendicontoAllocazione[];
}

export interface RendicontoParzialeAnno {
  anno: number;
  dovuto: number;
  pagato: number;
  // saldo-imputazioni (pagato − dovuto): nota tecnica "da riconciliare"
  saldo: number;
  // resti dei bonifici dell'anno (versato e mai imputato a nulla)
  resto: number;
  // sbilancio reale dell'anno = saldo + resto
  saldo_anno: number;
  // progressivo cumulato cronologico (fino a fine quell'anno)
  saldo_progressivo: number;
}

export interface RendicontoImputazione {
  descrizione: string;
  causale: string;
  quota: number;
}

export interface RendicontoVersamento {
  data: string;
  descrizione: string;
  importo: number;
  imputato: number;
  imputazioni: RendicontoImputazione[];
}

export interface RendicontoSezione {
  causale: string;
  label: string;
  righe: RendicontoRiga[];
  dovuto: number;
  pagato: number;
  saldo: number;
}

export interface RendicontoMovimentoDeposito {
  data: string | null;
  descrizione: string;
  importo: number;
  pagato: number;
  stato: string;
}

export interface Rendiconto {
  tenant: {
    id: number;
    nominativo: string;
    codice_fiscale: string | null;
    email: string | null;
  };
  periodo: { da: string | null; a: string | null };
  emesso_il: string;
  sezioni: RendicontoSezione[];
  totali: {
    dovuto: number;
    pagato: number;
    saldo: number;
    resto: number;
    sbilancio_reale: number;
  };
  parziali_anno: RendicontoParzialeAnno[];
  versamenti: RendicontoVersamento[];
  totale_versato: number;
  deposito: {
    versato: number;
    data_versamento: string | null;
    da_restituire: number;
    override: boolean;
    data_restituzione_prevista: string | null;
    restituito_effettivo: boolean;
    netto_da_restituire: number;
    residuo_debito: number;
    movimenti: RendicontoMovimentoDeposito[];
  };
}

interface State {
  byTenant: Record<number, Rendiconto>;
  loading: boolean;
  errore: string | null;
}

export const useRendicontoStore = defineStore('rendiconto', {
  state: (): State => ({
    byTenant: {},
    loading: false,
    errore: null,
  }),
  actions: {
    async load(tenantId: number, force = false): Promise<void> {
      if (this.byTenant[tenantId] && !force) return;
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<Rendiconto>(
          `/api/v1/tenants/${tenantId}/rendiconto/`,
        );
        this.byTenant[tenantId] = data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore nel caricamento';
      } finally {
        this.loading = false;
      }
    },
    get(tenantId: number): Rendiconto | null {
      return this.byTenant[tenantId] ?? null;
    },
  },
});
