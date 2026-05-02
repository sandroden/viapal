import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export interface QuadroPerTenant {
  giorni: number;
  importo: number;
  stato: string | null;
}

export interface QuadroRiga {
  periodo_id: number;
  periodo_label: string;
  periodo_da: string;
  periodo_a: string;
  totale_periodo: number;
  per_tenant: Record<string, QuadroPerTenant>;
}

export interface QuadroAnnuale {
  anno: number;
  tenants: string[];
  righe: QuadroRiga[];
  totale_anno_per_tenant: Record<string, number>;
  totale_anno: number;
}

interface State {
  byAnno: Record<number, QuadroAnnuale>;
  loading: boolean;
  errore: string | null;
}

export const useQuadroStore = defineStore('quadro', {
  state: (): State => ({
    byAnno: {},
    loading: false,
    errore: null,
  }),
  actions: {
    async loadAnno(anno: number, force = false): Promise<QuadroAnnuale | null> {
      if (this.byAnno[anno] && !force) return this.byAnno[anno];
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<QuadroAnnuale>(`/api/v1/quadro-annuale/${anno}/`);
        this.byAnno = { ...this.byAnno, [anno]: data };
        return data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore';
        return null;
      } finally {
        this.loading = false;
      }
    },
  },
});
