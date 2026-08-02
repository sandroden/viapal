import { defineStore } from 'pinia';
import { api } from 'boot/axios';

/** Modello di un documento generabile: il testo sta in tabella, uno per
 *  immobile, perché cambia da proprietà a proprietà e a cambiarlo è il
 *  proprietario. Nel repository c'è solo un esempio da adattare. */
export interface ModelloDocumento {
  id: number;
  property: number;
  codice: string;
  codice_display: string;
  nome: string;
  corpo_html: string;
  note: string;
  updated_at: string;
}

export interface Segnaposto {
  chiave: string;
  etichetta: string;
  fonte: string;
  obbligatorio: boolean;
}

/** I due documenti generabili, nell'ordine in cui compaiono. */
export const CODICI_DOCUMENTO = [
  { codice: 'atto_subentro_locazione', label: 'Atto di subentro nel contratto' },
  { codice: 'cessione_fabbricato', label: 'Comunicazione di cessione di fabbricato' },
] as const;

const ENDPOINT = '/api/v1/document-templates/';

interface State {
  modelli: ModelloDocumento[];
  loading: boolean;
  salvataggio: boolean;
  errore: string | null;
}

function messaggioErrore(e: unknown, fallback: string): string {
  const err = e as { response?: { data?: Record<string, string[] | string> } };
  const dati = err?.response?.data;
  if (!dati) return fallback;
  const primo = Object.values(dati)[0];
  if (Array.isArray(primo)) return primo[0] ?? fallback;
  return typeof primo === 'string' ? primo : fallback;
}

export const useModelliDocumentoStore = defineStore('modelliDocumento', {
  state: (): State => ({ modelli: [], loading: false, salvataggio: false, errore: null }),

  getters: {
    /** Modello caricato per un documento, se esiste. */
    perCodice:
      (s) =>
      (codice: string): ModelloDocumento | null =>
        s.modelli.find((m) => m.codice === codice) ?? null,
  },

  actions: {
    async fetch(): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<ModelloDocumento[]>(ENDPOINT);
        this.modelli = data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento modelli.');
      } finally {
        this.loading = false;
      }
    },

    /** Crea o sostituisce il modello di un documento. */
    async salva(codice: string, corpoHtml: string, nome = ''): Promise<boolean> {
      this.salvataggio = true;
      this.errore = null;
      const esistente = this.modelli.find((m) => m.codice === codice);
      try {
        if (esistente) {
          await api.patch(`${ENDPOINT}${esistente.id}/`, {
            corpo_html: corpoHtml,
            ...(nome ? { nome } : {}),
          });
        } else {
          await api.post(ENDPOINT, { codice, corpo_html: corpoHtml, nome });
        }
        await this.fetch();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Salvataggio non riuscito.');
        return false;
      } finally {
        this.salvataggio = false;
      }
    },

    async elimina(id: number): Promise<boolean> {
      this.errore = null;
      try {
        await api.delete(`${ENDPOINT}${id}/`);
        await this.fetch();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Eliminazione non riuscita.');
        return false;
      }
    },

    /** HTML di esempio versionato nel repository, da adattare. */
    async esempio(codice: string): Promise<string> {
      const { data } = await api.get<{ corpo_html: string }>(`${ENDPOINT}esempio/`, {
        params: { codice },
      });
      return data.corpo_html;
    },

    /** Segnaposto disponibili in quel documento, derivati dal generatore. */
    async segnaposto(codice: string): Promise<{ titolo: string; segnaposto: Segnaposto[] }> {
      const { data } = await api.get<{ titolo: string; segnaposto: Segnaposto[] }>(
        `${ENDPOINT}segnaposto/`,
        { params: { codice } },
      );
      return data;
    },
  },
});
