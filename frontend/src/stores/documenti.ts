import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { fetchAllPaginated } from 'src/utils/paginate';

// --- Tipi -----------------------------------------------------------------

export type TipoDocumento =
  | 'carta_identita'
  | 'codice_fiscale'
  | 'passaporto'
  | 'permesso_soggiorno'
  | 'contratto_lavoro'
  | 'altro';

export interface DocumentoFE {
  id: number;
  tenant: number;
  tenant_nominativo: string;
  tipo: TipoDocumento;
  tipo_display: string;
  file: string;
  descrizione: string;
  data_scadenza: string | null;
  scaduto: boolean;
  created_at: string;
}

interface State {
  documenti: DocumentoFE[];
  loading: boolean;
  uploading: boolean;
  errore: string | null;
}

function messaggioErrore(e: unknown, fallback: string): string {
  const err = e as {
    response?: { data?: { detail?: string; file?: string[]; tipo?: string[] } };
    message?: string;
  };
  const data = err?.response?.data;
  if (data) {
    if (data.detail) return data.detail;
    if (Array.isArray(data.file) && data.file.length) return String(data.file[0]);
    if (Array.isArray(data.tipo) && data.tipo.length) return String(data.tipo[0]);
  }
  return err?.message ?? fallback;
}

export const useDocumentiStore = defineStore('documenti', {
  state: (): State => ({
    documenti: [],
    loading: false,
    uploading: false,
    errore: null,
  }),
  actions: {
    /** Carica i documenti. Senza ``tenantId`` l'API restituisce i propri
     *  (inquilino) o tutti (proprietario); con ``tenantId`` filtra per
     *  inquilino (uso lato proprietario). */
    async fetch(tenantId?: number): Promise<void> {
      this.loading = true;
      this.errore = null;
      try {
        const url = tenantId
          ? `/api/v1/tenant-documents/?tenant=${tenantId}`
          : '/api/v1/tenant-documents/';
        this.documenti = await fetchAllPaginated<DocumentoFE>(url);
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento documenti');
      } finally {
        this.loading = false;
      }
    },

    /** Carica più file in un'unica azione, creando un record per file
     *  (stesso tipo/descrizione/scadenza). Ritorna il numero di successi e
     *  fallimenti. */
    async caricaMulti(payload: {
      files: File[];
      tipo: TipoDocumento;
      descrizione?: string;
      dataScadenza?: string | null;
      tenantId?: number;
    }): Promise<{ ok: number; falliti: number }> {
      this.uploading = true;
      this.errore = null;
      let ok = 0;
      let falliti = 0;
      try {
        for (const file of payload.files) {
          const creato = await this._postUno({ ...payload, file });
          if (creato) ok += 1;
          else falliti += 1;
        }
      } finally {
        this.uploading = false;
      }
      return { ok, falliti };
    },

    /** POST di un singolo file (uso interno, non tocca lo stato uploading). */
    async _postUno(payload: {
      file: File;
      tipo: TipoDocumento;
      descrizione?: string;
      dataScadenza?: string | null;
      tenantId?: number;
    }): Promise<DocumentoFE | null> {
      try {
        const form = new FormData();
        form.append('file', payload.file);
        form.append('tipo', payload.tipo);
        if (payload.descrizione) form.append('descrizione', payload.descrizione);
        if (payload.dataScadenza) form.append('data_scadenza', payload.dataScadenza);
        if (payload.tenantId) form.append('tenant', String(payload.tenantId));
        const { data } = await api.post<DocumentoFE>('/api/v1/tenant-documents/', form);
        this.documenti.unshift(data);
        return data;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore caricamento documento');
        return null;
      }
    },

    async elimina(id: number): Promise<boolean> {
      this.errore = null;
      try {
        await api.delete(`/api/v1/tenant-documents/${id}/`);
        this.documenti = this.documenti.filter((d) => d.id !== id);
        return true;
      } catch (e: unknown) {
        this.errore = messaggioErrore(e, 'Errore eliminazione documento');
        return false;
      }
    },
  },
});
