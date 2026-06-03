<template>
  <q-page class="vp-auth-page row items-center justify-center">
    <q-card class="vp-auth-card q-pa-lg">
      <div class="text-h5 text-display q-mb-xs">{{ titolo }}</div>
      <div class="text-subtitle2 text-grey-7 q-mb-md">{{ sottotitolo }}</div>

      <q-form @submit.prevent="onSubmit" class="q-gutter-md">
        <q-input
          v-model="password1"
          :type="mostra ? 'text' : 'password'"
          label="Nuova password"
          autofocus
          outlined
          :rules="[(v) => !!v || 'Inserisci una password', (v) => v.length >= 8 || 'Almeno 8 caratteri']"
          autocomplete="new-password"
        >
          <template #append>
            <q-icon
              :name="mostra ? 'visibility_off' : 'visibility'"
              class="cursor-pointer"
              @click="mostra = !mostra"
            />
          </template>
        </q-input>
        <q-input
          v-model="password2"
          :type="mostra ? 'text' : 'password'"
          label="Conferma password"
          outlined
          :rules="[(v) => !!v || 'Conferma la password', (v) => v === password1 || 'Le password non coincidono']"
          autocomplete="new-password"
        />

        <q-banner v-if="errore" class="text-white bg-red-7 q-mb-sm" rounded>
          {{ errore }}
        </q-banner>

        <q-btn
          type="submit"
          :label="labelBottone"
          color="primary"
          class="full-width"
          :loading="loading"
          unelevated
          size="lg"
        />
      </q-form>

      <div class="q-mt-md text-center">
        <q-btn flat dense no-caps color="primary" label="Torna all'accesso" to="/login" />
      </div>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useQuasar } from 'quasar';
import { useAuthStore } from 'stores/auth';

const route = useRoute();
const router = useRouter();
const $q = useQuasar();
const auth = useAuthStore();

const isInvito = computed(() => route.query.invito === '1');
const titolo = computed(() => (isInvito.value ? 'Benvenuto su Viapal' : 'Reimposta la password'));
const sottotitolo = computed(() =>
  isInvito.value
    ? 'Scegli una password per attivare il tuo accesso.'
    : 'Scegli una nuova password per il tuo accesso.',
);
const labelBottone = computed(() => (isInvito.value ? 'Attiva accesso' : 'Salva password'));

const password1 = ref('');
const password2 = ref('');
const mostra = ref(false);
const errore = ref('');
const loading = ref(false);

function estraiErrore(e: unknown): string {
  const data = (e as { response?: { data?: Record<string, unknown> } })?.response?.data;
  if (data) {
    // dj-rest-auth ritorna errori per campo (token/uid scaduti, password debole...)
    for (const chiave of ['token', 'uid', 'new_password2', 'new_password1', 'detail']) {
      const v = data[chiave];
      if (Array.isArray(v) && v.length) return String(v[0]);
      if (typeof v === 'string' && v) return v;
    }
  }
  return 'Link non valido o scaduto. Richiedi un nuovo link dalla pagina di accesso.';
}

async function onSubmit() {
  errore.value = '';
  loading.value = true;
  try {
    await auth.confirmPasswordReset(
      String(route.params.uid),
      String(route.params.token),
      password1.value,
      password2.value,
    );
    $q.notify({
      type: 'positive',
      message: isInvito.value
        ? 'Accesso attivato! Ora puoi entrare con la tua password.'
        : 'Password aggiornata! Ora puoi accedere.',
    });
    await router.replace('/login');
  } catch (e: unknown) {
    errore.value = estraiErrore(e);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.vp-auth-page {
  min-height: 100vh;
  background: var(--vp-paper);
}
.vp-auth-card {
  width: min(420px, 92vw);
  background: var(--vp-cream);
  border-radius: var(--vp-r-lg);
  box-shadow: var(--vp-shadow-2);
}
</style>
