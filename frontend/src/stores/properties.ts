import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { useAuthStore, type PropertyInfo, type RuoloProperty } from 'stores/auth';

// Chiave localStorage letta anche dall'interceptor axios (boot/axios.ts):
// tenerle allineate.
export const STORAGE_KEY = 'vp-property-id';

export interface Membro {
  id: number;
  user: number;
  username: string;
  email: string;
  nominativo: string;
  ruolo: RuoloProperty;
  invitato_da: number | null;
}

export interface Quota {
  id: number;
  owner: number;
  owner_nominativo: string;
  quota: string;
  valid_from: string;
  valid_to: string | null;
}

export interface PropertyDettaglio {
  id: number;
  nome: string;
  indirizzo: string;
  bank_account_utenze: number | null;
  owner_anticipa_cessioni: number | null;
  mio_ruolo: RuoloProperty | null;
  n_stanze: number;
}

export function activePropertyIdFromStorage(): number | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  const id = raw ? Number(raw) : NaN;
  return Number.isFinite(id) && id > 0 ? id : null;
}

export const usePropertiesStore = defineStore('properties', {
  state: () => ({
    activePropertyId: activePropertyIdFromStorage(),
  }),
  getters: {
    // Gli immobili accessibili arrivano già con /api/auth/user/.
    properties(): PropertyInfo[] {
      const auth = useAuthStore();
      return auth.user?.properties ?? [];
    },
    activeProperty(): PropertyInfo | null {
      return this.properties.find((p) => p.id === this.activePropertyId) ?? null;
    },
    mioRuolo(): RuoloProperty | null {
      return this.activeProperty?.ruolo ?? null;
    },
    isProprietarioAttivo(): boolean {
      return this.mioRuolo === 'proprietario';
    },
    hasMultiple(): boolean {
      return this.properties.length > 1;
    },
  },
  actions: {
    /**
     * Allinea l'immobile attivo a quelli accessibili: se quello persistito
     * non è più valido (revoca, altro utente sullo stesso browser) si
     * ripiega sul default. Chiamata dal guard del router dopo fetchMe.
     */
    sincronizza() {
      const auth = useAuthStore();
      const valid = this.properties.some((p) => p.id === this.activePropertyId);
      if (!valid) {
        const fallback = auth.user?.default_property_id ?? null;
        this.activePropertyId = fallback;
        if (fallback) localStorage.setItem(STORAGE_KEY, String(fallback));
        else localStorage.removeItem(STORAGE_KEY);
      }
    },
    /**
     * Cambio immobile = hard reload sulla home proprietari: azzera tutti gli
     * store Pinia (stesso pattern dell'impersonation), così nessuna cache
     * dell'immobile precedente sopravvive.
     */
    cambia(id: number) {
      if (id === this.activePropertyId) return;
      localStorage.setItem(STORAGE_KEY, String(id));
      window.location.assign('/p/');
    },
    async creaProperty(payload: {
      nome: string;
      indirizzo: string;
      ruolo_creatore: 'proprietario' | 'gestore';
    }): Promise<PropertyDettaglio> {
      const { data } = await api.post<PropertyDettaglio>('/api/v1/properties/', payload);
      return data;
    },
    async caricaDettaglio(id: number): Promise<PropertyDettaglio> {
      const { data } = await api.get<PropertyDettaglio>(`/api/v1/properties/${id}/`);
      return data;
    },
    async aggiornaProperty(
      id: number,
      payload: Partial<Pick<PropertyDettaglio, 'nome' | 'indirizzo'>>,
    ): Promise<PropertyDettaglio> {
      const { data } = await api.patch<PropertyDettaglio>(
        `/api/v1/properties/${id}/`,
        payload,
      );
      return data;
    },
    async caricaMembri(id: number): Promise<Membro[]> {
      const { data } = await api.get<Membro[]>(`/api/v1/properties/${id}/membri/`);
      return data;
    },
    async cambiaRuoloMembro(id: number, membershipId: number, ruolo: RuoloProperty) {
      await api.patch(`/api/v1/properties/${id}/membri/${membershipId}/`, { ruolo });
    },
    async rimuoviMembro(id: number, membershipId: number) {
      await api.delete(`/api/v1/properties/${id}/membri/${membershipId}/`);
    },
    async invitaMembro(
      id: number,
      payload: { email: string; ruolo: RuoloProperty; nominativo?: string },
    ) {
      const { data } = await api.post(`/api/v1/properties/${id}/inviti/`, payload);
      return data as { esito: string; email: string; creato: boolean };
    },
    async caricaQuote(id: number): Promise<Quota[]> {
      const { data } = await api.get<Quota[]>(`/api/v1/properties/${id}/quote/`);
      return data;
    },
    async salvaQuote(
      id: number,
      payload: { valid_from: string; quote: Array<{ user: number; quota: string }> },
    ): Promise<Quota[]> {
      const { data } = await api.post<Quota[]>(`/api/v1/properties/${id}/quote/`, payload);
      return data;
    },
  },
});
