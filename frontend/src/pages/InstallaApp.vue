<template>
  <q-page padding class="vp-inst">
    <div class="vp-eyebrow">Viapal</div>
    <h1 class="vp-display vp-inst__titolo">Viapal sul tuo dispositivo</h1>
    <p class="vp-inst__occhiello">
      Due cose separate, e conviene farle entrambe: accendere le notifiche, così gli avvisi arrivano
      anche ad app chiusa, e mettere Viapal fra le app, così si apre senza passare dal browser e
      senza rifare l'accesso ogni volta.
    </p>

    <div class="vp-card vp-inst__vantaggi">
      <div v-for="v in VANTAGGI" :key="v.testo" class="vp-inst__vantaggio">
        <q-icon :name="v.icona" size="22px" class="vp-inst__vantaggio-icona" />
        <span>{{ v.testo }}</span>
      </div>
    </div>

    <!-- ── Passo 1: notifiche ─────────────────────────────────────────
         Prima dell'installazione perché quasi ovunque si accendono
         subito: su computer (Chrome e Firefox) e su Android le push
         funzionano senza installare niente. iPhone è l'unica eccezione, e
         lo dice il suo avviso. -->
    <section class="vp-inst__passo">
      <div class="vp-inst__passo-testa">
        <div class="vp-inst__numero">1</div>
        <h2>Accendi le notifiche</h2>
      </div>

      <!-- L'accesso è il prerequisito di *questo* passo, non un passo a sé:
           tenerlo qui evita che la numerazione cambi a seconda del login. -->
      <div v-if="!auth.isAuthenticated" class="vp-card vp-inst__corpo">
        <p class="vp-hint">
          Le notifiche si attivano per te, quindi serve prima l'accesso. Se non hai ancora una
          password, usa il link d'invito che ti è arrivato per email.
        </p>
        <q-btn
          unelevated
          color="primary"
          icon="login"
          label="Accedi"
          no-caps
          class="vp-inst__cta"
          data-testid="installa-accedi"
          @click="vaiAlLogin"
        />
      </div>

      <!-- iOS non espone le push a Safari: solo alla PWA installata (iOS
           16.4+). Mostrare qui un toggle che non può funzionare sarebbe
           peggio che spiegare l'ordine dei passi. -->
      <div v-else-if="pushRichiedeInstallazione" class="vp-card vp-inst__corpo">
        <q-banner rounded class="vp-inst__banner" data-testid="installa-ios-prima">
          <template #avatar>
            <q-icon name="info" color="primary" />
          </template>
          Su iPhone e iPad le notifiche arrivano <strong>solo all'app installata</strong>: qui sei
          nell'eccezione, fai prima il passo 2. Poi apri Viapal dall'icona nella schermata
          principale e torna su questa pagina — l'interruttore comparirà qui.
        </q-banner>
      </div>

      <NotifichePushPannello v-else class="vp-inst__corpo" :descrizione="DESCRIZIONE_NOTIFICHE" />
    </section>

    <!-- ── Passo 2: installazione ─────────────────────────────────── -->
    <section class="vp-inst__passo">
      <div class="vp-inst__passo-testa">
        <div class="vp-inst__numero" :class="{ 'vp-inst__numero--fatto': installata }">
          <q-icon v-if="installata" name="check" size="18px" />
          <template v-else>2</template>
        </div>
        <h2>Mettila fra le tue app</h2>
        <span v-if="!facoltativa" class="vp-badge vp-badge--wait">serve per le notifiche</span>
        <span v-else class="vp-inst__facoltativo">facoltativo</span>
      </div>

      <div class="vp-card vp-inst__corpo">
        <div v-if="installata" class="vp-inst__esito" data-testid="installa-gia-fatto">
          <q-icon name="check_circle" color="positive" size="24px" />
          <div><strong>Fatto.</strong> Stai già usando Viapal come app installata.</div>
        </div>

        <template v-else>
          <!-- Il link arriva quasi sempre da WhatsApp, e dal browser interno
               di WhatsApp non si installa niente: la voce di menu descritta
               più sotto lì non esiste proprio. -->
          <q-banner v-if="inApp" rounded class="vp-inst__banner" data-testid="installa-in-app">
            <template #avatar>
              <q-icon name="open_in_browser" color="warning" />
            </template>
            Stai guardando questa pagina dentro un'altra app (WhatsApp, Facebook…), e da qui non si
            può installare nulla. Apri il link in
            {{ piattaforma === 'ios' ? 'Safari' : 'Chrome' }}: di solito c'è una voce «Apri nel
            browser» nel menu in alto.
          </q-banner>

          <q-btn
            v-if="installabileConBottone"
            unelevated
            color="primary"
            size="lg"
            icon="install_mobile"
            label="Installa Viapal su questo dispositivo"
            no-caps
            class="full-width vp-inst__cta"
            data-testid="installa-bottone"
            @click="onInstalla"
          />

          <!-- Da computer l'installazione conta poco: le notifiche lì
               arrivano comunque. Quello che serve è portare la pagina sul
               telefono, dove l'app sta in tasca — inquadrando o mandandosi
               il link. -->
          <div v-if="suDesktop" class="vp-inst__porta" data-testid="installa-qr">
            <img v-if="qrDataUrl" :src="qrDataUrl" alt="QR di questa pagina" class="vp-inst__qr" />
            <div class="vp-inst__porta-testo">
              <div class="vp-section-title">Portala sul telefono</div>
              <p class="vp-hint">
                Inquadra il codice con la fotocamera, o mandati il link: è lì che l'app serve
                davvero, e su iPhone è l'unico modo per ricevere le notifiche.
              </p>
              <q-btn
                outline
                dense
                no-caps
                color="primary"
                icon="content_copy"
                label="Copia il link"
                @click="copiaLink"
              />
            </div>
          </div>

          <!-- Le istruzioni ci sono per tutte e tre le piattaforme, sempre.
               Il rilevamento decide quale è *aperta*, non quale esiste: chi
               legge da un computer deve poter leggere cosa dire a chi ha un
               telefono, ed è l'uso principale di questa pagina. -->
          <div class="vp-inst__istruzioni" data-testid="installa-istruzioni">
            <div class="vp-section-title">Come si fa</div>
            <!-- `default-opened` e non `model-value`: legata al valore la
                 sezione resterebbe bloccata com'è e le altre due non si
                 aprirebbero al tocco. -->
            <q-list separator class="vp-inst__sezioni">
              <q-expansion-item
                v-for="s in sezioni"
                :key="s.chiave"
                :default-opened="s.chiave === piattaforma"
                :icon="s.icona"
                :label="s.etichetta"
                :caption="s.chiave === piattaforma ? 'stai leggendo da qui' : undefined"
                :header-class="s.chiave === piattaforma ? 'vp-inst__sezione--qui' : ''"
                :data-testid="`installa-sezione-${s.chiave}`"
              >
                <div class="vp-inst__sezione-corpo">
                  <!-- Firefox su computer non installa affatto le app web.
                       L'avviso sta *accanto* alle istruzioni di Chrome/Edge,
                       non al posto loro: dire solo "non si può" lasciava la
                       pagina senza una sola strada percorribile. -->
                  <q-banner
                    v-if="s.avviso"
                    rounded
                    dense
                    class="vp-inst__banner"
                    data-testid="installa-non-supportato"
                  >
                    <template #avatar>
                      <q-icon name="info" color="primary" />
                    </template>
                    <span v-html="s.avviso" />
                  </q-banner>
                  <!-- Dove c'è l'avviso, i passi che seguono sono di un
                       *altro* browser: senza dirlo la lista sembra
                       contraddire l'avviso appena letto. -->
                  <p v-if="s.introPassi" class="vp-inst__intro">{{ s.introPassi }}</p>
                  <ol>
                    <li v-for="(passo, i) in s.passi" :key="i"><span v-html="passo" /></li>
                  </ol>
                  <p v-if="s.nota" class="vp-hint vp-inst__nota">{{ s.nota }}</p>
                </div>
              </q-expansion-item>
            </q-list>
          </div>

          <q-btn
            v-if="!suDesktop"
            flat
            dense
            no-caps
            color="primary"
            icon="content_copy"
            label="Copia il link di questa pagina"
            class="vp-inst__copia"
            @click="copiaLink"
          />
        </template>
      </div>
    </section>

    <div v-if="auth.isAuthenticated" class="vp-inst__fine">
      <q-btn
        outline
        color="primary"
        icon="arrow_forward"
        label="Vai all'app"
        no-caps
        @click="router.push(auth.homePath)"
      />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import QRCode from 'qrcode';
