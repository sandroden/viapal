import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';
import { fetchAllPaginated } from 'src/utils/paginate';

/** Una voce del pacchetto: o un documento esponibile, o un testo scritto a
 *  mano. Mai entrambi — il backend rifiuta la voce ibrida. */
export interface VoceLink {
  id: number;
  share: number;
  ordine: number;
  titolo: string;
  titolo_effettivo: string;
  tipo: 'documento' | 'testo';
  documento: number | null;
  documento_titolo: string;
  documento_file: string;
  corpo_md: string;
  corpo_html: string;
}

export interface LinkLettura {
  id: number;
  property: number;
  token: string;
  url_pubblico: string;
  destinatario: string;
  tenant: number | null;
  introduzione: string;
  /** La premessa resa e sanitizzata dal backend: si mostra questa, mai il
   *  markdown grezzo. */
  introduzione_html: string;
  attivo: boolean;
  visite: number;
  ultima_visita: string | null;
  voci: VoceLink[];
  created_at: string;
}

const SHARES = '/api/v1/document-shares/';
const VOCI = '/api/v1/share-items/';

interface State {
  link: LinkLettura[];
  loading: boolean;
  salvataggio: boolean;
  errore: string | null;
}

export const useLinkLetturaStore = defineStore('linkLettura', {
  state: (): State => ({ link: [], loading: false, salvataggio: false, errore: null }),

  actions: {
    async fetch(): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        this.link = await fetchAllPaginated<LinkLettura>(SHARES);
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento link di lettura.');
      } finally {
        this.loading = false;
      }
    },

    /** Rilegge un solo link: dopo ogni modifica alle voci il server è la
     *  fonte (ordine, titolo effettivo, HTML reso e sanitizzato). */
    async ricarica(id: number): Promise<void> {
      try {
        const { data } = await api.get<LinkLettura>(`${SHARES}${id}/`);
        this._sostituisci(data);
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore aggiornamento link.');
      }
    },

    _sostituisci(link: LinkLettura) {
      const i = this.link.findIndex((l) => l.id === link.id);
      if (i >= 0) this.link.splice(i, 1, link);
      else this.link.unshift(link);
    },

    async crea(payload: {
      destinatario: string;
      introduzione?: string;
      tenant?: number | null;
    }): Promise<LinkLettura | null> {
      this.salvataggio = true;
      this.errore = null;
      try {
        const { data } = await api.post<LinkLettura>(SHARES, payload);
        this._sostituisci(data);
        return data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Creazione del link non riuscita.');
        return null;
      } finally {
        this.salvataggio = false;
      }
    },

    async aggiorna(id: number, payload: Partial<LinkLettura>): Promise<boolean> {
      this.errore = null;
      try {
        const { data } = await api.patch<LinkLettura>(`${SHARES}${id}/`, payload);
        this._sostituisci(data);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Aggiornamento non riuscito.');
        return false;
      }
    },

    async elimina(id: number): Promise<boolean> {
      this.errore = null;
      try {
        await api.delete(`${SHARES}${id}/`);
        this.link = this.link.filter((l) => l.id !== id);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Eliminazione non riuscita.');
        return false;
      }
    },

    /** Revoca: il link resta in elenco (si sa a chi era stato mandato) ma
     *  l'URL già in giro smette di funzionare. */
    async cambiaAttivo(id: number, attivo: boolean): Promise<boolean> {
      this.errore = null;
      try {
        const azione = attivo ? 'riattiva' : 'revoca';
        const { data } = await api.post<LinkLettura>(`${SHARES}${id}/${azione}/`);
        this._sostituisci(data);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Operazione non riuscita.');
        return false;
      }
    },

    async aggiungiVoce(payload: {
      share: number;
      documento?: number;
      titolo?: string;
      corpo_md?: string;
    }): Promise<boolean> {
      this.salvataggio = true;
      this.errore = null;
      try {
        await api.post(VOCI, payload);
        await this.ricarica(payload.share);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Voce non aggiunta.');
        return false;
      } finally {
        this.salvataggio = false;
      }
    },

    async aggiornaVoce(
      voce: VoceLink,
      payload: { titolo?: string; corpo_md?: string },
    ): Promise<boolean> {
      this.salvataggio = true;
      this.errore = null;
      try {
        await api.patch(`${VOCI}${voce.id}/`, payload);
        await this.ricarica(voce.share);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Modifica non riuscita.');
        return false;
      } finally {
        this.salvataggio = false;
      }
    },

    async eliminaVoce(voce: VoceLink): Promise<boolean> {
      this.errore = null;
      try {
        await api.delete(`${VOCI}${voce.id}/`);
        await this.ricarica(voce.share);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Eliminazione non riuscita.');
        return false;
      }
    },

    /** Riordino in un colpo solo: la lista degli id nell'ordine voluto. */
    async riordina(id: number, ids: number[]): Promise<boolean> {
      this.errore = null;
      try {
        const { data } = await api.post<LinkLettura>(`${SHARES}${id}/riordina/`, {
          voci: ids,
        });
        this._sostituisci(data);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Riordino non riuscito.');
        return false;
      }
    },

    /** La proposta con cui si apre l'editor di un chiarimento nuovo.
     *
     *  Viene dal backend e non da una costante qui: è testo, non
     *  interfaccia, e il giorno in cui servirà diverso da immobile a
     *  immobile cambia là senza toccare questa pagina. Se la richiesta
     *  fallisce si apre vuoto: una proposta mancante non deve impedire di
     *  scrivere. */
    async testoPredefinito(): Promise<{ titolo: string; corpo_md: string }> {
      try {
        const { data } = await api.get<{ titolo: string; corpo_md: string }>(
          `${SHARES}testo-predefinito/`,
        );
        return data;
      } catch {
        return { titolo: '', corpo_md: '' };
      }
    },

    /** Anteprima del markdown resa dal backend: lo stesso renderer e lo
     *  stesso sanitizzatore della pagina pubblica. Un renderer JS a parte
     *  farebbe mentire l'anteprima. */
    async anteprimaMarkdown(corpoMd: string): Promise<string> {
      try {
        const { data } = await api.post<{ html: string }>(
          `${SHARES}anteprima-markdown/`,
          { corpo_md: corpoMd },
        );
        return data.html;
      } catch {
        return '';
      }
    },
  },
});
