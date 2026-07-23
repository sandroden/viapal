import { isAxiosError } from 'axios';

/**
 * Estrae un messaggio d'errore leggibile da una risposta axios/DRF: privilegia
 * `detail`, altrimenti la prima stringa trovata tra i valori del dizionario
 * campo→errori. Ritorna `fallback` se non riconosce la forma della risposta.
 */
export function messaggioErrore(e: unknown, fallback: string): string {
  if (isAxiosError(e)) {
    const data = e.response?.data as Record<string, unknown> | undefined;
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') return data.detail;
      for (const valore of Object.values(data)) {
        if (typeof valore === 'string') return valore;
        if (Array.isArray(valore) && typeof valore[0] === 'string') return valore[0];
      }
    }
  }
  return fallback;
}
