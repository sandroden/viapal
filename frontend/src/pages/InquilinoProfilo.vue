<template>
  <q-page padding class="vp-i-prof">
    <div class="vp-eyebrow">Profilo</div>
    <h1 class="vp-display vp-i-prof__titolo">{{ nominativo }}</h1>

    <!-- Dati modificabili dall'inquilino -->
    <q-card class="vp-i-prof__card">
      <q-card-section>
        <div class="vp-i-prof__card-titolo">I miei dati</div>
        <q-form ref="datiForm" @submit.prevent="salvaDati" class="q-gutter-md q-mt-sm">
          <q-input
            v-model="form.nominativo"
            label="Nominativo"
            outlined
            dense
            :rules="[(v) => !!v || 'Il nominativo è obbligatorio']"
          />
          <q-input v-model="form.telefono" label="Telefono" outlined dense />
          <q-input
            v-model="form.codice_fiscale"
            label="Codice fiscale"
            outlined
            dense
            maxlength="16"
            style="text-transform: uppercase"
          />
          <q-banner v-if="datiErrore" class="text-white bg-red-7" rounded dense>
            {{ datiErrore }}
          </q-banner>
          <q-btn
            type="submit"
            label="Salva dati"
            color="primary"
            icon="save"
            unelevated
            no-caps
            :loading="datiLoading"
          />
        </q-form>
      </q-card-section>

      <q-separator />

      <q-list>
        <q-item>
          <q-item-section>
            <q-item-label caption>Username</q-item-label>
            <q-item-label>{{ auth.user?.username }}</q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="auth.user?.email">
          <q-item-section>
            <q-item-label caption>Email</q-item-label>
            <q-item-label>{{ auth.user.email }}</q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="stanza">
          <q-item-section>
            <q-item-label caption>Stanza assegnata</q-item-label>
            <q-item-label>
              {{ stanza.nome }} — {{ formattaEuro(stanza.canone_mensile) }}/mese
            </q-item-label>
            <q-item-label caption> Da {{ formattaData(stanza.valid_from) }} </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
    </q-card>

    <!-- Accesso ai documenti -->
    <q-card class="vp-i-prof__card q-mt-md vp-i-prof__link">
      <q-item clickable @click="vaiDocumenti">
        <q-item-section avatar>
          <q-icon name="folder_shared" color="primary" size="28px" />
        </q-item-section>
        <q-item-section>
          <q-item-label>I miei documenti</q-item-label>
          <q-item-label caption>
            Carta d'identità, codice fiscale, passaporto, permesso, contratto di lavoro
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <q-icon name="chevron_right" color="grey-6" />
        </q-item-section>
      </q-item>
    </q-card>

    <!-- Notifiche push: visibile solo se browser e server le supportano -->
    <q-card v-if="push.disponibile.value" class="vp-i-prof__card q-mt-md">
      <q-item>
        <q-item-section avatar>
          <q-icon name="notifications_active" color="primary" size="28px" />
        </q-item-section>
        <q-item-section>
          <q-item-label>Notifiche su questo dispositivo</q-item-label>
          <q-item-label caption>
            Avvisi di bollette e scadenze anche ad app chiusa
          </q-item-label>
        </q-item-section>
        <q-item-section side>
          <q-toggle
            :model-value="push.attivo.value"
            color="primary"
            :disable="push.loading.value || push.negato.value"
            @update:model-value="togglePush"
          />
        </q-item-section>
      </q-item>
      <q-card-section v-if="push.negato.value" class="q-pt-none">
        <q-banner class="text-white bg-orange-8" rounded dense>
          Le notifiche sono bloccate per questo sito: sbloccale dalle
          impostazioni del browser e ricarica la pagina.
        </q-banner>
      </q-card-section>
      <q-card-section v-else-if="push.errore.value" class="q-pt-none">
        <q-banner class="text-white bg-red-7" rounded dense>
          {{ push.errore.value }}
        </q-banner>
      </q-card-section>
      <q-card-section v-if="push.attivo.value" class="q-pt-none">
        <q-btn
          outline
          color="primary"
          icon="send"
          label="Invia notifica di prova"
          no-caps
          size="sm"
          :loading="provaLoading"
          @click="inviaProva"
        />
      </q-card-section>
    </q-card>

    <q-card class="vp-i-prof__card q-mt-md">
      <q-expansion-item icon="lock_reset" label="Cambia password" header-class="text-primary">
        <q-form ref="cambioForm" @submit.prevent="cambiaPassword" class="q-pa-md q-gutter-md">
          <q-input
            v-model="pwdVecchia"
            type="password"
            label="Password attuale"
            outlined
            dense
            :rules="[(v) => !!v || 'Inserisci la password attuale']"
            autocomplete="current-password"
          />
          <q-input
            v-model="pwdNuova1"
            type="password"
            label="Nuova password"
            outlined
            dense
            :rules="[(v) => !!v || 'Inserisci la nuova password', (v) => v.length >= 8 || 'Almeno 8 caratteri']"
            autocomplete="new-password"
          />
          <q-input
            v-model="pwdNuova2"
            type="password"
            label="Conferma nuova password"
            outlined
            dense
            :rules="[(v) => v === pwdNuova1 || 'Le password non coincidono']"
            autocomplete="new-password"
          />
          <q-banner v-if="pwdErrore" class="text-white bg-red-7" rounded dense>
            {{ pwdErrore }}
          </q-banner>
          <q-btn
            type="submit"
            label="Aggiorna password"
            color="primary"
            unelevated
            no-caps
            :loading="pwdLoading"
          />
        </q-form>
      </q-expansion-item>
    </q-card>

    <div class="vp-i-prof__logout">
      <q-btn outline color="primary" icon="logout" label="Esci dal profilo" no-caps @click="logout" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar, type QForm } from 'quasar';
