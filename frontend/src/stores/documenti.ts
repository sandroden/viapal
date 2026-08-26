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
  /** Documenti immobile: contratto a cui la carta appartiene (null = carta
   *  della casa). */
  contract?: number | null;
  contract_nome?: string;
  /** Come si chiama il documento quando lo si mostra da solo. */
  titolo?: string;
  /** Documenti immobile: valorizzato = è la copia oscurata di quel
   *  documento, e sta fuori da tutti gli elenchi ufficiali. */
  copia_di?: number | null;
  copia_di_titolo?: string;
  /** Può stare in un link di lettura mandato a chi non ha un account. */
  esponibile?: boolean;
  /** Nato per essere letto da fuori (fac-simile): non nomina nessuno,
   *  quindi non ha bisogno di una copia oscurata. La regola sta sul
   *  backend (``TIPI_ESPONIBILI_PER_NATURA``), qui arriva già decisa. */
  esponibile_per_natura?: boolean;
  /** In quanti link di lettura è in uso (badge, e spiegazione del 409). */
  link_in_uso?: number;
}

/** Un dato che manca al documento, con il posto in cui si compila.
 *  Stessa forma restituita dall'anteprima dei documenti generati. */
export interface DatoMancante {
  campo: string;
  etichetta: string;
  fonte: string;
  dove: string;
  link: string;
  esterno: boolean;
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

      /** Genera il fac-simile di un documento (solo documenti proprietà).
       *
       *  Non è la copia oscurata di un atto firmato — quella nominerebbe
       *  qualcuno — ma lo stesso modello con OMISSIS al posto delle parti
       *  che cambiano da un caso all'altro. In caso di dati incompleti il
       *  backend risponde 400 con l'elenco di cosa manca e dove si compila:
       *  torna quello, non un messaggio. */
      async generaFacsimile(
        codice: string,
      ): Promise<{ ok: boolean; documento?: DocumentoFE; mancanti?: DatoMancante[] }> {
        this.uploading = true;
        this.errore = null;
        try {
          const { data } = await api.post<DocumentoFE>(`${endpoint}facsimile/`, {
            codice,
          });
          this.documenti.unshift(data);
          return { ok: true, documento: data };
        } catch (e: unknown) {
          const corpo = (e as { response?: { data?: { mancanti?: DatoMancante[] } } })
            .response?.data;
          if (corpo?.mancanti?.length) return { ok: false, mancanti: corpo.mancanti };
          this.errore = messaggioErrore(e, 'Generazione del fac-simile non riuscita');
          return { ok: false };
        } finally {
          this.uploading = false;
        }
      },

