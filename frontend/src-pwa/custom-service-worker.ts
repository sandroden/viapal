/*
 * This file (which will be your service worker)
 * is picked up by the build system ONLY if
 * quasar.config file > pwa > workboxMode is set to "InjectManifest"
 */

declare const self: ServiceWorkerGlobalScope &
  typeof globalThis & { skipWaiting: () => void };

import { clientsClaim } from 'workbox-core';
import {
  precacheAndRoute,
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
} from 'workbox-precaching';
import { registerRoute, NavigationRoute } from 'workbox-routing';

// Propaga subito il SW nuovo ai client che hanno ancora quello vecchio in
// cache (altrimenti gli aggiornamenti non arrivano finché non chiudono
// tutte le tab).
void self.skipWaiting();
clientsClaim();

// Use with precache injection
precacheAndRoute(self.__WB_MANIFEST);

cleanupOutdatedCaches();

// Non-SSR fallbacks to index.html
// Production SSR fallbacks to offline.html (except for dev)
if (process.env.PROD) {
  registerRoute(
    new NavigationRoute(
      createHandlerBoundToURL(process.env.PWA_FALLBACK_HTML),
      {
        // Il dominio serve sia la SPA sia Django (admin/api/static/...),
        // instradati da Traefik per path. Senza questa denylist il
        // navigation fallback di Workbox dirotta /admin sull'index.html
        // della SPA (pagina "tutta beige"): vanno esclusi i path Django.
        denylist: [
          new RegExp(process.env.PWA_SERVICE_WORKER_REGEX),
          /workbox-(.)*\.js$/,
          /^\/admin/,
          /^\/api/,
          /^\/static/,
          /^\/media/,
          /^\/accounts/,
        ],
      },
    ),
  );
}

// ── Notifiche push ────────────────────────────────────────────────────────
// Il backend invia un payload JSON {title, body, url} (vedi
// notifications/push.py). Il SW viene svegliato dal push service di sistema
// solo all'arrivo del messaggio: mostra la notifica e termina.

interface PushPayload {
  title?: string;
  body?: string;
  url?: string;
}

// Il progetto compila con la lib DOM (non WebWorker): PushEvent,
// NotificationEvent e Clients non esistono nel programma TS. Dichiariamo
// il sottoinsieme che usiamo, senza inquinare i tipi globali.
interface ExtendableEventLike extends Event {
  waitUntil(promise: Promise<unknown>): void;
}
interface PushEventLike extends ExtendableEventLike {
  data: { json(): unknown; text(): string } | null;
}
interface NotificationEventLike extends ExtendableEventLike {
  notification: Notification & { data?: PushPayload };
}
interface WindowClientLike {
  navigate(url: string): Promise<unknown>;
  focus(): Promise<unknown>;
}
interface ServiceWorkerSelf {
  registration: ServiceWorkerRegistration;
  clients: {
    matchAll(options: {
      type: string;
      includeUncontrolled: boolean;
    }): Promise<WindowClientLike[]>;
    openWindow(url: string): Promise<unknown>;
  };
  addEventListener(type: 'push', listener: (event: PushEventLike) => void): void;
  addEventListener(
    type: 'notificationclick',
    listener: (event: NotificationEventLike) => void,
  ): void;
}

const sw = self as unknown as ServiceWorkerSelf;

sw.addEventListener('push', (event) => {
  let payload: PushPayload = {};
  try {
    payload = (event.data?.json() as PushPayload) ?? {};
  } catch {
    payload = { body: event.data?.text() ?? '' };
  }
  event.waitUntil(
    sw.registration.showNotification(payload.title ?? 'Viapal', {
      body: payload.body ?? '',
      icon: '/icons/icon-192x192.png',
      badge: '/icons/icon-128x128.png',
      data: { url: payload.url ?? '/' },
    }),
  );
});

// Al tocco sulla notifica: porta in primo piano una tab/PWA già aperta
// navigandola all'URL della notifica, oppure ne apre una nuova.
sw.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url ?? '/';
  event.waitUntil(
    sw.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then(async (clients) => {
        const client = clients[0];
        if (client) {
          await client.navigate(url);
          return client.focus();
        }
        return sw.clients.openWindow(url);
      }),
  );
});
