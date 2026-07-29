import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { fetchAllPaginated } from 'src/utils/paginate';

// --- Tipi -----------------------------------------------------------------

export interface DocumentoFE {
  id: number;
  tipo: string;
  tipo_display: string;
  file: string;
  descrizione: string;
  data_scadenza: string | null;
  scaduto: boolean;
  created_at: string;
  // Presenti a seconda dell'endpoint (documenti inquilino vs proprietà).
  tenant?: number;
  tenant_nominativo?: string;
  property?: number;
}

export interface TipoDocumentoOption {
  label: string;
  value: string;
}

export const TIPI_DOCUMENTO_INQUILINO: TipoDocumentoOption[] = [
  { label: "Carta d'identità", value: 'carta_identita' },
  { label: 'Codice fiscale / Tessera sanitaria', value: 'codice_fiscale' },
  { label: 'Passaporto', value: 'passaporto' },
  { label: 'Permesso di soggiorno', value: 'permesso_soggiorno' },
  { label: 'Contratto di lavoro', value: 'contratto_lavoro' },
  { label: 'Ricevuta del subentro', value: 'ricevuta_subentro' },
  { label: 'Atto di subentro', value: 'atto_subentro' },
  { label: 'Altro', value: 'altro' },
];

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

/** Factory di store documenti su un endpoint DRF multipart.
 *
 *  ``targetField`` è il nome del campo FK inviato quando si opera su un
 *  target esplicito (es. il proprietario che carica per un inquilino o per
 *  l'immobile); l'inquilino non lo passa mai (il backend forza il proprio).
 */
function creaDocumentiStore(
  storeId: string,
  endpoint: string,
  targetField: 'tenant' | 'property',
) {
  return defineStore(storeId, {
    state: (): State => ({
      documenti: [],
      loading: false,
      uploading: false,
      errore: null,
    }),
    actions: {
      /** Carica i documenti; con ``targetId`` filtra per target (uso lato
       *  proprietario), senza l'API restituisce i propri (inquilino). */
      async fetch(targetId?: number): Promise<void> {
        this.loading = true;
        this.errore = null;
        try {
          const url = targetId ? `${endpoint}?${targetField}=${targetId}` : endpoint;
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
        tipo: string;
        descrizione?: string;
        dataScadenza?: string | null;
        targetId?: number;
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
        tipo: string;
        descrizione?: string;
        dataScadenza?: string | null;
        targetId?: number;
      }): Promise<DocumentoFE | null> {
        try {
          const form = new FormData();
          form.append('file', payload.file);
          form.append('tipo', payload.tipo);
          if (payload.descrizione) form.append('descrizione', payload.descrizione);
          if (payload.dataScadenza) form.append('data_scadenza', payload.dataScadenza);
          if (payload.targetId) form.append(targetField, String(payload.targetId));
          const { data } = await api.post<DocumentoFE>(endpoint, form);
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
          await api.delete(`${endpoint}${id}/`);
          this.documenti = this.documenti.filter((d) => d.id !== id);
          return true;
        } catch (e: unknown) {
          this.errore = messaggioErrore(e, 'Errore eliminazione documento');
          return false;
        }
      },
    },
  });
}

export const useDocumentiStore = creaDocumentiStore(
  'documenti',
  '/api/v1/tenant-documents/',
  'tenant',
);

/** Store istanziato: entrambe le varianti (inquilino/proprietà) condividono
 *  questa forma, il componente DocumentiPannello la riceve come prop. */
export type DocumentiStore = ReturnType<typeof useDocumentiStore>;
