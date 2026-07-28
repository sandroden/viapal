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
