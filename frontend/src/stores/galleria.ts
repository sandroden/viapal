import { defineStore } from 'pinia';
import { api } from 'boot/axios';

// --- Tipi -----------------------------------------------------------------

export interface FotoGalleria {
  id: number;
  url: string;
  didascalia: string;
}

export interface StanzaPubblica {
  id: number;
  nome: string;
  superficie_mq: string | null;
  colore: string;
  descrizione: string;
  disponibile: boolean;
  libera_dal: string | null;
  prezzo_mensile: string | null;
  ordinamento: number;
  foto: FotoGalleria[];
}

export interface AreaPubblica {
  id: number;
  nome: string;
  colore: string;
  descrizione: string;
  ordinamento: number;
  foto: FotoGalleria[];
}

export interface FactsPubblici {
  mq_totali?: number | string;
  n_camere?: number | string;
  n_bagni?: number | string;
  n_posti_letto?: number | string;
}

export interface PosizionePubblica {
  indirizzo?: string;
  mezzi?: string;
  mezzi_chips?: string[];
  parcheggio?: string;
  regole?: string;
}

export interface TestiPubblici {
  hero_eyebrow?: string;
  hero_titolo?: string;
  hero_indirizzo?: string;
  planimetria_nota?: string;
  facts?: FactsPubblici;
  posizione?: PosizionePubblica;
}

export interface GalleriaPubblica {
  id: number;
  nome: string;
  slug: string;
  indirizzo: string;
  testi_pubblici: TestiPubblici;
  foto_hero: string | null;
  foto_planimetria: string | null;
  foto_mappa: string | null;
  rooms: StanzaPubblica[];
  aree: AreaPubblica[];
}

interface State {
  galleria: GalleriaPubblica | null;
  loading: boolean;
  uploading: boolean;
  errore: string | null;
}

function messaggioErrore(e: unknown, fallback: string): string {
  const err = e as {
    response?: { data?: { detail?: string; image?: string[]; slug?: string[] } };
    message?: string;
  };
  const data = err?.response?.data;
  if (data) {
    if (data.detail) return data.detail;
    if (Array.isArray(data.image) && data.image.length) return String(data.image[0]);
    if (Array.isArray(data.slug) && data.slug.length) return String(data.slug[0]);
  }
  return err?.message ?? fallback;
}

export const useGalleriaStore = defineStore('galleria', {
  state: (): State => ({
    galleria: null,
    loading: false,
    uploading: false,
    errore: null,
  }),
  actions: {
    /** Carica il payload pubblico della galleria (nessuna autenticazione). */
    async fetchPublic(slug: string): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const { data } = await api.get<GalleriaPubblica>(
          `/api/v1/public/galleria/${slug}/`,
        );
        this.galleria = data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Galleria non trovata');
        this.galleria = null;
      } finally {
        this.loading = false;
      }
    },

    /** Ricarica la galleria dopo una modifica (uso interno). */
    async _refresh(): Promise<void> {
      if (this.galleria) await this.fetchPublic(this.galleria.slug);
    },

    /** Carica una foto legata a una camera (roomId) o a un ambiente comune
     *  (areaId). Accetta sia file (q-file/drag) sia blob incollati (Ctrl-V). */
    async uploadImage(payload: {
      propertyId: number;
      roomId?: number;
      areaId?: number;
      file: File;
      didascalia?: string;
    }): Promise<boolean> {
      this.uploading = true;
      this.errore = null;
      try {
        const form = new FormData();
        form.append('property', String(payload.propertyId));
        form.append('image', payload.file);
        if (payload.roomId) form.append('room', String(payload.roomId));
        if (payload.areaId) form.append('area', String(payload.areaId));
        if (payload.didascalia) form.append('didascalia', payload.didascalia);
        await api.post('/api/v1/gallery-images/', form);
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento immagine');
        return false;
      } finally {
        this.uploading = false;
      }
    },

    /** Crea un ambiente comune (cucina, soggiorno, bagni…). */
    async createArea(propertyId: number, nome: string): Promise<boolean> {
      this.errore = null;
      try {
        await api.post('/api/v1/gallery-areas/', { property: propertyId, nome });
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore creazione ambiente');
        return false;
      }
    },

    /** PATCH dei campi di un ambiente comune. */
    async patchArea(id: number, payload: Record<string, unknown>): Promise<boolean> {
      this.errore = null;
      try {
        await api.patch(`/api/v1/gallery-areas/${id}/`, payload);
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore salvataggio ambiente');
        return false;
      }
    },

    /** Elimina un ambiente comune (e le sue foto). */
    async deleteArea(id: number): Promise<boolean> {
      this.errore = null;
      try {
        await api.delete(`/api/v1/gallery-areas/${id}/`);
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore eliminazione ambiente');
        return false;
      }
    },

    /** Imposta un'immagine singleton dell'immobile (hero/planimetria/mappa). */
    async uploadSingolare(payload: {
      propertyId: number;
      campo: 'foto_hero' | 'foto_planimetria' | 'foto_mappa';
      file: File;
    }): Promise<boolean> {
      this.uploading = true;
      this.errore = null;
      try {
        const form = new FormData();
        form.append(payload.campo, payload.file);
        await api.patch(`/api/v1/properties/${payload.propertyId}/`, form);
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento immagine');
        return false;
      } finally {
        this.uploading = false;
      }
    },

    /** Elimina una foto della galleria. */
    async deleteImage(id: number): Promise<boolean> {
      this.errore = null;
      try {
        await api.delete(`/api/v1/gallery-images/${id}/`);
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore eliminazione immagine');
        return false;
      }
    },

    /** PATCH dei campi immobile (testi_pubblici, pubblica, indirizzo, immagini). */
    async patchProperty(
      id: number,
      payload: Record<string, unknown>,
    ): Promise<boolean> {
      this.errore = null;
      try {
        await api.patch(`/api/v1/properties/${id}/`, payload);
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore salvataggio');
        return false;
      }
    },

    /** PATCH dei campi galleria di una stanza. */
    async patchRoom(
      id: number,
      payload: Record<string, unknown>,
    ): Promise<boolean> {
      this.errore = null;
      try {
        await api.patch(`/api/v1/rooms/${id}/`, payload);
        await this._refresh();
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore salvataggio');
        return false;
      }
    },
  },
});
