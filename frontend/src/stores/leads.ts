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

export type StatoLead = 'nuovo' | 'contattato' | 'risposto' | 'perso' | 'scartato';

/** Da dove arriva il contatto. `fb_gruppo` è l'unico che il bot sa produrre;
 *  gli altri li inserisce una persona. */
export type CanaleLead = 'fb_gruppo' | 'fb_post' | 'subito' | 'idealista' | 'immobiliare' | 'altro';

export interface Lead {
  id: number;
  post_id: string;
  group_id: string;
  group_label: string;
  canale: CanaleLead;
  canale_display: string;
  author_name: string;
  author_url: string;
  permalink: string;
  link_messenger: string;
  /** Telefono, email o nick sulla piattaforma. Vuoto per i lead del bot. */
  contatto: string;
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
  risposto_at: string | null;
  note: string;
  /** Francobollo incollato a mano: data URI, non un URL a un file. */
  foto: string;
  /** Inserito a mano (nessun post_id): è l'unico che si può modificare e
   *  cancellare dalla pagina. */
  manuale: boolean;
  created_at: string;
}

export interface RiepilogoLead {
  totale: number;
  /** nuovo + contattato + risposto: non è uno stato, è il filtro di default. */
  attivi: number;
  per_stato: Record<StatoLead, number>;
  gruppi: { id: string; nome: string }[];
  canali: { id: CanaleLead; nome: string; n: number }[];
}

/** Una riga delle statistiche. `contattati` e `risposto` contano le date
 *  (contattato_at, risposto_at), non lo stato attuale: chi ha risposto e poi
 *  ha trovato altro resta una risposta ottenuta. */
export interface RigaStatistica {
  totale: number;
  contattati: number;
  risposto: number;
  attivi: number;
  persi: number;
  scartati: number;
  ultimo_at: string | null;
}

export interface StatisticaCanale extends RigaStatistica {
  canale: CanaleLead;
  nome: string;
  /** Solo per fb_gruppo: una riga per gruppo Facebook. */
  gruppi?: (RigaStatistica & { id: string; nome: string })[];
}

export interface StatisticheLead {
  totale: RigaStatistica;
  canali: StatisticaCanale[];
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
  { value: 'perso', label: 'Ha trovato altro', colore: 'warning', tono: 'perso', icona: 'directions_walk' },
  { value: 'scartato', label: 'Scartato', colore: 'grey', tono: 'scartato', icona: 'block' },
];

/** Gli stati in cui il contatto è ancora da lavorare: il filtro "Attivi". */
export const STATI_ATTIVI: StatoLead[] = ['nuovo', 'contattato', 'risposto'];

export const CANALI: { value: CanaleLead; label: string; icona: string }[] = [
  { value: 'fb_gruppo', label: 'Gruppo Facebook', icona: 'groups' },
  { value: 'fb_post', label: 'Risposta a un mio post', icona: 'reply' },
  { value: 'subito', label: 'Subito.it', icona: 'storefront' },
  { value: 'idealista', label: 'Idealista', icona: 'apartment' },
  { value: 'immobiliare', label: 'Immobiliare.it', icona: 'home_work' },
  { value: 'altro', label: 'Altro', icona: 'more_horiz' },
];

/** Quello che una persona può scrivere di un lead manuale, in creazione e in
 *  modifica. Il resto (stato, note, foto) passa dalle azioni dedicate. */
export interface DatiLeadManuale {
  canale: CanaleLead;
  author_name: string;
  contatto?: string;
  author_url?: string;
  permalink?: string;
  testo?: string;
  analisi?: Pick<AnalisiLead, 'zona' | 'budget_max' | 'disponibile_da'>;
  note?: string;
  stato?: StatoLead;
}

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
    async fetch(
      filtri: { stato?: string; canale?: string; gruppo?: string; preso_da?: string } = {},
    ) {
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

    /** Non passa dallo stato: la pagina delle statistiche è di sola lettura
     *  e non ha bisogno di sopravvivere al cambio di rotta. */
    async fetchStatistiche(): Promise<StatisticheLead> {
      const { data } = await api.get<StatisticheLead>(`${ENDPOINT}statistiche/`);
      return data;
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

    /** Lead inserito a mano. Va in testa alla lista: è appena stato scritto
     *  ed è quello che si vuole vedere, qualunque sia l'ordine del server. */
    async crea(dati: DatiLeadManuale): Promise<Lead> {
      const { data } = await api.post<Lead>(ENDPOINT, dati);
      this.leads.unshift(data);
      return data;
    },

    /** Solo i campi descrittivi di un lead manuale: stato, note e foto hanno
     *  le loro azioni. */
    async modifica(lead: Lead, dati: Partial<DatiLeadManuale>): Promise<Lead> {
      const { data } = await api.patch<Lead>(`${ENDPOINT}${lead.id}/`, dati);
      this._aggiorna(data);
      return data;
    },

    /** Solo per i manuali: sui lead del bot il server risponde 409, e
     *  l'errore arriva a chi chiama con il suo messaggio. */
    async elimina(lead: Lead): Promise<void> {
      await api.delete(`${ENDPOINT}${lead.id}/`);
      this.leads = this.leads.filter((l) => l.id !== lead.id);
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
