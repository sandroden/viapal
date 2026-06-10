import { defineStore } from 'pinia';
import { api } from 'boot/axios';

export interface RicaviBlocco {
  rent: number;
  utility: number;
  extra: number;
  totale: number;
}

export interface ContoBlocco {
  ricavi: RicaviBlocco;
  spese_ordinarie: number;
  margine_operativo: number;
  spese_straordinarie: number;
  utile: number;
}

export interface ContoBloccoCompetenza extends ContoBlocco {
  non_incassato: number;
  non_incassato_voci: number;
  insoluti: number;
}

export interface VoceCategoria {
  nome: string;
  importo: number;
}

export interface UtileProQuota {
  owner_id: number;
  nominativo: string;
  quota: number;
  utile_cassa: number;
  utile_competenza: number;
}

export interface SerieAnno {
  anno: number;
  ricavi: number;
  spese: number;
  utile: number;
}

export interface OccupazioneStanza {
  stanza: string;
  giorni_occupati: number;
  giorni_finestra: number;
  tasso: number;
}

export interface ContoEconomicoData {
  anno: number;
  anni_disponibili: number[];
  cassa: ContoBlocco;
  competenza: ContoBloccoCompetenza;
  spese_dettaglio: {
    ordinarie: VoceCategoria[];
    straordinarie: VoceCategoria[];
  };
  utile_pro_quota: UtileProQuota[];
  serie_anni: SerieAnno[];
  occupazione: {
    tasso_medio: number | null;
    per_stanza: OccupazioneStanza[];
  };
}

interface State {
  data: ContoEconomicoData | null;
  loading: boolean;
  errore: string | null;
}

export const useContoEconomicoStore = defineStore('contoEconomico', {
  state: (): State => ({
    data: null,
    loading: false,
    errore: null,
  }),
  actions: {
    async fetch(anno?: number): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const params: Record<string, number> = {};
        if (anno) params.anno = anno;
        const { data } = await api.get<ContoEconomicoData>(
          '/api/v1/dashboard/conto-economico/',
          { params },
        );
        this.data = data;
      } catch (e: unknown) {
        this.errore = (e as Error)?.message ?? 'Errore caricamento conto economico';
      } finally {
        this.loading = false;
      }
    },
  },
});
