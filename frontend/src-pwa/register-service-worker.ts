import { register } from 'register-service-worker';

// ── Auto-reload all'aggiornamento del service worker ────────────────────────
// Il SW custom usa skipWaiting()+clientsClaim(): a ogni deploy il nuovo SW
// prende SUBITO il controllo delle tab già aperte e cleanupOutdatedCaches()
// rimuove la precache della versione precedente. La pagina, però, sta ancora
// eseguendo il bundle VECCHIO: i suoi chunk lazy (entry + ~decine di route
// chunk con hash diverso a ogni build) non esistono più né in cache né sul
// server (404) → l'import dinamico della prossima rotta fallisce e l'app si
// pianta ("resta in attesa" / pagina che non risponde).
//
// La cura standard: appena un nuovo SW diventa controller, ricarichiamo UNA
// volta per ripartire con asset coerenti. Il gate su `controller` esistente
// evita il reload alla primissima installazione (nessun controller iniziale →
// non è un aggiornamento), mentre il flag impedisce reload multipli.
if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
  let reloading = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (reloading) return;
    reloading = true;
    window.location.reload();
  });
}

// The ready(), registered(), cached(), updatefound() and updated()
// events passes a ServiceWorkerRegistration instance in their arguments.
// ServiceWorkerRegistration: https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration

register(process.env.SERVICE_WORKER_FILE, {
  // The registrationOptions object will be passed as the second argument
  // to ServiceWorkerContainer.register()
  // https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerContainer/register#Parameter

  // registrationOptions: { scope: './' },

  ready (/* registration */) {
    // console.log('Service worker is active.')
  },

  registered (/* registration */) {
    // console.log('Service worker has been registered.')
  },

  cached (/* registration */) {
    // console.log('Content has been cached for offline use.')
  },

  updatefound (/* registration */) {
    // console.log('New content is downloading.')
  },

  updated (/* registration */) {
    // console.log('New content is available; please refresh.')
  },

  offline () {
    // console.log('No internet connection found. App is running in offline mode.')
  },

  error (/* err */) {
    // console.error('Error during service worker registration:', err)
  },
});
