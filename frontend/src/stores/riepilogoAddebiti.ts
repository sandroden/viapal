import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { messaggioErrore } from 'src/utils/apiErrors';

// --- Tipi -----------------------------------------------------------------

/** Voce di addebito nel formato della home inquilino (`posizione_inquilino`). */
export interface VoceFE {
  tipo: string;
  id: number;
  descrizione: string;
  competenza: string;
  importo: number;
  importo_dovuto: number;
  importo_pagato: number;
  residuo: number;
  parziale: boolean;
  scadenza: string;
  stato: string;
  giorni_ritardo: number;
  semaforo: string;
}

export interface RiepilogoFE {
  tenant_id: number;
  tenant_nominativo: string;
  email: string;
  /** Nessuna assegnazione attiva: ex inquilino. Resta in anteprima ma è
   *  fuori dall'invio automatico — si spunta a mano per sollecitarlo. */
  uscito: boolean;
  /** C'è davvero qualcosa da chiedere (canone del mese o pendenti). */
  da_sollecitare: boolean;
  /** false = non parte da solo: o non c'è niente da sollecitare, o è uscito. */
  notificare: boolean;
  canone: VoceFE | null;
  pendenti: VoceFE[];
  in_attesa: VoceFE[];
  oggetto: string;
  corpo: string;
  corpo_html: string;
  canale: string;
  ultimo_invio_at: string | null;
  esito?: string;
  errore?: string;
  push?: { inviate: number; rimosse: number; errori: number };
}

export interface InvioRiepiloghiResponse {
  property_id: number;
  dry_run: boolean;
  from_email: string;
  giorni: number;
  totale: number;
  inviati: number;
  errori: number;
  push_inviate: number;
  senza_email: string[];
  non_inviati: string[];
  esclusi: string[];
  /** Ex inquilini con arretrati saltati dall'invio automatico. */
  ex_inquilini: string[];
  riepiloghi: RiepilogoFE[];
}

/**
 * Chi parte davvero. Le due selezioni sono speculari:
 * - inquilino **attivo**: parte di default, `escludi` lo toglie;
 * - **ex inquilino**: fermo di default, `includi` lo rimette (mai se non
 *   c'è nulla da sollecitare — il backend lo rifiuterebbe comunque).
 */
export function inviabile(
  r: RiepilogoFE,
  escludi: number[],
  includi: number[],
): boolean {
  if (!r.email) return false;
  if (r.uscito) return r.da_sollecitare && includi.includes(r.tenant_id);
  return r.notificare && !escludi.includes(r.tenant_id);
}

interface State {
  anteprima: InvioRiepiloghiResponse | null;
  loading: boolean;
  errore: string | null;
}

export const useRiepilogoAddebitiStore = defineStore('riepilogoAddebiti', {
  state: (): State => ({
    anteprima: null,
    loading: false,
    errore: null,
  }),
  actions: {
    /**
     * Un solo endpoint per anteprima e invio: con `dryRun` non parte nulla e
     * la risposta contiene il testo esatto delle email da approvare.
     * `escludi` sono **tenant_id** deselezionati a mano; `includi` sono ex
     * inquilini spuntati a mano, che altrimenti l'invio salterebbe.
     */
    async invia(
      dryRun: boolean,
      escludi: number[] = [],
      includi: number[] = [],
    ): Promise<InvioRiepiloghiResponse | null> {
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.post<InvioRiepiloghiResponse>(
          '/api/v1/riepilogo-addebiti/invia/',
          { dry_run: dryRun, escludi, includi },
        );
        // L'anteprima resta quella del dry-run: dopo un invio reale la
        // rileggiamo comunque, così i badge "già inviato il …" si aggiornano.
        this.anteprima = data;
        return data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore invio riepiloghi');
        return null;
      } finally {
        this.loading = false;
      }
    },

    reset(): void {
      this.anteprima = null;
      this.errore = null;
    },
  },
});
