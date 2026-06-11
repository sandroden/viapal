import { computed, ref } from 'vue';
import { api } from 'boot/axios';

/**
 * Notifiche push: stato e azioni di sottoscrizione del device corrente.
 *
 * Flusso: permesso Notification → `pushManager.subscribe` con la chiave
 * pubblica VAPID del backend → POST della subscription (endpoint + chiavi)
 * su /api/notifications/push-subscriptions/. Il backend fa upsert per
 * endpoint, quindi ri-abilitare è sempre sicuro.
 *
 * Su iOS le notifiche sono disponibili solo con la PWA installata
 * ("Aggiungi a schermata Home", iOS ≥ 16.4): nel browser Safari normale
 * `supportato` risulta false e il toggle non viene mostrato.
 */

interface PushSubscriptionApi {
  id: number;
  endpoint: string;
}

interface VapidInfo {
  abilitato: boolean;
  public_key: string;
}

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function etichettaDevice(): string {
  const ua = navigator.userAgent;
  const os = /android/i.test(ua)
    ? 'Android'
    : /iphone|ipad/i.test(ua)
      ? 'iOS'
      : /mac/i.test(ua)
        ? 'macOS'
        : /windows/i.test(ua)
          ? 'Windows'
          : 'Linux';
  const browser = /edg/i.test(ua)
    ? 'Edge'
    : /firefox/i.test(ua)
      ? 'Firefox'
      : /chrome|crios/i.test(ua)
        ? 'Chrome'
        : /safari/i.test(ua)
          ? 'Safari'
          : 'Browser';
  return `${browser} su ${os}`;
}

export function usePush() {
  const supportato =
    'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;

  /** Il backend ha le chiavi VAPID configurate. */
  const abilitatoServer = ref(false);
  /** Questo device è già sottoscritto. */
  const attivo = ref(false);
  /** Permesso negato a livello browser: il toggle va spiegato, non riprovato. */
  const negato = ref(false);
  const loading = ref(false);
  const errore = ref('');

  const disponibile = computed(() => supportato && abilitatoServer.value);

  let publicKey = '';

  async function subscriptionCorrente(): Promise<PushSubscription | null> {
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  }

  /** Carica stato server + stato locale del device. Da chiamare in onMounted. */
  async function init(): Promise<void> {
    if (!supportato) return;
    try {
      const { data } = await api.get<VapidInfo>(
        '/api/v1/push-subscriptions/vapid-public-key/',
      );
      abilitatoServer.value = data.abilitato;
      publicKey = data.public_key;
      if (!data.abilitato) return;
      negato.value = Notification.permission === 'denied';
      attivo.value = (await subscriptionCorrente()) !== null;
    } catch {
      abilitatoServer.value = false;
    }
  }

  async function abilita(): Promise<void> {
    errore.value = '';
    loading.value = true;
    try {
      const permesso = await Notification.requestPermission();
      negato.value = permesso === 'denied';
      if (permesso !== 'granted') {
        if (negato.value) {
          errore.value =
            'Le notifiche sono bloccate per questo sito: sbloccale dalle impostazioni del browser.';
        }
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub =
        (await reg.pushManager.getSubscription()) ??
        (await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey).buffer as ArrayBuffer,
        }));
      const json = sub.toJSON();
      await api.post('/api/v1/push-subscriptions/', {
        endpoint: sub.endpoint,
        p256dh: json.keys?.p256dh ?? '',
        auth: json.keys?.auth ?? '',
        device_label: etichettaDevice(),
      });
      attivo.value = true;
    } catch (e) {
      errore.value = `Attivazione non riuscita: ${e instanceof Error ? e.message : String(e)}`;
    } finally {
      loading.value = false;
    }
  }

  async function disabilita(): Promise<void> {
    errore.value = '';
    loading.value = true;
    try {
      const sub = await subscriptionCorrente();
      if (sub) {
        // Rimuove la registrazione lato server (match per endpoint)...
        const { data } = await api.get<PushSubscriptionApi[]>(
          '/api/v1/push-subscriptions/',
        );
        const mia = data.find((s) => s.endpoint === sub.endpoint);
        if (mia) {
          await api.delete(`/api/v1/push-subscriptions/${mia.id}/`);
        }
        // ...e quella lato browser.
        await sub.unsubscribe();
      }
      attivo.value = false;
    } catch (e) {
      errore.value = `Disattivazione non riuscita: ${e instanceof Error ? e.message : String(e)}`;
    } finally {
      loading.value = false;
    }
  }

  /** Invia una notifica di prova a tutti i device dell'utente. */
  async function provaNotifica(): Promise<{ inviate: number }> {
    const { data } = await api.post<{ inviate: number }>(
      '/api/v1/push-subscriptions/test/',
    );
    return data;
  }

  return {
    supportato,
    disponibile,
    attivo,
    negato,
    loading,
    errore,
    init,
    abilita,
    disabilita,
    provaNotifica,
  };
}