      /** Carica la copia oscurata di un documento esistente (solo documenti
       *  proprietà: l'azione esiste solo su quell'endpoint).
       *
       *  Il file arriva già oscurato: l'applicazione non entra nel merito
       *  (un rettangolo nero non cancella il testo sotto). Il legame con
       *  l'originale e la spunta «esponibile» li mette il server. */
      async caricaCopiaLettura(payload: {
        originaleId: number;
        file: File;
        descrizione?: string;
      }): Promise<boolean> {
        this.uploading = true;
        this.errore = null;
        try {
          const fd = new FormData();
          fd.append('file', payload.file);
          if (payload.descrizione) fd.append('descrizione', payload.descrizione);
          const { data } = await api.post<DocumentoFE>(
            `${endpoint}${payload.originaleId}/copia-lettura/`,
            fd,
          );
          this.documenti.unshift(data);
          return true;
        } catch (e: unknown) {
          this.errore = messaggioErrore(e, 'Caricamento della copia non riuscito');
          return false;
        } finally {
          this.uploading = false;
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

      /** Ogni file porta il proprio tipo: nel foglio di caricamento della
       *  scheda Immobile si trascinano insieme documenti diversi (contratto
       *  + side letter), e il tipo è proposto dal nome del file. */
      async caricaTipizzati(payload: {
        voci: { file: File; tipo: string; descrizione?: string }[];
        visibileInquilini?: boolean;
        contract?: number | null;
        targetId?: number;
      }): Promise<{ ok: number; falliti: number }> {
        this.uploading = true;
        this.errore = null;
        let ok = 0;
        let falliti = 0;
        const { voci, ...comuni } = payload;
        try {
          for (const voce of voci) {
            const creato = await this._postUno({ ...comuni, ...voce });
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
        contract?: number | null;
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
          if (payload.contract) form.append('contract', String(payload.contract));
          if (payload.targetId) form.append(targetField, String(payload.targetId));
          const { data } = await api.post<DocumentoFE>(endpoint, form);
          this.documenti.unshift(data);
          return data;
        } catch (e: unknown) {
          this.errore = messaggioErrore(e, 'Errore caricamento documento');
          return null;
        }
      },

      /** Modifica i metadati di un documento già caricato, senza rimandare
       *  il file. In JSON e non in form-data: ``contract: null`` deve poter
       *  dire «staccalo dal contratto», e un campo vuoto in multipart non
       *  sa distinguere «nessuno» da «non toccare». */
      async aggiorna(
        id: number,
        patch: {
          tipo?: string;
          descrizione?: string;
          contract?: number | null;
          visibile_inquilini?: boolean;
          esponibile?: boolean;
          data_scadenza?: string | null;
        },
      ): Promise<boolean> {
        this.errore = null;
        try {
          const { data } = await api.patch<DocumentoFE>(`${endpoint}${id}/`, patch);
          const idx = this.documenti.findIndex((d) => d.id === id);
          if (idx >= 0) this.documenti[idx] = data;
          return true;
        } catch (e: unknown) {
          this.errore = messaggioErrore(e, 'Errore aggiornamento documento');
          return false;
        }
      },

      /** Spunta «esponibile» (solo documenti proprietà): togliendola i link
       *  già mandati smettono di servire quel file — revoca a grana fine. */
      async impostaEsponibile(id: number, esponibile: boolean): Promise<boolean> {
        return this.aggiorna(id, { esponibile });
      },

      /** Cambia la visibilità agli inquilini (solo documenti proprietà). */
      async impostaVisibilita(id: number, visibile: boolean): Promise<boolean> {
        const ok = await this.aggiorna(id, { visibile_inquilini: visibile });
        if (!ok && this.errore === 'Errore aggiornamento documento') {
          this.errore = 'Errore aggiornamento visibilità';
        }
        return ok;
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

/** L'unico documento che ha senso mandare a chi deve ancora decidere: la
 *  comunicazione di cessione di fabbricato è un adempimento verso
 *  l'autorità, non una carta che un candidato legge prima di firmare. */
export const CODICE_FACSIMILE = 'atto_subentro_locazione';

export const TIPI_DOCUMENTO_PROPRIETA: TipoDocumentoOption[] = [
  { label: 'Contratto di locazione', value: 'contratto' },
  { label: 'Side letter', value: 'side_letter' },
  { label: 'Registrazione contratto', value: 'registrazione_contratto' },
  { label: 'Regolamento condominiale', value: 'regolamento_condominiale' },
  { label: 'Regole di convivenza', value: 'regole_convivenza' },
  { label: 'Fac-simile', value: 'fac_simile' },
  { label: 'Altro', value: 'altro' },
];

/** Tipi che *sono* la carta di un contratto: senza contratto il backend li
 *  rifiuta (``PropertyDocument.TIPI_CONTRATTUALI``). Duplicata qui come la
 *  lista dei tipi: il FE non ha un endpoint da cui derivarla. */
export const TIPI_CONTRATTUALI = ['contratto', 'side_letter', 'registrazione_contratto'];

export function richiedeContratto(tipo: string): boolean {
  return TIPI_CONTRATTUALI.includes(tipo);
}

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
