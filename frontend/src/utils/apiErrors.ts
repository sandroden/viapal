import { isAxiosError } from 'axios';

/** Profondità massima di discesa nel payload d'errore DRF. */
const MAX_PROFONDITA = 4;

interface FogliaErrore {
  messaggio: string;
  /** Nomi dei campi attraversati (senza indici numerici né `non_field_errors`). */
  percorso: string[];
}

/**
 * Percorre il payload (dict/array annidati, come li produce un serializer DRF
 * anche con `many=True`) e ritorna la prima stringa foglia trovata, insieme al
 * percorso dei nomi campo attraversati. Gli indici degli array e la chiave
 * `non_field_errors` non entrano nel percorso.
 */
function primaFoglia(nodo: unknown, percorso: string[], profondita: number): FogliaErrore | null {
  if (typeof nodo === 'string') return { messaggio: nodo, percorso };
  if (profondita >= MAX_PROFONDITA || nodo === null || typeof nodo !== 'object') {
    return null;
  }
  if (Array.isArray(nodo)) {
    for (const voce of nodo) {
      const esito = primaFoglia(voce, percorso, profondita + 1);
      if (esito) return esito;
    }
    return null;
  }
  for (const [campo, valore] of Object.entries(nodo as Record<string, unknown>)) {
    const esito = primaFoglia(
      valore,
      campo === 'non_field_errors' ? percorso : [...percorso, campo],
      profondita + 1,
    );
    if (esito) return esito;
  }
  return null;
}

/**
 * Estrae un messaggio d'errore leggibile da una risposta axios/DRF.
 *
 * Ordine di priorità sul payload `e.response.data`:
 * 1. `detail` stringa → ritornata così com'è;
 * 2. `non_field_errors` → prima stringa dell'array;
 * 3. estrazione ricorsiva della prima stringa foglia (dict/array annidati,
 *    es. errori di serializer `many=True` come
 *    `{"rate_deposito": [{"importo": ["obbligatorio"]}]}`), prefissata con
 *    l'ultimo nome campo attraversato → `"importo: obbligatorio"`;
 * 4. payload stringa nuda: ritornata solo se corta e non HTML.
 *
 * Ritorna `fallback` per errori di rete/timeout (nessuna `response`), payload
 * HTML o comunque non riconosciuti.
 */
export function messaggioErrore(e: unknown, fallback: string): string {
  if (!isAxiosError(e) || !e.response) return fallback;
  const data: unknown = e.response.data;

  if (typeof data === 'string') {
    const testo = data.trim();
    if (!testo || testo.startsWith('<') || testo.length >= 200) return fallback;
    return testo;
  }

  if (data === null || typeof data !== 'object') return fallback;

  if (!Array.isArray(data)) {
    const dict = data as Record<string, unknown>;
    if (typeof dict.detail === 'string') return dict.detail;
    const nfe = dict.non_field_errors;
    if (Array.isArray(nfe) && typeof nfe[0] === 'string') return nfe[0];
  }

  const foglia = primaFoglia(data, [], 0);
  if (foglia) {
    const campo = foglia.percorso.at(-1);
    return campo ? `${campo}: ${foglia.messaggio}` : foglia.messaggio;
  }

  return fallback;
}
