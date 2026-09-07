/** Quanto tempo fa, come lo direbbe una persona: «12 min fa», «3 h fa», e
 *  oltre il giorno la data corta. Serve dove si scorre una lista e conta
 *  l'ordine più della precisione. */
export function quando(iso: string): string {
  const minuti = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minuti < 60) return `${Math.max(minuti, 1)} min fa`;
  if (minuti < 60 * 24) return `${Math.round(minuti / 60)} h fa`;
  return new Date(iso).toLocaleDateString('it-IT', { day: 'numeric', month: 'short' });
}
