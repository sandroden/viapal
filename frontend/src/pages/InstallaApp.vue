<template>
  <q-page padding class="vp-inst">
    <div class="vp-eyebrow">Viapal</div>
    <h1 class="vp-display vp-inst__titolo">{{ titolo }}</h1>
    <p class="vp-inst__occhiello">
      Viapal è un sito che si comporta come un'app: si aggiunge
      {{ suDesktop ? 'al computer' : 'alla schermata principale del telefono' }} e da lì si apre
      {{ suDesktop ? 'con un clic' : 'con un tocco' }}, senza passare dal browser e senza rifare
      l'accesso ogni volta.
      <template v-if="piattaforma === 'ios'">
        Su iPhone è anche l'unica strada per ricevere le notifiche.
      </template>
    </p>

    <!-- Cosa ci si guadagna: la pagina la apre chi non sa perché dovrebbe
         installare qualcosa, e la ragione va data prima delle istruzioni. -->
    <div class="vp-card vp-inst__vantaggi">
      <div v-for="v in vantaggi" :key="v.testo" class="vp-inst__vantaggio">
        <q-icon :name="v.icona" size="22px" class="vp-inst__vantaggio-icona" />
        <span>{{ v.testo }}</span>
      </div>
    </div>

    <!-- ── Passo 1: installazione ─────────────────────────────────── -->
    <section class="vp-inst__passo">
      <div class="vp-inst__passo-testa">
        <div class="vp-inst__numero" :class="{ 'vp-inst__numero--fatto': installata }">
          <q-icon v-if="installata" name="check" size="18px" />
          <template v-else>1</template>
        </div>
        <h2>{{ titoloPasso }}</h2>
      </div>

      <div class="vp-card vp-inst__corpo">
        <template v-if="installata">
          <div class="vp-inst__esito" data-testid="installa-gia-fatto">
            <q-icon name="check_circle" color="positive" size="24px" />
            <div><strong>Fatto.</strong> Stai già usando Viapal come app installata.</div>
          </div>
        </template>

        <template v-else>
          <!-- Il link arriva quasi sempre da WhatsApp, e dal browser interno
               di WhatsApp non si installa niente: la voce di menu che stiamo
               per descrivere lì non esiste proprio. -->
          <q-banner v-if="inApp" rounded class="vp-inst__banner" data-testid="installa-in-app">
            <template #avatar>
              <q-icon name="open_in_browser" color="warning" />
            </template>
            Stai guardando questa pagina dentro un'altra app (WhatsApp, Facebook…), e da qui non si
            può installare nulla. Apri il link in
            {{ piattaforma === 'ios' ? 'Safari' : 'Chrome' }}: di solito c'è una voce «Apri nel
            browser» nel menu in alto.
          </q-banner>

          <!-- Firefox su computer non ha alcun modo di installare: mandarlo a
               cercare la voce di menu delle istruzioni sarebbe una caccia a
               vuoto. Si dice com'è e si indica la strada che funziona. -->
          <q-banner
            v-if="!installabile"
            rounded
            class="vp-inst__banner"
            data-testid="installa-non-supportato"
          >
            <template #avatar>
              <q-icon name="info" color="primary" />
            </template>
            <strong>Firefox su computer non installa le app web.</strong> Per avere Viapal come
            applicazione apri questa pagina in Chrome o in Edge — oppure, meglio, installala sul
            telefono: è lì che servono le notifiche. Le notifiche su Firefox funzionano comunque
            anche senza installare: vai pure al passo successivo.
          </q-banner>

          <q-btn
            v-if="installabileConBottone"
            unelevated
            color="primary"
            size="lg"
            icon="install_mobile"
            label="Installa Viapal"
            no-caps
            class="full-width vp-inst__cta"
            data-testid="installa-bottone"
            @click="onInstalla"
          />

          <!-- Le istruzioni manuali restano visibili anche quando il bottone
               c'è: se il browser rifiuta il prompt (o l'utente lo chiude per
               sbaglio) senza di esse non resta niente da fare. -->
          <div v-if="installabile" class="vp-inst__istruzioni" data-testid="installa-istruzioni">
            <div class="vp-section-title">
              {{ installabileConBottone ? 'Oppure a mano' : istruzioni.titolo }}
            </div>
            <ol>
              <li v-for="(passo, i) in istruzioni.passi" :key="i">
                <span v-html="passo" />
              </li>
            </ol>
            <p v-if="istruzioni.nota" class="vp-hint vp-inst__nota">{{ istruzioni.nota }}</p>
          </div>

          <q-btn
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

    <!-- ── Passo 2: accesso ───────────────────────────────────────── -->
    <section v-if="!auth.isAuthenticated" class="vp-inst__passo">
      <div class="vp-inst__passo-testa">
        <div class="vp-inst__numero">2</div>
        <h2>Entra con le tue credenziali</h2>
      </div>
      <div class="vp-card vp-inst__corpo">
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
    </section>

    <!-- ── Passo 3: notifiche ─────────────────────────────────────── -->
    <section class="vp-inst__passo">
      <div class="vp-inst__passo-testa">
        <div class="vp-inst__numero">{{ auth.isAuthenticated ? 2 : 3 }}</div>
        <h2>Accendi le notifiche</h2>
      </div>

      <div v-if="!auth.isAuthenticated" class="vp-card vp-inst__corpo">
        <p class="vp-hint q-mb-none">Il pulsante per attivarle compare qui dopo l'accesso.</p>
      </div>

      <!-- iOS non espone le push a Safari: solo alla PWA installata (iOS
           16.4+). Mostrare qui un toggle che non può funzionare sarebbe
           peggio che spiegare l'ordine dei passi. -->
      <div v-else-if="pushRichiedeInstallazione" class="vp-card vp-inst__corpo">
        <q-banner rounded class="vp-inst__banner" data-testid="installa-ios-prima">
          <template #avatar>
            <q-icon name="info" color="primary" />
          </template>
          Su iPhone e iPad le notifiche arrivano <strong>solo all'app installata</strong>. Completa
          il passo 1, poi apri Viapal dall'icona nella schermata principale e torna su questa
          pagina: qui troverai l'interruttore.
        </q-banner>
      </div>

      <NotifichePushPannello v-else class="vp-inst__corpo" :descrizione="descrizioneNotifiche" />
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
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useAuthStore } from 'stores/auth';
import { useInstallPwa } from 'src/composables/useInstallPwa';
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
const titolo = suDesktop ? "Installa l'app sul computer" : "Installa l'app sul telefono";
const titoloPasso = suDesktop
  ? 'Installa Viapal sul computer'
  : 'Metti Viapal nella schermata principale';