import { useAuthStore } from 'stores/auth';
import { useInstallPwa, type Piattaforma } from 'src/composables/useInstallPwa';
import NotifichePushPannello from 'components/profilo/NotifichePushPannello.vue';

const auth = useAuthStore();
const router = useRouter();
const $q = useQuasar();
const {
  piattaforma,
  motore,
  installabile,
  inApp,
  installata,
  installabileConBottone,
  pushRichiedeInstallazione,
  installa,
} = useInstallPwa();

const suDesktop = piattaforma === 'desktop';
const urlPagina = `${window.location.origin}/installa`;

/** Su iPhone l'installazione non è una comodità: senza, niente notifiche. */
const facoltativa = piattaforma !== 'ios';

// La pagina è pubblica: quasi sempre la si apre prima del login, quando il
// ruolo non si sa ancora. Anche dopo, distinguere inquilino e proprietario
// qui non aggiunge nulla — chi legge vuole sapere a cosa serve, non quale
// evento tocca a lui. Testi anfibi, buoni per entrambi.
const VANTAGGI = [
  {
    icona: 'notifications_active',
    testo: 'Ti avvisa quando c’è un pagamento da fare o da confermare',
  },
  { icona: 'bolt', testo: 'Si apre da sola, senza cercare il sito nel browser' },
  { icona: 'lock_open', testo: 'Resti connesso: niente password ogni volta' },
];

