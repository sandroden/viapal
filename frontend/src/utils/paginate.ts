import { api } from 'boot/axios';

/**
 * Normalizza un dizionario di filtri in query-string per il backend DRF:
 * scarta null/undefined/stringhe vuote e serializza numeri e booleani.
 */
export function paramsClean(
  filtri: Record<string, unknown>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(filtri)) {
    if (v === null || v === undefined || v === '') continue;
    if (typeof v === 'number') out[k] = v.toString();
    else if (typeof v === 'boolean') out[k] = v ? 'true' : 'false';
    else if (typeof v === 'string') out[k] = v;
  }
  return out;
}

/**
 * Scarica TUTTE le pagine di un endpoint DRF paginato (LimitOffset),
 * accumulando i `results` finché non si raggiunge `count`.
 *
 * Serve per le liste che possono superare il `max_limit` del backend (200):
 * fermarsi alla prima pagina le troncherebbe in silenzio, nascondendo voci
 * reali (es. un'utenza 2024 da abbinare con periodo 2023-2026). Se l'endpoint
 * non è paginato (risposta array) la ritorna così com'è.
 */
export async function fetchAllPaginated<T>(
  url: string,
  filtri: Record<string, unknown> = {},
): Promise<T[]> {
  const pageSize = Number(filtri.limit) || 200;
  const acc: T[] = [];
  let offset = 0;
  // Guardia anti-loop: il backend cap a 200/pagina, quindi bastano poche
  // pagine; il tetto duro evita cicli infiniti se `count` fosse incoerente.
  for (let guard = 0; guard < 1000; guard++) {
    const { data } = await api.get<T[] | { count?: number; results?: T[] }>(url, {
      params: paramsClean({ ...filtri, limit: pageSize, offset }),
    });
    if (Array.isArray(data)) return data; // endpoint non paginato
    const results = data.results ?? [];
    acc.push(...results);
    const count = typeof data.count === 'number' ? data.count : acc.length;
    offset += pageSize;
    if (results.length === 0 || acc.length >= count) break;
  }
  return acc;
}
