// Composable per formattare date secondo locale italiano.
const dateFormatter = new Intl.DateTimeFormat('it-IT', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

const longDateFormatter = new Intl.DateTimeFormat('it-IT', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
});

const monthFormatter = new Intl.DateTimeFormat('it-IT', {
  month: 'long',
  year: 'numeric',
});

function toDate(input: Date | string | null | undefined): Date | null {
  if (!input) return null;
  if (input instanceof Date) return input;
  const d = new Date(input);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function useFormatoData() {
  function formattaData(valore: Date | string | null | undefined): string {
    const d = toDate(valore);
    return d ? dateFormatter.format(d) : '—';
  }

  function formattaDataLunga(valore: Date | string | null | undefined): string {
    const d = toDate(valore);
    return d ? longDateFormatter.format(d) : '—';
  }

  function formattaMese(valore: Date | string | null | undefined): string {
    const d = toDate(valore);
    return d ? monthFormatter.format(d) : '—';
  }

  return { formattaData, formattaDataLunga, formattaMese };
}
