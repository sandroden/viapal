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

export interface DispositivoPush {
  id: number;
  endpoint: string;
  device_label: string;
  ultima_attivita: string | null;
  created_at: string;
  /** Il browser da cui si sta guardando, riconosciuto per endpoint. */
  corrente: boolean;
}

interface PushSubscriptionApi {
  id: number;
  endpoint: string;
  device_label: string;
  ultima_attivita: string | null;
  created_at: string;
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
  // Fuori da HTTPS/localhost il browser non espone affatto queste API: la
  // causa più comune è l'indirizzo (IP di LAN, hostname della macchina), non
  // il browser. Tenerle distinte permette di dire *cosa* manca.
  const contestoSicuro = window.isSecureContext;
  const supportato =
    'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  const origine = window.location.origin;

  /** Il backend ha le chiavi VAPID configurate. */
  const abilitatoServer = ref(false);
  /** Questo device è già sottoscritto. */
  const attivo = ref(false);
  /** Permesso negato a livello browser: il toggle va spiegato, non riprovato. */
  const negato = ref(false);
  const loading = ref(false);
  const errore = ref('');

  /** La verifica col server non è riuscita (rete assente, backend in
   *  riavvio): diverso da "il canale non c'è". */
  const verificaFallita = ref(false);

  /** I device sottoscritti da questo utente, non solo quello in uso.
   *
   *  Serve a rendere visibile una cosa che altrimenti si scopre solo da una
   *  notifica che non arriva: la sottoscrizione è del **browser**, non della
   *  persona, e chi entra dopo su quello stesso browser se la prende
   *  (l'upsert lato server è per endpoint). Chi si vede la lista vuota sa
   *  perché non riceve più nulla. */
  const dispositivi = ref<DispositivoPush[]>([]);
  /** La lista non è arrivata (rete, backend giù): diverso da «zero device».
   *  Senza distinguerle si finisce per dire «non hai nessun dispositivo» a
   *  chi ne ha, che è esattamente l'assenza muta che il pannello evita. */
  const dispositiviNonLetti = ref(false);
  /** Endpoint di questo browser, per marcare la riga «questo dispositivo». */
  const endpointCorrente = ref('');

  // Il pannello si disegna se il *server* ha il canale, anche quando questo
  // browser non può usarlo: sparire in silenzio lascia l'utente a chiedersi
  // dove sia finito il toggle, ed è esattamente il caso che non si diagnostica.
  const disponibile = computed(() => abilitatoServer.value || verificaFallita.value);

  let publicKey = '';

  async function subscriptionCorrente(): Promise<PushSubscription | null> {
    const reg = await navigator.serviceWorker.ready;
    return reg.pushManager.getSubscription();
  }

  /** Ricarica la lista dei device. Best-effort: un errore qui non deve
   *  spegnere il toggle, che è la funzione principale del pannello. */
  async function caricaDispositivi(): Promise<void> {
    try {
      const { data } = await api.get<PushSubscriptionApi[]>('/api/v1/push-subscriptions/');
      dispositivi.value = data.map((d) => ({
        ...d,
        corrente: d.endpoint === endpointCorrente.value,
      }));
      dispositiviNonLetti.value = false;
    } catch {
      dispositivi.value = [];
      dispositiviNonLetti.value = true;
    }
  }

  /** Disattiva le notifiche su un device dell'elenco.
   *
   *  Se è questo browser va tolta anche la sottoscrizione locale, o il
   *  browser resterebbe iscritto al push service a vuoto e `attivo`
   *  tornerebbe vero al reload successivo. */
  async function rimuoviDispositivo(id: number): Promise<void> {
    const device = dispositivi.value.find((d) => d.id === id);
    errore.value = '';
    loading.value = true;
    try {
      await api.delete(`/api/v1/push-subscriptions/${id}/`);
      if (device?.corrente) {
        const sub = await subscriptionCorrente();
        if (sub) await sub.unsubscribe();
        attivo.value = false;
        endpointCorrente.value = '';
      }
      await caricaDispositivi();
    } catch (e) {
      errore.value = `Rimozione non riuscita: ${e instanceof Error ? e.message : String(e)}`;
    } finally {
      loading.value = false;
    }
  }

  /** Carica stato server + stato locale del device. Da chiamare in onMounted.
   *
   *  Interroga il server anche su un browser che non supporta le push: è il
   *  server a dire se il canale esiste, e senza quella risposta non si può
   *  distinguere «non configurato» da «non l'ho potuto chiedere».
   */
  async function init(tentativi = 3): Promise<void> {
    for (let i = 0; i < tentativi; i++) {
      try {
        const { data } = await api.get<VapidInfo>('/api/v1/push-subscriptions/vapid-public-key/');
        verificaFallita.value = false;
        abilitatoServer.value = data.abilitato;
        publicKey = data.public_key;
        if (!data.abilitato) return;
        // La lista dei device si carica anche da un browser che non può
        // usare le push: è proprio lì che serve vedere quali dispositivi
        // restano attivi altrove.
        if (supportato) {
          negato.value = Notification.permission === 'denied';
          const sub = await subscriptionCorrente();
          endpointCorrente.value = sub?.endpoint ?? '';
          attivo.value = sub !== null;
        }
        await caricaDispositivi();
        return;
      } catch (e: unknown) {
        const stato = (e as { response?: { status?: number } })?.response?.status;
        // Risposta vera del server (403 non autenticato, 404): il canale non
        // c'è per questo utente, inutile insistere.
        if (stato !== undefined && stato < 500) {
          abilitatoServer.value = false;
          verificaFallita.value = false;
          return;
        }
        // Rete assente o backend in riavvio: il dev server riparte in qualche
        // secondo e `init` gira una volta sola, in onMounted. Senza ritentare
        // il toggle resterebbe sparito fino al reload successivo.
        if (i === tentativi - 1) {
          abilitatoServer.value = false;
          verificaFallita.value = true;
          errore.value = 'Non riesco a verificare le notifiche: server non raggiungibile.';
          return;
        }
        await new Promise((r) => setTimeout(r, 800 * (i + 1)));
      }
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
      endpointCorrente.value = sub.endpoint;
      await caricaDispositivi();
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
        const { data } = await api.get<PushSubscriptionApi[]>('/api/v1/push-subscriptions/');
        const mia = data.find((s) => s.endpoint === sub.endpoint);
        if (mia) {
          await api.delete(`/api/v1/push-subscriptions/${mia.id}/`);
        }
        // ...e quella lato browser.
        await sub.unsubscribe();
      }
      attivo.value = false;
      endpointCorrente.value = '';
      await caricaDispositivi();
    } catch (e) {
      errore.value = `Disattivazione non riuscita: ${e instanceof Error ? e.message : String(e)}`;
    } finally {
      loading.value = false;
    }
  }

  /** Invia una notifica di prova a tutti i device dell'utente. */
  async function provaNotifica(): Promise<{ inviate: number }> {
    const { data } = await api.post<{ inviate: number }>('/api/v1/push-subscriptions/test/');
    return data;
  }

  return {
    supportato,
    contestoSicuro,
    origine,
    verificaFallita,
    disponibile,
    attivo,
    negato,
    loading,
    errore,
    dispositivi,
    dispositiviNonLetti,
    init,
    abilita,
    disabilita,
    rimuoviDispositivo,
    provaNotifica,
  };
}
