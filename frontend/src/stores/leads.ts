import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { fetchAllPaginated, paramsClean } from 'src/utils/paginate';
import { messaggioErrore } from 'src/utils/apiErrors';

/** Esito del classificatore del bot. I campi possono mancare tutti: il post
 *  è testo libero scritto da una persona, non un modulo. */
export interface AnalisiLead {
  zona?: string | null;
  budget_max?: number | string | null;
  disponibile_da?: string | null;
  stanze_compatibili?: string[];
  motivo?: string | null;
}

export type StatoLead = 'nuovo' | 'contattato' | 'risposto' | 'scartato';

export interface Lead {
  id: number;
  post_id: string;
  group_id: string;
  group_label: string;
  author_name: string;
  author_url: string;
  permalink: string;
  link_messenger: string;
  testo: string;
  analisi: AnalisiLead;
  commento_proposto: string;
  privato_proposto: string;
  seen_at: string;
  stato: StatoLead;
  stato_display: string;
  preso_da: number | null;
  preso_da_nome: string;
  preso_at: string | null;
  contattato_at: string | null;
  note: string;
  /** Francobollo incollato a mano: data URI, non un URL a un file. */
  foto: string;
  created_at: string;
}

export interface RiepilogoLead {
  totale: number;
  per_stato: Record<StatoLead, number>;
  gruppi: { id: string; nome: string }[];
}

/** Come si presenta uno stato: etichetta, colore Quasar per i controlli, e
 *  l'aspetto che ha sulla card (`tono` = suffisso della classe, `icona`).
 *  Sta qui e non nella pagina perché la card e i filtri devono dire la stessa
 *  cosa con gli stessi colori. */
export const STATI: {
  value: StatoLead;
  label: string;
  colore: string;
  tono: string;
  icona: string;
}[] = [
  { value: 'nuovo', label: 'Da contattare', colore: 'primary', tono: 'nuovo', icona: 'schedule' },
  { value: 'contattato', label: 'Contattato', colore: 'info', tono: 'contattato', icona: 'send' },
  { value: 'risposto', label: 'Ha risposto', colore: 'positive', tono: 'risposto', icona: 'forum' },
  { value: 'scartato', label: 'Scartato', colore: 'grey', tono: 'scartato', icona: 'block' },
];

interface State {
  leads: Lead[];
  riepilogo: RiepilogoLead | null;
  loading: boolean;
  errore: string | null;
}

const ENDPOINT = '/api/v1/leads/';

export const useLeadsStore = defineStore('leads', {
  state: (): State => ({
    leads: [],
    riepilogo: null,
    loading: false,
    errore: null,
  }),

  actions: {
    /** Carica la lista. Tutte le pagine: una campagna può produrre qualche
     *  centinaio di post e fermarsi alla prima ne nasconderebbe una parte
     *  senza dirlo. */
    async fetch(filtri: { stato?: string; gruppo?: string; preso_da?: string } = {}) {
      this.loading = true;
      this.errore = null;
      try {
        const qs = new URLSearchParams(paramsClean(filtri)).toString();
        this.leads = await fetchAllPaginated<Lead>(qs ? `${ENDPOINT}?${qs}` : ENDPOINT);
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore nel caricamento dei lead');
      } finally {
        this.loading = false;
      }
    },

    async fetchRiepilogo() {
      try {
        const { data } = await api.get<RiepilogoLead>(`${ENDPOINT}riepilogo/`);
        this.riepilogo = data;
      } catch {
        // Il riepilogo alimenta solo i contatori dei filtri: se non arriva,
        // la pagina resta perfettamente usabile.
        this.riepilogo = null;
      }
    },

    /** Sostituisce in lista il lead aggiornato dal backend. */
    _aggiorna(lead: Lead) {
      const i = this.leads.findIndex((l) => l.id === lead.id);
      if (i >= 0) this.leads.splice(i, 1, lead);
    },

    async cambiaStato(lead: Lead, stato: StatoLead) {
      const { data } = await api.patch<Lead>(`${ENDPOINT}${lead.id}/`, { stato });
      this._aggiorna(data);
      return data;
    },

    async salvaNote(lead: Lead, note: string) {
      const { data } = await api.patch<Lead>(`${ENDPOINT}${lead.id}/`, { note });
      this._aggiorna(data);
      return data;
    },

    /** La fotina del profilo, o stringa vuota per toglierla. */
    async salvaFoto(lead: Lead, foto: string): Promise<{ ok: boolean; messaggio?: string }> {
      try {
        const { data } = await api.patch<Lead>(`${ENDPOINT}${lead.id}/`, { foto });
        this._aggiorna(data);
        return { ok: true };
      } catch (e: unknown) {
        return { ok: false, messaggio: messaggioErrore(e, 'Foto non salvata') };
      }
    },

    /** «Lo contatto io». Il 409 non è un errore da nascondere: è l'altro che
     *  l'ha preso un attimo prima, e va detto. */
    async prendi(lead: Lead): Promise<{ ok: boolean; messaggio?: string }> {
      try {
        const { data } = await api.post<Lead>(`${ENDPOINT}${lead.id}/prendi/`);
        this._aggiorna(data);
        return { ok: true };
      } catch (e: unknown) {
        await this.fetch();
        return { ok: false, messaggio: messaggioErrore(e, 'Non è stato possibile prenderlo') };
      }
    },

    async rilascia(lead: Lead): Promise<{ ok: boolean; messaggio?: string }> {
      try {
        const { data } = await api.post<Lead>(`${ENDPOINT}${lead.id}/rilascia/`);
        this._aggiorna(data);
        return { ok: true };
      } catch (e: unknown) {
        return { ok: false, messaggio: messaggioErrore(e, 'Non è stato possibile lasciarlo') };
      }
    },

    /** Fine campagna: i lead si cancellano, qui come sul portatile del bot. */
    async chiudiCampagna(): Promise<number> {
      const { data } = await api.post<{ cancellati: number }>(
        `${ENDPOINT}chiudi-campagna/`,
        { conferma: true },
      );
      this.leads = [];
      await this.fetchRiepilogo();
      return data.cancellati;
    },
  },
});
