import { defineStore } from 'pinia';
import { api } from 'boot/axios';
import { fetchAllPaginated } from 'src/utils/paginate';
import { messaggioErrore } from 'src/utils/apiErrors';

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
  visibile_inquilini?: boolean;
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
  { label: 'Registrazione contratto subentro', value: 'ricevuta_registrazione' },
  { label: 'Atto di subentro nel contratto', value: 'atto_subentro_locazione' },
  { label: 'Comunicazione di cessione di fabbricato', value: 'cessione_fabbricato' },
  { label: 'Altro', value: 'altro' },
];

interface State {
  documenti: DocumentoFE[];
  loading: boolean;
  uploading: boolean;
  errore: string | null;
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
        visibileInquilini?: boolean;
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

      /** Come ``caricaMulti``, ma ogni file porta la propria descrizione:
       *  serve al fascicolo, dove fronte e retro sono due file dello stesso
       *  tipo distinti dall'etichetta. */
      async caricaPagine(payload: {
        pagine: { file: File; descrizione?: string }[];
        tipo: string;
        dataScadenza?: string | null;
        visibileInquilini?: boolean;
        targetId?: number;
      }): Promise<{ ok: number; falliti: number }> {
        this.uploading = true;
        this.errore = null;
        let ok = 0;
        let falliti = 0;
        const { pagine, ...comuni } = payload;
        try {
          for (const pagina of pagine) {
            const creato = await this._postUno({
              ...comuni,
              file: pagina.file,
              ...(pagina.descrizione ? { descrizione: pagina.descrizione } : {}),
            });
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
        visibileInquilini?: boolean;
        targetId?: number;
      }): Promise<DocumentoFE | null> {
        try {
          const form = new FormData();
          form.append('file', payload.file);
          form.append('tipo', payload.tipo);
          if (payload.descrizione) form.append('descrizione', payload.descrizione);
          if (payload.dataScadenza) form.append('data_scadenza', payload.dataScadenza);
          if (payload.visibileInquilini !== undefined)
            form.append('visibile_inquilini', payload.visibileInquilini ? 'true' : 'false');
          if (payload.targetId) form.append(targetField, String(payload.targetId));
          const { data } = await api.post<DocumentoFE>(endpoint, form);
          this.documenti.unshift(data);
          return data;
        } catch (e: unknown) {
          this.errore = messaggioErrore(e, 'Errore caricamento documento');
          return null;
        }
      },

      /** Cambia la visibilità agli inquilini (solo documenti proprietà).
       *  L'endpoint accetta solo form-data, quindi PATCH via FormData. */
      async impostaVisibilita(id: number, visibile: boolean): Promise<boolean> {
        this.errore = null;
        try {
          const form = new FormData();
          form.append('visibile_inquilini', visibile ? 'true' : 'false');
          const { data } = await api.patch<DocumentoFE>(`${endpoint}${id}/`, form);
          const idx = this.documenti.findIndex((d) => d.id === id);
          if (idx >= 0) this.documenti[idx] = data;
          return true;
        } catch (e: unknown) {
          this.errore = messaggioErrore(e, 'Errore aggiornamento visibilità');
          return false;
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

export const TIPI_DOCUMENTO_PROPRIETA: TipoDocumentoOption[] = [
  { label: 'Contratto di locazione', value: 'contratto' },
  { label: 'Side letter', value: 'side_letter' },
  { label: 'Registrazione contratto', value: 'registrazione_contratto' },
  { label: 'Regolamento condominiale', value: 'regolamento_condominiale' },
  { label: 'Altro', value: 'altro' },
];

export const useDocumentiStore = creaDocumentiStore(
  'documenti',
  '/api/v1/tenant-documents/',
  'tenant',
);

/** Documenti dell'immobile: il backend opera sempre sull'immobile attivo
 *  (header X-Property-Id), quindi fetch/upload non passano targetId. */
export const useDocumentiProprietaStore = creaDocumentiStore(
  'documentiProprieta',
  '/api/v1/property-documents/',
  'property',
);

/** Store istanziato: entrambe le varianti (inquilino/proprietà) condividono
 *  questa forma, il componente DocumentiPannello la riceve come prop. */
export type DocumentiStore = ReturnType<typeof useDocumentiStore>;
