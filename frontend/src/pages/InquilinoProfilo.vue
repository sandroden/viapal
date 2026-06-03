<template>
  <q-page padding class="vp-i-prof">
    <div class="vp-eyebrow">Profilo</div>
    <h1 class="vp-display vp-i-prof__titolo">{{ nominativo }}</h1>

    <q-card class="vp-i-prof__card">
      <q-list separator>
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
        <q-item v-if="tenant?.telefono">
          <q-item-section>
            <q-item-label caption>Telefono</q-item-label>
            <q-item-label>{{ tenant.telefono }}</q-item-label>
          </q-item-section>
        </q-item>
        <q-item v-if="stanza">
          <q-item-section>
            <q-item-label caption>Stanza assegnata</q-item-label>
            <q-item-label>
              {{ stanza.nome }} — {{ formattaEuro(stanza.canone_mensile) }}/mese
            </q-item-label>
            <q-item-label caption>
              Da {{ formattaData(stanza.valid_from) }}
            </q-item-label>
          </q-item-section>
        </q-item>
      </q-list>
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

    <p class="vp-i-prof__hint">
      Per modifiche al profilo o alla stanza, contatta il proprietario.
    </p>

    <div class="vp-i-prof__logout">
      <q-btn outline color="primary" icon="logout" label="Esci dal profilo" no-caps @click="logout" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useQuasar, type QForm } from 'quasar';
import { useAuthStore } from 'stores/auth';
import { useDashboardStore } from 'stores/dashboard';
import { useFormatoEuro } from 'src/composables/useFormatoEuro';
import { useFormatoData } from 'src/composables/useFormatoData';

const auth = useAuthStore();
const router = useRouter();
const $q = useQuasar();
const store = useDashboardStore();
const { formattaEuro } = useFormatoEuro();
const { formattaData } = useFormatoData();

const tenant = computed(() => store.inquilinoData?.tenant ?? null);
const stanza = computed(() => store.inquilinoData?.stanza_corrente ?? null);
const nominativo = computed(
  () =>
    tenant.value?.nominativo ||
    [auth.user?.first_name, auth.user?.last_name].filter(Boolean).join(' ') ||
    auth.user?.username ||
    '—',
);

onMounted(() => {
  void store.loadInquilino();
});

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
    // Svuotare i campi rifa scattare le regole "obbligatorio": azzeriamo la
    // validazione così non si vedono errori dopo un cambio riuscito.
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
.vp-i-prof__hint {
  color: var(--vp-ink-3);
  font-size: var(--vp-text-sm);
  margin-top: var(--vp-gap-3);
}
.vp-i-prof__logout {
  margin-top: var(--vp-gap-5);
  display: flex;
  justify-content: center;
}
</style>
