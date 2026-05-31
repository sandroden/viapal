import { ref, watchEffect, type Ref } from 'vue';
import QRCode from 'qrcode';

export interface EpcDati {
  beneficiario: string;
  iban: string;
  causale: string;
  importo: number;
}

/**
 * Compone la stringa EPC069-12 (GiroCode / EPC QR) per un bonifico SEPA.
 * L'app bancaria che la legge precompila IBAN, beneficiario, importo e causale.
 * Versione "002": il BIC è opzionale (riga vuota).
 */
export function buildEpcPayload(d: EpcDati): string {
  const importo = d.importo > 0 ? `EUR${d.importo.toFixed(2)}` : '';
  const beneficiario = d.beneficiario.slice(0, 70);
  const iban = d.iban.replace(/\s+/g, '').toUpperCase();
  const causale = d.causale.slice(0, 140);
  return [
    'BCD',
    '002',
    '1',
    'SCT',
    '', // BIC (opzionale in v002)
    beneficiario,
    iban,
    importo,
    '', // Purpose
    '', // Remittance strutturata
    causale, // Remittance non strutturata
    '', // Info beneficiario→ordinante
  ].join('\n');
}

/**
 * Genera reattivamente il data-URL PNG del QR EPC a partire dai dati e
 * dall'importo (es. il residuo, che può cambiare nel form).
 */
export function useEpcQr(dati: Ref<EpcDati | null>) {
  const dataUrl = ref<string>('');
  const errore = ref<string>('');

  watchEffect(() => {
    const d = dati.value;
    if (!d || d.importo <= 0) {
      dataUrl.value = '';
      return;
    }
    QRCode.toDataURL(buildEpcPayload(d), {
      errorCorrectionLevel: 'M',
      margin: 1,
      width: 240,
    })
      .then((url) => {
        dataUrl.value = url;
        errore.value = '';
      })
      .catch((e: unknown) => {
        errore.value = (e as Error)?.message ?? 'QR non generato';
        dataUrl.value = '';
      });
  });

  return { dataUrl, errore };
}
