/**
 * Anagrafica estesa dell'inquilino: i dati che chiedono i documenti generati
 * (atto di subentro, cessione di fabbricato). La compila il proprietario
 * dalla scheda inquilino o l'inquilino stesso dal proprio profilo: i campi
 * stanno in `AnagraficaPersonaCampi.vue`, questo modulo ne porta la forma.
 */

export const TIPI_DOCUMENTO_IDENTITA = [
  { label: "Carta d'identità", value: 'carta_identita' },
  { label: 'Passaporto', value: 'passaporto' },
  { label: 'Permesso di soggiorno', value: 'permesso_soggiorno' },
];

export interface AnagraficaPersona {
  cognome: string;
  nome: string;
  data_nascita: string | null;
  comune_nascita: string;
  provincia_nascita: string;
  cittadinanza: string;
  codice_fiscale: string;
  residenza_via: string;
  residenza_comune: string;
  residenza_provincia: string;
  residenza_cap: string;
  documento_tipo: string | null;
  documento_numero: string;
  documento_autorita: string;
  documento_data_rilascio: string | null;
}

export function anagraficaVuota(): AnagraficaPersona {
  return {
    cognome: '',
    nome: '',
    data_nascita: null,
    comune_nascita: '',
    provincia_nascita: '',
    cittadinanza: '',
    codice_fiscale: '',
    residenza_via: '',
    residenza_comune: '',
    residenza_provincia: '',
    residenza_cap: '',
    documento_tipo: null,
    documento_numero: '',
    documento_autorita: '',
    documento_data_rilascio: null,
  };
}

/** Copia nei campi di `dest` i valori presenti in `dati` (null/assenti restano vuoti). */
export function riempi<T extends object>(dest: T, dati: Partial<Record<keyof T, unknown>>): T {
  for (const chiave of Object.keys(dest) as Array<keyof T>) {
    const valore = dati[chiave];
    if (valore !== undefined && valore !== null) {
      (dest[chiave] as string) = String(valore);
    }
  }
  return dest;
}

/** Payload per il backend: date vuote → null, tipo documento vuoto → ''. */
export function payloadAnagrafica(a: AnagraficaPersona) {
  return {
    ...a,
    codice_fiscale: a.codice_fiscale.trim().toUpperCase(),
    residenza_provincia: a.residenza_provincia.trim().toUpperCase(),
    data_nascita: a.data_nascita || null,
    documento_data_rilascio: a.documento_data_rilascio || null,
    documento_tipo: a.documento_tipo ?? '',
  };
}
