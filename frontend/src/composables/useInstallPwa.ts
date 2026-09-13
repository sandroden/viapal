import { computed, readonly, ref } from 'vue';

/**
 * Installazione della PWA: stato e azioni della pagina /installa.
 *
 * Il punto delicato è `beforeinstallprompt`: il browser lo spara **all'avvio**
 * dell'app, molto prima che la rotta lazy `/installa` sia montata. Se lo si
 * ascoltasse in `onMounted` della pagina, a freddo l'evento sarebbe già
 * passato e il bottone "Installa" non si abiliterebbe mai. Per questo gli
 * ascoltatori si registrano nel boot (`boot/pwa-install.ts`) e l'evento vive
 * in stato di modulo, che la pagina si limita a leggere.
 *
 * Su iOS non esiste alcuna API di installazione: si può solo istruire
 * l'utente (Condividi → Aggiungi a Home). Ed è lì che serve davvero, perché
 * iOS consente le notifiche push **solo** alla PWA installata (iOS ≥ 16.4).
 */

/** L'evento non standard di Chromium: non è nei tipi DOM. */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export type Piattaforma = 'ios' | 'android' | 'desktop';
/** Motore del browser, non la marca: è il motore a decidere se e come si
 *  installa. `chromium` copre Chrome, Edge, Brave, Opera, Samsung Internet. */
export type MotoreBrowser = 'chromium' | 'firefox' | 'safari' | 'altro';

const promptEvent = ref<BeforeInstallPromptEvent | null>(null);
/** Installazione conclusa mentre la pagina era aperta (evento `appinstalled`). */
const installataOra = ref(false);
/** L'app sta girando dall'icona, non dentro il browser. */
const inStandalone = ref(rilevaStandalone());

function rilevaStandalone(): boolean {
  if (typeof window === 'undefined') return false;
  // `navigator.standalone` è il modo iOS, `display-mode` quello standard.
  const iosStandalone = (window.navigator as Navigator & { standalone?: boolean }).standalone;
  return window.matchMedia('(display-mode: standalone)').matches || iosStandalone === true;
}

/** Da chiamare una sola volta, all'avvio dell'app (boot). */
export function registraAscoltatoriInstall(): void {
  if (typeof window === 'undefined') return;

  window.addEventListener('beforeinstallprompt', (e) => {
    // Senza preventDefault Chrome mostra la sua mini-infobar e l'evento non
    // resta disponibile per il nostro bottone.
    e.preventDefault();
    promptEvent.value = e as BeforeInstallPromptEvent;
  });

  window.addEventListener('appinstalled', () => {
    installataOra.value = true;
    promptEvent.value = null;
  });

  // L'installazione da Chrome non ricarica la pagina: senza questo la
  // pagina resterebbe a dire "da installare" mentre l'icona c'è già.
  window.matchMedia('(display-mode: standalone)').addEventListener('change', (e) => {
    inStandalone.value = e.matches;
  });
}

function rilevaPiattaforma(): Piattaforma {
  if (typeof navigator === 'undefined') return 'desktop';
  const ua = navigator.userAgent;
  // iPadOS 13+ si dichiara Macintosh: lo tradisce il touch.
  const iPadOS = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;
  if (/iPhone|iPad|iPod/i.test(ua) || iPadOS) return 'ios';
  if (/Android/i.test(ua)) return 'android';
  return 'desktop';
}

function rilevaMotore(piattaforma: Piattaforma): MotoreBrowser {
  if (typeof navigator === 'undefined') return 'altro';
  const ua = navigator.userAgent;
  // Su iOS sono tutti WebKit per obbligo di piattaforma: Chrome e Firefox
  // per iOS si installano con la stessa condivisione di Safari.
  if (piattaforma === 'ios') return 'safari';
  if (/FxiOS|Firefox\//i.test(ua)) return 'firefox';
  // Edge e Opera dichiarano anche "Chrome": il test su Chrome li copre tutti,
  // e per l'installazione si comportano allo stesso modo.
  if (/Chrome\/|Chromium\/|CriOS/i.test(ua)) return 'chromium';
  if (/Safari\//i.test(ua)) return 'safari';
  return 'altro';
}

/**
 * Browser incorporato in un'altra app (Facebook, Instagram…): il link
 * arriverà proprio di lì, e da lì non si installa nulla. Va detto, o
 * l'utente cerca a vuoto una voce di menu che non esiste.
 *
 * Solo marcatori espliciti nello user agent. Su iOS si potrebbe dedurlo
 * dall'assenza di `navigator.standalone` (Safari lo espone, le WKWebView
 * no), ma quella prova pesca dentro anche Chrome e Firefox per iOS, dove
 * l'installazione funziona: accusare il browser sbagliato confonde più
 * del silenzio. Per il resto basta la nota «apri in Safari» sotto le
 * istruzioni, che è un suggerimento e non una diagnosi.
 */
function rilevaInApp(piattaforma: Piattaforma): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent;
  if (/FBAN|FBAV|FB_IAB|Instagram|Line\/|Twitter|MicroMessenger/i.test(ua)) return true;
  // Android: le WebView si dichiarano tali con "; wv" — è il caso di WhatsApp.
  return piattaforma === 'android' && /; wv\)/.test(ua);
}

export function useInstallPwa() {
  const piattaforma = rilevaPiattaforma();
  const motore = rilevaMotore(piattaforma);
  const inApp = rilevaInApp(piattaforma);

  /** L'app è già installata (o lo è appena stata). */
  const installata = computed(() => inStandalone.value || installataOra.value);
  /** Chrome/Edge ci ha dato l'evento: possiamo installare con un bottone. */
  const installabileConBottone = computed(() => promptEvent.value !== null);

  /**
   * Firefox **su computer** non installa le app web: non c'è API, non c'è
   * voce di menu, servirebbe un'estensione. Dirgli "cerca l'icona Installa
   * nella barra degli indirizzi" è mandarlo a cercare una cosa che non
   * esiste. Su Android invece Firefox installa senza problemi.
   *
   * L'evento `beforeinstallprompt` batte lo user agent: se il browser ci ha
   * offerto l'installazione, sa installare — e l'euristica, che è pur
   * sempre una lettura di stringhe, non deve poter nascondere un bottone
   * che funziona il giorno in cui Firefox lo implementa.
   *
   * Nota: non installabile ≠ senza notifiche. Firefox su computer le push
   * le riceve lo stesso; è solo iOS a pretendere l'app installata.
   */
  const installabile = computed(
    () => installabileConBottone.value || !(piattaforma === 'desktop' && motore === 'firefox'),
  );

  /**
   * Su iOS le notifiche push funzionano **solo** dentro la PWA installata:
   * finché si guarda la pagina in Safari il toggle non può funzionare, e
   * prometterlo sarebbe peggio che spiegare il perché.
   */
  const pushRichiedeInstallazione = computed(() => piattaforma === 'ios' && !installata.value);

  async function installa(): Promise<'accepted' | 'dismissed' | 'non-disponibile'> {
    const evento = promptEvent.value;
    if (!evento) return 'non-disponibile';
    // `prompt()` si può chiamare una volta sola per evento: consumiamolo
    // subito, così il bottone non resta cliccabile a vuoto.
    promptEvent.value = null;
    await evento.prompt();
    const { outcome } = await evento.userChoice;
    return outcome;
  }

  return {
    piattaforma,
    motore,
    installabile,
    inApp,
    installata,
    installabileConBottone,
    pushRichiedeInstallazione,
    inStandalone: readonly(inStandalone),
    installa,
  };
}