const DESCRIZIONE_NOTIFICHE = 'Avvisi di scadenze e pagamenti, anche ad app chiusa';

interface Sezione {
  chiave: Piattaforma;
  etichetta: string;
  icona: string;
  passi: string[];
  nota: string;
  /** Riquadro sopra le istruzioni, per il browser che non può installare. */
  avviso?: string;
  /** Riga che dice a quale browser si riferiscono i passi, quando non è
   *  quello in uso. */
  introPassi?: string;
}

/**
 * Le tre piattaforme, sempre tutte e tre.
 *
 * Ogni sezione ha un contenuto **predefinito** — il browser più diffuso su
 * quella piattaforma — e usa la variante del browser reale **solo se è la
 * piattaforma rilevata**: degli altri dispositivi non sappiamo il browser,
 * e indovinarlo produrrebbe istruzioni sbagliate con l'aria di essere
 * giuste.
 */
const sezioni = computed<Sezione[]>(() => [
  {
    chiave: 'ios',
    etichetta: 'Su iPhone e iPad',
    icona: 'phone_iphone',
    // Su iOS ogni browser è WebKit per obbligo di piattaforma: una sola
    // istruzione, cambia solo dove sta il pulsante Condividi.
    passi: [
      'Tocca <strong>Condividi</strong>, il quadrato con la freccia in su (in Safari è in basso, negli altri browser nel menu in alto).',
      'Scorri e tocca <strong>Aggiungi a Home</strong>.',
      'Conferma con <strong>Aggiungi</strong>: l’icona di Viapal compare fra le altre app.',
    ],
    nota: 'Su iPhone questo passaggio non è facoltativo: le notifiche arrivano solo all’app installata (da iOS 16.4).',
  },
  {
    chiave: 'android',
    etichetta: 'Su Android',
    icona: 'android',
    passi:
      piattaforma === 'android' && motore === 'firefox'
        ? [
            'Tocca i <strong>tre puntini</strong> in alto a destra.',
            'Scegli <strong>Installa</strong> (in alcune versioni: «Aggiungi a schermata Home»).',
            'Conferma: l’icona di Viapal compare fra le altre app.',
          ]
        : [
            'Tocca i <strong>tre puntini</strong> in alto a destra.',
            'Scegli <strong>Installa app</strong> (in alcune versioni: «Aggiungi a schermata Home»).',
            'Conferma: l’icona di Viapal compare fra le altre app.',
          ],
    nota: 'Non trovi la voce? Dal browser interno di WhatsApp non si installa: apri il link in Chrome o in Firefox.',
  },
  sezioneComputer(),
]);

