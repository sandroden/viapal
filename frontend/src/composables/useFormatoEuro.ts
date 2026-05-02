// Composable per formattare importi in Euro secondo locale italiano.
const formatter = new Intl.NumberFormat('it-IT', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function useFormatoEuro() {
  function formattaEuro(valore: number | string | null | undefined): string {
    if (valore === null || valore === undefined || valore === '') return '—';
    const n = typeof valore === 'string' ? Number(valore) : valore;
    if (Number.isNaN(n)) return '—';
    return formatter.format(n);
  }

  return { formattaEuro };
}
