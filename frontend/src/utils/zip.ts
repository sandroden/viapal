/**
 * Costruzione di un archivio ZIP nel browser, senza dipendenze.
 *
 * Metodo **store** (nessuna compressione): il contenuto sono foto JPEG/WebP,
 * già compresse, su cui deflate guadagnerebbe pochi punti percentuali a
 * fronte di una libreria in più nel bundle. Lo ZIP serve qui solo a
 * impacchettare: un file unico invece di N download.
 *
 * Limiti accettati: niente ZIP64 (archivi < 4 GB) e nomi file ASCII — quelli
 * generati da `ScaricaFotoDialog` sono già slug `[a-z0-9-]`.
 */

export interface FileZip {
  nome: string;
  dati: Uint8Array<ArrayBuffer>;
}

const TABELLA_CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(dati: Uint8Array<ArrayBuffer>): number {
  let c = 0xffffffff;
  for (let i = 0; i < dati.length; i++) c = TABELLA_CRC[(c ^ dati[i]!) & 0xff]! ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

/** Data/ora in formato MS-DOS (campo obbligatorio dell'header ZIP). */
function dataDos(d: Date): { tempo: number; data: number } {
  return {
    tempo: (d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1),
    data: ((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate(),
  };
}

/**
 * Impacchetta i file in un Blob `application/zip`.
 *
 * Struttura: per ogni file un local header + i dati, poi la central
 * directory con una voce per file e infine l'End Of Central Directory.
 */
export function creaZip(files: FileZip[], quando = new Date()): Blob {
  const { tempo, data } = dataDos(quando);
  const codificatore = new TextEncoder();
  const pezzi: Uint8Array<ArrayBuffer>[] = [];
  const centrale: Uint8Array<ArrayBuffer>[] = [];
  let offset = 0;

  for (const f of files) {
    const nome = codificatore.encode(f.nome);
    const crc = crc32(f.dati);
    const dim = f.dati.length;

    const locale = new Uint8Array(30 + nome.length);
    const vl = new DataView(locale.buffer);
    vl.setUint32(0, 0x04034b50, true); // firma local file header
    vl.setUint16(4, 20, true); // versione minima
    vl.setUint16(6, 0, true); // flag
    vl.setUint16(8, 0, true); // metodo: 0 = store
    vl.setUint16(10, tempo, true);
    vl.setUint16(12, data, true);
    vl.setUint32(14, crc, true);
    vl.setUint32(18, dim, true); // dimensione compressa
    vl.setUint32(22, dim, true); // dimensione originale
    vl.setUint16(26, nome.length, true);
    vl.setUint16(28, 0, true); // extra field
    locale.set(nome, 30);

    pezzi.push(locale, f.dati);

    const voce = new Uint8Array(46 + nome.length);
    const vc = new DataView(voce.buffer);
    vc.setUint32(0, 0x02014b50, true); // firma central directory
    vc.setUint16(4, 20, true); // versione di creazione
    vc.setUint16(6, 20, true); // versione minima
    vc.setUint16(8, 0, true);
    vc.setUint16(10, 0, true);
    vc.setUint16(12, tempo, true);
    vc.setUint16(14, data, true);
    vc.setUint32(16, crc, true);
    vc.setUint32(20, dim, true);
    vc.setUint32(24, dim, true);
    vc.setUint16(28, nome.length, true);
    vc.setUint16(30, 0, true); // extra
    vc.setUint16(32, 0, true); // commento
    vc.setUint16(34, 0, true); // disco
    vc.setUint16(36, 0, true); // attributi interni
    vc.setUint32(38, 0, true); // attributi esterni
    vc.setUint32(42, offset, true); // offset del local header
    voce.set(nome, 46);
    centrale.push(voce);

    offset += locale.length + dim;
  }

  const dimCentrale = centrale.reduce((n, v) => n + v.length, 0);
  const fine = new Uint8Array(22);
  const vf = new DataView(fine.buffer);
  vf.setUint32(0, 0x06054b50, true); // firma EOCD
  vf.setUint16(4, 0, true); // numero disco
  vf.setUint16(6, 0, true); // disco della central directory
  vf.setUint16(8, files.length, true); // voci su questo disco
  vf.setUint16(10, files.length, true); // voci totali
  vf.setUint32(12, dimCentrale, true);
  vf.setUint32(16, offset, true); // offset della central directory
  vf.setUint16(20, 0, true); // commento archivio

  return new Blob([...pezzi, ...centrale, fine], { type: 'application/zip' });
}