function sezioneComputer(): Sezione {
  const rilevato = suDesktop;
  // Safari installa dal menu Archivio, e solo da macOS 14 (Sonoma).
  if (rilevato && motore === 'safari') {
    return {
      chiave: 'desktop',
      etichetta: 'Su computer (Safari)',
      icona: 'computer',
      passi: [
        'Apri il menu <strong>Archivio</strong> nella barra in alto.',
        'Scegli <strong>Aggiungi al Dock</strong>.',
        'Conferma: Viapal compare nel Dock e si apre come un’applicazione.',
      ],
      nota: 'La voce c’è da macOS 14 (Sonoma) in poi. Su versioni precedenti serve Chrome o Edge.',
    };
  }
  const base: Sezione = {
    chiave: 'desktop',
    etichetta: 'Su computer',
    icona: 'computer',
    passi: [
      'Cerca l’icona <strong>Installa</strong> nella barra degli indirizzi, a destra.',
      'In alternativa: menu <strong>⋮</strong> → <strong>Installa Viapal</strong>.',
    ],
    nota: 'Vale per Chrome, Edge, Brave e Opera. Su Mac, con Safari: Archivio → Aggiungi al Dock.',
  };
  // Firefox su computer non installa le app web: serve un'estensione, il
  // supporto nativo è sperimentale e solo su Windows. Lo si dice, e si
  // lasciano comunque le istruzioni per il browser che funziona.
  if (rilevato && !installabile.value) {
    return {
      ...base,
      etichetta: 'Su computer (Firefox)',
      introPassi: 'In Chrome, Edge, Brave o Opera:',
      // La nota di base ripete i browser, che l'intro ha già nominato.
      nota: 'Su Mac, con Safari: Archivio → Aggiungi al Dock.',
      avviso:
        '<strong>Firefox su computer non installa le app web.</strong> Le notifiche, però, le ricevi lo stesso: il passo 1 funziona così com’è. Per avere anche l’icona dell’app, apri questa pagina in Chrome o in Edge.',
    };
  }
  return base;
}

const qrDataUrl = ref('');

onMounted(async () => {
  if (!suDesktop) return;
  try {
    qrDataUrl.value = await QRCode.toDataURL(urlPagina, {
      errorCorrectionLevel: 'M',
      margin: 1,
      width: 200,
    });
  } catch {
    // Nessun QR: restano il link da copiare e le istruzioni scritte.
    qrDataUrl.value = '';
  }
});

async function onInstalla() {
  const esito = await installa();
  if (esito === 'dismissed') {
    $q.notify({
      type: 'info',
      message: 'Installazione annullata. Puoi rifarlo dal menu del browser.',
    });
  }
}

function vaiAlLogin() {
  void router.push({ path: '/login', query: { next: '/installa' } });
}

async function copiaLink() {
  try {
    await navigator.clipboard.writeText(urlPagina);
    $q.notify({ type: 'positive', message: 'Link copiato.' });
  } catch {
    // Niente clipboard (contesto non sicuro, permesso negato): mostrarlo
    // basta, si seleziona a mano.
    $q.notify({ type: 'info', message: urlPagina, timeout: 8000 });
  }
}
</script>