import { api } from 'boot/axios';
import { useAuthStore } from 'stores/auth';
import { useDashboardStore } from 'stores/dashboard';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';
import { usePush } from 'src/composables/usePush';

const auth = useAuthStore();
const router = useRouter();
const $q = useQuasar();
const store = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const stanza = computed(() => store.inquilinoData?.stanza_corrente ?? null);

// --- Dati editabili (fonte autorevole: /tenants/me/) ---
interface DatiMe {
  nominativo: string;
  telefono: string;
  codice_fiscale: string;
}
const form = reactive<DatiMe>({ nominativo: '', telefono: '', codice_fiscale: '' });
const datiForm = ref<QForm | null>(null);
const datiErrore = ref('');
const datiLoading = ref(false);

const nominativo = computed(
  () =>
    form.nominativo ||
    [auth.user?.first_name, auth.user?.last_name].filter(Boolean).join(' ') ||
    auth.user?.username ||
    '—',
);

async function caricaDati() {
  try {
    const { data } = await api.get<DatiMe>('/api/v1/tenants/me/');
    form.nominativo = data.nominativo ?? '';
    form.telefono = data.telefono ?? '';
    form.codice_fiscale = data.codice_fiscale ?? '';
  } catch {
    // Profilo non disponibile (es. proprietario in anteprima): lascia vuoto.
  }
}

onMounted(() => {
  void store.loadInquilino();
  void caricaDati();
  void push.init();
});

// --- Notifiche push ---
const push = usePush();
const provaLoading = ref(false);

async function togglePush(valore: boolean) {
  if (valore) {
    await push.abilita();
    if (push.attivo.value) {
      $q.notify({ type: 'positive', message: 'Notifiche attivate su questo dispositivo.' });
    }
  } else {
    await push.disabilita();
  }
}

async function inviaProva() {
  provaLoading.value = true;
  try {
    const esito = await push.provaNotifica();
    $q.notify({
      type: esito.inviate ? 'positive' : 'warning',
      message: esito.inviate
        ? `Notifica di prova inviata (${esito.inviate} dispositivi).`
        : 'Nessun dispositivo raggiunto: riattiva le notifiche.',
    });
  } catch {
    $q.notify({ type: 'negative', message: 'Invio della prova non riuscito.' });
  } finally {
    provaLoading.value = false;
  }
}

async function salvaDati() {
  datiErrore.value = '';
  datiLoading.value = true;
  try {
    const { data } = await api.patch<DatiMe>('/api/v1/tenants/me/', {
      nominativo: form.nominativo,
      telefono: form.telefono,
      codice_fiscale: form.codice_fiscale.toUpperCase(),
    });
    form.nominativo = data.nominativo ?? '';
    form.telefono = data.telefono ?? '';
    form.codice_fiscale = data.codice_fiscale ?? '';
    // Aggiorna i dati mostrati altrove (home, ecc.).
    void store.loadInquilino();
    $q.notify({ type: 'positive', message: 'Dati aggiornati.' });
  } catch (e: unknown) {
    const d = (e as { response?: { data?: Record<string, unknown> } })?.response?.data;
    datiErrore.value = estraiPrimoErrore(d) ?? 'Impossibile salvare i dati. Riprova.';
  } finally {
    datiLoading.value = false;
  }
}

function estraiPrimoErrore(d: Record<string, unknown> | undefined): string | null {
  if (!d) return null;
  for (const v of Object.values(d)) {
    if (Array.isArray(v) && v.length) return String(v[0]);
    if (typeof v === 'string' && v) return v;
  }
  return null;
}

async function vaiDocumenti() {
  await router.push('/i/documenti');
}

async function logout() {
  await auth.logout();
  await router.replace('/login');
}

// --- Cambio password ---
const cambioForm = ref<QForm | null>(null);
const pwdVecchia = ref('');
const pwdNuova1 = ref('');
const pwdNuova2 = ref('');
const pwdErrore = ref('');
const pwdLoading = ref(false);

function estraiErrorePwd(e: unknown): string {
  const data = (e as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (data) {
    for (const chiave of ['old_password', 'new_password2', 'new_password1', 'detail']) {
      const v = data[chiave];
      if (Array.isArray(v) && v.length) return String(v[0]);
      if (typeof v === 'string' && v) return v;
    }
  }
  return 'Impossibile aggiornare la password. Riprova.';
}

async function cambiaPassword() {
  pwdErrore.value = '';
  pwdLoading.value = true;
  try {
    await auth.changePassword(pwdVecchia.value, pwdNuova1.value, pwdNuova2.value);
    pwdVecchia.value = '';
    pwdNuova1.value = '';
    pwdNuova2.value = '';
    void nextTick(() => cambioForm.value?.resetValidation());
    $q.notify({ type: 'positive', message: 'Password aggiornata.' });
  } catch (e: unknown) {
    pwdErrore.value = estraiErrorePwd(e);
  } finally {
    pwdLoading.value = false;
  }
}
</script>

<style scoped>
.vp-i-prof {
  max-width: 640px;
  margin: 0 auto;
}
.vp-i-prof__titolo {
  font-size: var(--vp-text-2xl);
  margin: var(--vp-gap-1) 0 var(--vp-gap-4);
}
.vp-i-prof__card {
  background: var(--vp-cream);
  border: 1px solid var(--vp-paper-3);
  border-radius: var(--vp-r-lg);
  overflow: hidden;
}
.vp-i-prof__card-titolo {
  font-weight: 600;
  color: var(--vp-ink);
}
.vp-i-prof__link {
  cursor: pointer;
}
.vp-i-prof__logout {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: center;
}
</style>
