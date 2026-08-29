/**
 * Utility immagini lato client.
 *
 * `resizeImageFile` ridimensiona una foto nel browser *prima* dell'upload:
 * le foto da smartphone sono 4-12 MB e 4000px di lato, mentre in galleria
 * non se ne usano mai più di ~1600px. Ridurre qui evita banda, spazio su
 * disco e il limite di dimensione del validatore backend.
 *
 * Origine: composable `useMediaUpload` del progetto "nicolas", qui ridotto
 * alla sola funzione standalone (niente crop manuale).
 */

const MAX_LATO = 1920;
const QUALITA = 0.85;

/** True se il browser sa produrre WebP da canvas (tutti i moderni). */
function supportaWebp(): boolean {
  return document.createElement('canvas').toDataURL('image/webp').startsWith('data:image/webp');
}

function caricaImmagine(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  return new Promise((resolve, reject) => {
    const el = new Image();
    el.onload = () => {
      URL.revokeObjectURL(url);
      resolve(el);
    };
    el.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('immagine non decodificabile'));
    };
    el.src = url;
  });
}

/**
 * Ridimensiona `file` entro `maxLato` px (lato lungo) e lo riconverte in
 * WebP (fallback JPEG). Le immagini già più piccole vengono comunque
 * ricodificate: il guadagno di peso resta significativo.
 *
 * Non solleva mai: se il browser non sa decodificare il file (es. HEIC di
 * iPhone, che passa il test `image/*` ma non ha decoder) ritorna il file
 * originale, così l'errore lo dà il validatore backend con un messaggio
 * sensato invece di far sparire l'upload.
 */
export async function resizeImageFile(
  file: File,
  maxLato = MAX_LATO,
  qualita = QUALITA,
): Promise<File> {
  try {
    const img = await caricaImmagine(file);
    const scala = Math.min(maxLato / img.naturalWidth, maxLato / img.naturalHeight, 1);
    const w = Math.round(img.naturalWidth * scala);
    const h = Math.round(img.naturalHeight * scala);

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    if (!ctx) return file;
    ctx.drawImage(img, 0, 0, w, h);

    const mime = supportaWebp() ? 'image/webp' : 'image/jpeg';
    const ext = mime === 'image/webp' ? 'webp' : 'jpg';
    const nome = file.name.replace(/\.[^.]+$/, '') + '.' + ext;

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, mime, qualita),
    );
    if (!blob) return file;
    // Se la ricodifica ha peggiorato le cose (immagini piccole già ottimizzate)
    // tengo l'originale.
    if (blob.size >= file.size && scala === 1) return file;
    return new File([blob], nome, { type: mime });
  } catch {
    return file;
  }
}

/**
 * Ritaglia al centro e riduce a un quadrato di `lato` px, restituendo un
 * data URI (WebP, fallback JPEG) invece di un File.
 *
 * Serve per le fotine dei lead, che non finiscono su disco ma dentro una
 * colonna: la campagna si chiude cancellando i lead in blocco, e un file su
 * storage sopravviverebbe a quella cancellazione. Il default di 256px è il
 * doppio dei 60 CSS a cui si mostra: su uno schermo denso (2x, e i 4k lo
 * sono) una sorgente più piccola si vede impastata. Restano pochi KB, meno
 * di quanto pesi la riga di testo del post.
 *
 * Ritorna null se il browser non sa decodificare l'immagine: chi chiama lo
 * dice all'utente, invece di far sparire l'operazione in silenzio.
 */
export async function imageToSquareDataUrl(
  file: File,
  lato = 256,
  qualita = 0.8,
): Promise<string | null> {
  try {
    const img = await caricaImmagine(file);
    const canvas = document.createElement('canvas');
    canvas.width = lato;
    canvas.height = lato;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    // Ritaglio quadrato centrale: le foto di profilo sono già dei ritratti,
    // e lo schiacciamento renderebbe le facce irriconoscibili.
    const min = Math.min(img.naturalWidth, img.naturalHeight);
    const sx = (img.naturalWidth - min) / 2;
    const sy = (img.naturalHeight - min) / 2;
    ctx.drawImage(img, sx, sy, min, min, 0, 0, lato, lato);

    const mime = supportaWebp() ? 'image/webp' : 'image/jpeg';
    return canvas.toDataURL(mime, qualita);
  } catch {
    return null;
  }
}

/** Salva un Blob già in memoria con il nome indicato. */
export function scaricaBlob(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objectUrl);
}

/**
 * Scarica un file dal suo URL forzando il nome. Passa da `fetch` + blob
 * perché l'attributo `download` di `<a>` viene ignorato per URL cross-origin
 * e comunque non permette di rinominare il file servito da `/media`.
 */
export async function scaricaUrl(url: string, filename: string): Promise<void> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`download fallito (${res.status})`);
  scaricaBlob(await res.blob(), filename);
}