<style scoped>
.vp-inst {
  max-width: 640px;
  margin: 0 auto;
}
.vp-inst__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-3);
}
.vp-inst__occhiello {
  font-size: var(--vp-text-sm);
  line-height: 1.55;
  color: var(--vp-ink-2);
  margin: 0 0 var(--vp-gap-5);
}

.vp-inst__vantaggi {
  padding: var(--vp-gap-4);
  display: grid;
  gap: var(--vp-gap-3);
}
.vp-inst__vantaggio {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  font-size: var(--vp-text-sm);
  color: var(--vp-ink-2);
}
.vp-inst__vantaggio-icona {
  color: var(--vp-terra);
  flex: 0 0 auto;
}

.vp-inst__passo {
  margin-top: var(--vp-gap-6);
}
.vp-inst__passo-testa {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  margin-bottom: var(--vp-gap-3);
  flex-wrap: wrap;
}
.vp-inst__passo-testa h2 {
  font-size: var(--vp-text-lg);
  font-weight: 600;
  margin: 0;
}
.vp-inst__facoltativo {
  font-size: var(--vp-text-xs);
  color: var(--vp-ink-3);
}
.vp-inst__numero {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--vp-terra-soft);
  color: var(--vp-terra-deep);
  font-size: var(--vp-text-sm);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.vp-inst__numero--fatto {
  background: var(--vp-sage-soft);
  color: var(--vp-sage-deep);
}

.vp-inst__corpo {
  padding: var(--vp-gap-4);
}
.vp-inst__esito {
  display: flex;
  align-items: center;
  gap: var(--vp-gap-3);
  font-size: var(--vp-text-sm);
}
.vp-inst__banner {
  background: var(--vp-paper-2);
  color: var(--vp-ink-2);
  font-size: var(--vp-text-sm);
  line-height: 1.5;
}
.vp-inst__cta {
  border-radius: var(--vp-r-pill);
}

/* Riquadro "portala sul telefono": QR a sinistra, testo a destra, in
   colonna quando la finestra si stringe. */
.vp-inst__porta {
  display: flex;
  gap: var(--vp-gap-4);
  align-items: center;
  flex-wrap: wrap;
  padding: var(--vp-gap-4);
  border-radius: var(--vp-r-md);
  background: var(--vp-paper-2);
  margin-bottom: var(--vp-gap-4);
}
.vp-inst__qr {
  width: 132px;
  height: 132px;
  max-width: 100%;
  border-radius: var(--vp-r-sm);
  background: #fff;
  flex: 0 0 auto;
}
.vp-inst__porta-testo {
  flex: 1 1 220px;
  min-width: 0;
}
.vp-inst__porta-testo p {
  margin: var(--vp-gap-1) 0 var(--vp-gap-3);
}

.vp-inst__istruzioni {
  margin-top: var(--vp-gap-2);
}
.vp-inst__sezioni {
  margin-top: var(--vp-gap-2);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-md);
  overflow: hidden;
}
.vp-inst__sezione--qui {
  background: var(--vp-paper-2);
}
.vp-inst__sezione-corpo {
  padding: 0 var(--vp-gap-4) var(--vp-gap-4);
}
.vp-inst__sezione-corpo ol {
  margin: var(--vp-gap-2) 0 0;
  padding-left: 20px;
  font-size: var(--vp-text-sm);
  line-height: 1.6;
  color: var(--vp-ink-2);
}
.vp-inst__sezione-corpo li + li {
  margin-top: var(--vp-gap-2);
}
.vp-inst__intro {
  margin: var(--vp-gap-3) 0 0;
  font-size: var(--vp-text-sm);
  font-weight: 500;
  color: var(--vp-ink-2);
}
.vp-inst__nota {
  margin: var(--vp-gap-3) 0 0;
}
.vp-inst__copia {
  margin-top: var(--vp-gap-3);
}
.vp-inst__fine {
  margin: var(--vp-gap-6) 0 var(--vp-gap-5);
  text-align: center;
}
</style>