// La pagina è pubblica: quasi sempre la si apre prima del login, quando il
// ruolo non si sa ancora. Anche dopo, distinguere inquilino e proprietario
// qui non aggiunge nulla — chi legge vuole sapere a cosa serve, non quale
// evento tocca a lui. Testi anfibi, buoni per entrambi.
const vantaggi = [
  {
    icona: 'notifications_active',
    testo: 'Ti avvisa quando c’è un pagamento da fare o da confermare',
  },
  {
    icona: 'bolt',
    testo: suDesktop
      ? 'Si apre come un’applicazione, senza browser'
      : 'Si apre con un tocco, come un’app',
  },
  { icona: 'lock_open', testo: 'Resti connesso: niente password ogni volta' },
];

const descrizioneNotifiche = 'Avvisi di scadenze e pagamenti, anche ad app chiusa';

/** Le istruzioni manuali: l'unica strada su iOS e su Safari, e la rete di
 *  sicurezza dove il prompt automatico c'è ma può essere chiuso per sbaglio.
 *
 *  Dipendono dal **browser**, non solo dalla piattaforma: su computer la
 *  voce di menu di Chrome non esiste in Safari, e in Firefox non esiste
 *  affatto (quel ramo non arriva neppure qui, vedi `installabile`). */
const istruzioni = computed(() => {
  if (piattaforma === 'ios') {
    return {
      // Su iOS anche Chrome e Firefox sono WebKit: stessa condivisione,
      // cambia solo dove sta il pulsante.
      titolo: 'Su iPhone e iPad',
      passi: [
        'Tocca <strong>Condividi</strong>, il quadrato con la freccia in su (in Safari è in basso, negli altri browser nel menu in alto).',
        'Scorri e tocca <strong>Aggiungi a Home</strong>.',
        'Conferma con <strong>Aggiungi</strong>: l’icona di Viapal compare fra le altre app.',
      ],
      nota: 'Non trovi «Aggiungi a Home»? Stai probabilmente guardando la pagina dentro un’altra app: apri questo link in Safari.',
    };
  }
  if (piattaforma === 'android') {
    if (motore === 'firefox') {
      return {
        titolo: 'Su Android (Firefox)',
        passi: [
          'Tocca i <strong>tre puntini</strong> in alto a destra.',
          'Scegli <strong>Installa</strong> (in alcune versioni: «Aggiungi a schermata Home»).',
          'Conferma: l’icona di Viapal compare fra le altre app.',
        ],
        nota: '',
      };
    }
    return {
      titolo: 'Su Android (Chrome)',
      passi: [
        'Tocca i <strong>tre puntini</strong> in alto a destra.',
        'Scegli <strong>Installa app</strong> (in alcune versioni: «Aggiungi a schermata Home»).',
        'Conferma: l’icona di Viapal compare fra le altre app.',
      ],
      nota: 'Non trovi «Installa app»? Apri questo link in Chrome: dal browser di WhatsApp non si installa.',
    };
  }
  if (motore === 'safari') {
    return {
      // Safari installa dal menu Archivio, e solo da macOS 14 (Sonoma).
      titolo: 'Su Mac (Safari)',
      passi: [
        'Apri il menu <strong>Archivio</strong> nella barra in alto.',
        'Scegli <strong>Aggiungi al Dock</strong>.',
        'Conferma: Viapal compare nel Dock e si apre come un’applicazione.',
      ],
      nota: 'La voce c’è da macOS 14 (Sonoma) in poi. Su versioni precedenti usa Chrome o Edge.',
    };
  }
  return {
    titolo: 'Su computer (Chrome, Edge o Brave)',
    passi: [
      'Cerca l’icona <strong>Installa</strong> nella barra degli indirizzi, a destra.',
      'In alternativa: menu <strong>⋮</strong> → <strong>Installa Viapal</strong>.',
    ],
    nota: '',
  };
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
  const url = `${window.location.origin}/installa`;
  try {
    await navigator.clipboard.writeText(url);
    $q.notify({ type: 'positive', message: 'Link copiato.' });
  } catch {
    // Niente clipboard (contesto non sicuro, permesso negato): mostrarlo
    // basta, si seleziona a mano.
    $q.notify({ type: 'info', message: url, timeout: 8000 });
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
}
.vp-inst__passo-testa h2 {
  font-size: var(--vp-text-lg);
  font-weight: 600;
  margin: 0;
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
.vp-inst__istruzioni {
  margin-top: var(--vp-gap-4);
}
.vp-inst__istruzioni ol {
  margin: var(--vp-gap-2) 0 0;
  padding-left: 20px;
  font-size: var(--vp-text-sm);
  line-height: 1.6;
  color: var(--vp-ink-2);
}
.vp-inst__istruzioni li + li {
  margin-top: var(--vp-gap-2);
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
